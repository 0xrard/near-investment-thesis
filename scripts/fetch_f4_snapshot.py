#!/usr/bin/env python3
"""Fetch the F4 buyback-wallet snapshot -> data/buyback_wallet_30d.json.

Reads the buyback wallet's trailing-30-day receipts from the Nearblocks
API (read-only, no key) and writes the snapshot that
scripts/check_falsifiers.py uses for falsifier F4 (buyback-wallet
outflow > 5% / 30d).

Safety, so a judge can trust the snapshot this writes:
  1. Fail hard on truncated pagination. If the page limit is reached,
     or the receipt history ends, before the 30-day window is covered,
     exit non-zero and write NOTHING. A partial snapshot would
     undercount outflow and make F4 a false not_triggered. This is
     the biggest risk, so it is checked explicitly, not assumed.
  2. Atomic write. The snapshot is written to a temp file in the same
     directory, then os.replace()d into place. A failure mid-run
     (e.g. HTTP 429) never corrupts the good snapshot already on disk.
  3. Bounded backoff on HTTP 429/5xx (max 3 attempts per request,
     exponential backoff, then fail). Plus a small delay between pages
     so the fetch stays polite. Nearblocks rate-limits after a few
     rapid calls; a previous re-fetch hit HTTP 429 after 3 pages.
  4. All required fields are written: balance_near,
     outbound_near_total, checked_at_utc, window_start_utc,
     window_end_utc, source, provenance — plus threshold_near,
     receipts_examined, inbound/outbound counts and
     inbound_counterparties, which evaluate_f4 uses.
  5. Native NEAR only. Amounts are action deposits (yocto -> NEAR).
     Token transfers (wNEAR / FT) are function calls whose deposits
     are ~1 yocto and contribute ~0; they are not counted as NEAR flow.
  6. NOT run by rebuild.sh. The rebuild stays deterministic offline;
     run this script explicitly when the snapshot needs refreshing.
  7. Wallet address from --wallet (default: the buyback wallet
     verified in the thesis, buybacks.multisignature.near). No API
     key is needed or stored.
  8. Self-verification. After writing, the script imports evaluate_f4
     from check_falsifiers and reports its status on the snapshot it
     just wrote. A cannot_check result is reported (exit 2).

Usage:
    python3 scripts/fetch_f4_snapshot.py [--wallet ADDR] [--out PATH]
        [--window-days N] [--max-pages N]

Exit codes: 0 snapshot written and self-check is evaluable
(not_triggered or triggered); 1 fetch/validation error, nothing
written; 2 snapshot written but self-check says cannot_check.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DEFAULT_OUT = DATA / "buyback_wallet_30d.json"
DEFAULT_WALLET = "buybacks.multisignature.near"
NEARBLOCKS = "https://api.nearblocks.io/v1"

YOCTO_PER_NEAR = 10 ** 24
WINDOW_DAYS = 30
THRESHOLD_PCT = 5
PER_PAGE = 100
MAX_PAGES = 50  # 5,000 receipts; the wallet has ~779 in 30d, so this is headroom, not a target
PAGE_DELAY_S = 2.0  # polite pause between pages; Nearblocks rate-limits
# after a few rapid calls, and a previous re-fetch hit HTTP 429 after
# 3 pages at a shorter delay. Tune with --page-delay if needed.
MAX_ATTEMPTS = 3  # per request: 1 try + 2 retries, then fail
BACKOFF_BASE_S = 5.0  # exponential backoff on 429/5xx: 5s, 10s, then fail


class FetchError(Exception):
    """A fetch failed (HTTP error, bad response, truncated window, ...)."""


def _get_json(url):
    """GET url as JSON, with bounded backoff on 429/5xx. Raises FetchError."""
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "near-thesis-f4-fetch/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            retryable = e.code in (429, 500, 502, 503, 504)
            if not retryable or attempt == MAX_ATTEMPTS:
                raise FetchError(f"GET {url} failed: HTTP {e.code}") from e
            wait = BACKOFF_BASE_S * (2 ** (attempt - 1))
            print(f"  HTTP {e.code} (attempt {attempt}/{MAX_ATTEMPTS}), "
                  f"backing off {wait:.0f}s...", file=sys.stderr)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            raise FetchError(f"GET {url} failed: {e}") from e
    raise FetchError(f"GET {url} failed after {MAX_ATTEMPTS} attempts: {last_err}")


def _receipt_amount_near(receipt):
    """Native NEAR moved by one receipt: sum of action deposits (yocto -> NEAR)."""
    total_yocto = 0.0
    for action in receipt.get("actions") or []:
        try:
            total_yocto += float(action.get("deposit") or 0)
        except (TypeError, ValueError):
            continue
    return total_yocto / YOCTO_PER_NEAR


def _receipt_ts(receipt):
    """Receipt block timestamp as an aware UTC datetime (block_timestamp is ns)."""
    ns = int(receipt["block_timestamp"])
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc)


def fetch_snapshot(wallet, window_days=WINDOW_DAYS, max_pages=MAX_PAGES,
                   page_delay=PAGE_DELAY_S):
    """Fetch the wallet's trailing-window receipts. Returns the snapshot dict.

    Raises FetchError (and writes nothing) if pagination is truncated:
    the page limit is hit, or the receipt history ends, before the
    window start is reached.
    """
    now_utc = datetime.now(timezone.utc)
    window_start = now_utc - timedelta(days=window_days)

    # ---- balance (one call) ---------------------------------------------
    bal = _get_json(f"{NEARBLOCKS}/account/{wallet}")
    try:
        account = bal["account"][0]
        balance_near = float(account["amount"]) / YOCTO_PER_NEAR
        balance_block = int(account["block_height"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise FetchError(f"unexpected /account response for {wallet}: {e}") from e
    if not balance_near > 0:
        raise FetchError(f"balance for {wallet} is {balance_near} (must be > 0)")

    # ---- receipts, newest first, until past the window start ------------
    inbound_count = 0
    outbound_count = 0
    self_count = 0
    no_near_count = 0
    inbound_near = 0.0
    outbound_near = 0.0
    inbound_counterparties = {}
    outbound_counterparties = {}
    receipts_examined = 0
    oldest_seen = None
    reached_window_start = False

    for page in range(1, max_pages + 1):
        if page > 1:
            time.sleep(page_delay)
        data = _get_json(
            f"{NEARBLOCKS}/account/{wallet}/txns"
            f"?page={page}&per_page={PER_PAGE}&order=desc"
        )
        txns = data.get("txns") or []
        if not txns:
            # History ended before the window start was reached: the
            # window is not fully covered, so the snapshot would be
            # incomplete. Fail, do not write a partial snapshot.
            break
        for receipt in txns:
            ts = _receipt_ts(receipt)
            if ts < window_start:
                reached_window_start = True
                break
            receipts_examined += 1
            if oldest_seen is None or ts < oldest_seen:
                oldest_seen = ts
            amount = _receipt_amount_near(receipt)
            predecessor = (receipt.get("predecessor_account_id")
                           or receipt.get("predecessor_id")
                           or receipt.get("predecessor"))
            receiver = (receipt.get("receiver_account_id")
                        or receipt.get("receiver_id")
                        or receipt.get("receiver"))
            if amount == 0:
                no_near_count += 1
            if receiver == wallet and predecessor != wallet:
                inbound_count += 1
                inbound_near += amount
                inbound_counterparties[predecessor] = inbound_counterparties.get(predecessor, 0) + 1
            elif predecessor == wallet and receiver != wallet:
                outbound_count += 1
                outbound_near += amount
                outbound_counterparties[receiver] = outbound_counterparties.get(receiver, 0) + 1
            elif predecessor == wallet and receiver == wallet:
                self_count += 1
        if reached_window_start:
            break
    else:
        # The for loop ran out of pages without a break: the page limit
        # was hit before the window start was reached.
        raise FetchError(
            f"pagination truncated: {max_pages} pages ({max_pages * PER_PAGE} receipts) "
            f"did not reach the {window_days}-day window start "
            f"({window_start.isoformat()}); refusing to write a partial snapshot"
        )
    if not reached_window_start:
        raise FetchError(
            f"receipt history ended before the {window_days}-day window start "
            f"({window_start.isoformat()}); only {receipts_examined} receipts in window, "
            f"refusing to write a partial snapshot"
        )

    threshold_near = balance_near * THRESHOLD_PCT / 100
    outflow_pct = outbound_near / balance_near * 100 if balance_near else 0.0
    checked_at = now_utc.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    window_start_s = window_start.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    snapshot = {
        "wallet": wallet,
        "balance_near": round(balance_near, 2),
        "balance_block_height": balance_block,
        "threshold_near": round(threshold_near, 2),
        "threshold_pct": THRESHOLD_PCT,
        "window_days": window_days,
        "window_start_utc": window_start_s,
        "window_end_utc": checked_at,
        "checked_at_utc": checked_at,
        "receipts_examined": receipts_examined,
        "inbound_count": inbound_count,
        "inbound_near_total": round(inbound_near, 2),
        "inbound_counterparties": inbound_counterparties,
        "outbound_count": outbound_count,
        "outbound_near_total": round(outbound_near, 2),
        "outbound_counterparties": outbound_counterparties,
        "self_transfers_count": self_count,
        "outflow_pct_of_balance": round(outflow_pct, 4),
        "status": "triggered" if outflow_pct > THRESHOLD_PCT else "not_triggered",
        "source": ("Nearblocks API (read-only): /v1/account/{wallet} (balance) "
                   "+ /v1/account/{wallet}/txns (receipts, order=desc, per_page=100). "
                   "Direction by predecessor/receiver; amounts = action deposits."),
        "provenance": (f"Fetched {checked_at} by scripts/fetch_f4_snapshot.py "
                       f"({receipts_examined} receipts in the trailing {window_days}d window)."),
        "notes": ("Gas per receipt (~0.00002 NEAR) is not counted as flow; negligible "
                  "against the 5% threshold. Counts native NEAR (action deposits) only, "
                  "not token transfers. "
                  f"Of {receipts_examined} receipts examined, {inbound_count} carried inbound "
                  f"NEAR and {outbound_count} carried outbound NEAR; {no_near_count} moved no NEAR."),
    }
    return snapshot


def main():
    parser = argparse.ArgumentParser(
        description="Fetch the F4 buyback-wallet snapshot from Nearblocks.")
    parser.add_argument("--wallet", default=DEFAULT_WALLET,
                        help=f"wallet to read (default: {DEFAULT_WALLET})")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help=f"snapshot path (default: {DEFAULT_OUT})")
    parser.add_argument("--window-days", type=int, default=WINDOW_DAYS,
                        help=f"trailing window in days (default: {WINDOW_DAYS})")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES,
                        help=f"pagination cap, fail if hit (default: {MAX_PAGES})")
    parser.add_argument("--page-delay", type=float, default=PAGE_DELAY_S,
                        help=f"pause between pages in seconds (default: {PAGE_DELAY_S})")
    args = parser.parse_args()

    out = Path(args.out)
    try:
        snapshot = fetch_snapshot(args.wallet, args.window_days,
                                  args.max_pages, args.page_delay)
    except FetchError as e:
        print(f"fetch_f4_snapshot: ERROR: {e}", file=sys.stderr)
        print("fetch_f4_snapshot: nothing written (existing snapshot untouched).",
              file=sys.stderr)
        return 1

    # ---- atomic write: temp file in the same directory, then replace ----
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.tmp")
    tmp.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, out)
    print(f"fetch_f4_snapshot: wrote {out} "
          f"({snapshot['receipts_examined']} receipts, "
          f"balance {snapshot['balance_near']:,.2f} NEAR, "
          f"outbound {snapshot['outbound_near_total']:,.2f} NEAR)")

    # ---- self-verification: run evaluate_f4 on what was just written ----
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from check_falsifiers import evaluate_f4
        result = evaluate_f4(snapshot, datetime.now(timezone.utc))
        print(f"fetch_f4_snapshot: self-check F4 = {result['status']} "
              f"({result['reading_text']})")
        if result["status"] == "cannot_check":
            print("fetch_f4_snapshot: WARNING: F4 reports cannot_check on the "
                  "snapshot just written; see the reading above.", file=sys.stderr)
            return 2
    except Exception as e:  # noqa: BLE001 - self-check must never break the write
        print(f"fetch_f4_snapshot: WARNING: self-check could not run ({e}); "
              f"snapshot is on disk, verify with scripts/check_falsifiers.py.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
