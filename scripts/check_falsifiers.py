#!/usr/bin/env python3
"""Check the six thesis falsifiers (F1-F6, Chapter 6 / Table 5) and write
data/falsifiers.json.

Each falsifier is evaluated from the shipped data/ CSVs, the buyback-wallet
snapshot (data/buyback_wallet_30d.json, Nearblocks — see its provenance
field; no live call is made here), plus the monthly net revenue series
scraped live from revenue.near.org (same keyless scrape the figure scripts
use). Nothing here needs credentials, a JWT, or BigQuery.

Statuses:
  not_triggered      - measured, threshold not breached
  triggered          - measured, threshold breached (downgrades the thesis)
  not_yet_decidable  - a deadline check whose date has not arrived yet
  cannot_check       - the data needed to evaluate it does not exist in-repo
                       (and, for F5, has no public endpoint at all); also F4
                       when its snapshot is invalid or older than
                       F4_MAX_SNAPSHOT_AGE_DAYS (a stale snapshot must not
                       keep reporting "not triggered")

A triggered falsifier is a FINDING, not a build error: this script always
exits 0 when it produces a report. It exits 1 only on an internal error
(e.g. a data file it must read is missing entirely), so rebuild.sh can warn
and continue.

Definitions (PDF §5, Table 5):
  F1  Intents volume < $75M/day x 30d.
  F2  Take < 3 bps OR capture < 15% x 60d. Take is NET revenue / volume
      (PDF §4: "take rate (net revenue divided by volume)"), NOT gross
      fees / volume. Net revenue is monthly, so the 60d net figure is
      pro-rated by overlapping days in each month (documented approximation).
  F3  HSP-029 not live by mid-2027 (deadline 30 Jun 2027).
  F4  Buyback-wallet outflow > 5% / 30d.
  F5  ETF outflows for 4+ weeks. The PDF itself states this reading is NOT
      re-runnable ("All readings re-runnable except F5").
  F6  Net-revenue run-rate not doubling in 4 quarters. Run-rate = sum of net
      revenue over the last 3 COMPLETE calendar months, annualised (x4);
      baseline = the same 3 months 12 months earlier.
"""

import calendar
import csv
import datetime
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "falsifiers.json"
MANIFEST = DATA / "manifest.json"

F3_DEADLINE = datetime.date(2027, 6, 30)


def read_series(path, value_col):
    """Read a date,value CSV -> sorted [(date, float)] or None if missing."""
    if not path.exists():
        return None
    rows = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rows.append((datetime.date.fromisoformat(row["date"]),
                         float(row[value_col])))
    rows.sort()
    return rows


def _revenue_rsc():
    """Fetch revenue.near.org once; return the decoded RSC payload text,
    or None when unreachable/unparseable. The payload carries both the
    monthly net-revenue series and the daily cumulative revenue series,
    so one fetch feeds both parsers below."""
    try:
        html = requests.get("https://revenue.near.org",
                            headers={"User-Agent": "near-thesis/1.0"},
                            timeout=30).text
        chunks = re.findall(
            r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', html)
        rsc = "".join(chunks).encode().decode("unicode_escape",
                                              errors="replace")
        return rsc or None
    except Exception as exc:  # noqa: BLE001 - live scrape is best-effort
        print(f"falsifiers: revenue.near.org unreachable ({exc})",
              file=sys.stderr)
        return None


def revenue_monthly(rsc):
    """Monthly net protocol revenue (USD) from the RSC payload.
    Returns {(year, month): net_usd} or None when unparseable. Same
    technique as scripts/generate_chapter3_figures.py."""
    rows = re.findall(
        r'\{"date":"([^"]+)","value":([\d.]+),"cumulative":([\d.]+)\}',
        rsc)
    if not rows:
        return None
    mon = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
    out = {}
    for label, value, _cum in rows:
        m, y = label.split()
        out[(2000 + int(y.strip("'")), mon[m])] = float(value)
    return out


def revenue_daily(rsc):
    """Daily cumulative revenue (NEAR) from the RSC payload's
    absoluteRevEmissions array. Returns {date: cumulative_revenue_near}
    or None when unparseable. Same series
    scripts/generate_chapter4_figures.py uses for Figure 6."""
    m = re.search(r'"absoluteRevEmissions":\[(.*?)\]', rsc, re.S)
    if not m:
        return None
    try:
        arr = json.loads("[" + re.sub(r',\{"date[^\}]*$', "",
                                      m.group(1)) + "]")
    except Exception:
        return None
    return {datetime.date.fromisoformat(e["date"]): float(e["revenueNear"])
            for e in arr}


def net_in_window(net_m, start, end, daily=None, today=None):
    """Net revenue over [start, end], pro-rating monthly figures by the
    overlapping days in each month. Returns (value, months_used).
    The current (partial) month's dashboard value is month-to-date, NOT a
    full-month figure: pro-rating it by overlap/days-in-month undercounts
    it (Nov 2026 was counted at 10/30 of an MTD value; the true 10-day
    figure is ~3x that — verified 12 Nov 2026 against the daily series).
    For the partial month, use the daily cumulative revenue series when
    available: the overlap's share is its NEAR delta over the MTD NEAR
    delta. Without the daily series, fall back to overlap /
    days-elapsed-in-month."""
    total = 0.0
    used = []
    d = datetime.date(start.year, start.month, 1)
    while d <= end:
        dim = calendar.monthrange(d.year, d.month)[1]
        m_start = datetime.date(d.year, d.month, 1)
        m_end = datetime.date(d.year, d.month, dim)
        lo, hi = max(m_start, start), min(m_end, end)
        overlap = (hi - lo).days + 1
        if overlap > 0 and (d.year, d.month) in net_m:
            key = (d.year, d.month)
            partial = (today is not None
                       and (d.year, d.month) == (today.year, today.month))
            if partial and daily:
                month_days = [dt for dt in daily
                              if (dt.year, dt.month) == key]
                if month_days:
                    mtd_end = max(month_days)
                    prev_end = m_start - datetime.timedelta(days=1)
                    mtd_near = daily[mtd_end] - daily.get(prev_end, 0.0)
                    hi_near = daily.get(hi, daily[mtd_end])
                    lo_near = daily.get(lo - datetime.timedelta(days=1),
                                        0.0)
                    overlap_near = hi_near - lo_near
                    if mtd_near > 0 and overlap_near >= 0:
                        total += net_m[key] * overlap_near / mtd_near
                        used.append(f"{d.strftime('%b %y')} ({overlap}d "
                                    "of MTD, daily series)")
                    else:
                        total += net_m[key] * overlap / today.day
                        used.append(f"{d.strftime('%b %y')} "
                                    f"({overlap}/{today.day}d elapsed)")
                else:
                    total += net_m[key] * overlap / today.day
                    used.append(f"{d.strftime('%b %y')} "
                                f"({overlap}/{today.day}d elapsed)")
            elif partial and today is not None:
                total += net_m[key] * overlap / today.day
                used.append(f"{d.strftime('%b %y')} "
                            f"({overlap}/{today.day}d elapsed)")
            else:
                total += net_m[key] * overlap / dim
                used.append(f"{d.strftime('%b %y')} ({overlap}/{dim}d)")
        d = m_end + datetime.timedelta(days=1)
    return total, used


def usd(x):
    if x >= 1e9:
        return f"${x / 1e9:.2f}B"
    if x >= 1e6:
        return f"${x / 1e6:.2f}M"
    return f"${x:,.0f}"


F4_MAX_SNAPSHOT_AGE_DAYS = 30  # = the F4 window: an older snapshot no longer overlaps the current 30d


def _f4_unavailable(reading_text, evidence, source):
    return {
        "id": "F4",
        "name": "Buyback-wallet outflow > 5% / 30d",
        "threshold": "outflow > 5% of balance in 30d",
        "reading": None,
        "reading_text": reading_text,
        "status": "cannot_check",
        "evidence": evidence,
        "source": source,
    }


def evaluate_f4(snap, now_utc):
    """F4 from the buyback-wallet snapshot. Returns cannot_check (never a
    silent not_triggered) when the snapshot is missing, malformed, has a
    zero/invalid balance, or is older than F4_MAX_SNAPSHOT_AGE_DAYS."""
    if not (isinstance(snap, dict) and "outbound_near_total" in snap
            and "balance_near" in snap):
        return _f4_unavailable(
            "cannot compute: no buyback-wallet snapshot",
            "No data/buyback_wallet_30d.json in this repo. Evaluating the "
            "falsifier needs the buyback wallet address + a 30-day flow "
            "history (Nearblocks).",
            "none (snapshot missing)")
    try:
        out_near = float(snap["outbound_near_total"])
        bal = float(snap["balance_near"])
    except (TypeError, ValueError):
        return _f4_unavailable(
            "cannot compute: snapshot values are not numeric",
            "outbound_near_total / balance_near in data/buyback_wallet_30d.json "
            "must be numbers.",
            snap.get("source", "data/buyback_wallet_30d.json"))
    if not bal > 0:
        return _f4_unavailable(
            "cannot compute: snapshot balance is zero or invalid",
            "balance_near must be > 0 to express the outflow as a share of "
            "the balance.",
            snap.get("source", "data/buyback_wallet_30d.json"))
    checked = snap.get("checked_at_utc")
    try:
        ts = datetime.datetime.fromisoformat(str(checked))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return _f4_unavailable(
            "cannot compute: snapshot has no valid checked_at_utc",
            "checked_at_utc must be an ISO-8601 timestamp so the snapshot "
            "age can be verified.",
            snap.get("source", "data/buyback_wallet_30d.json"))
    age_days = (now_utc - ts).total_seconds() / 86400
    if age_days > F4_MAX_SNAPSHOT_AGE_DAYS:
        return _f4_unavailable(
            f"snapshot stale: checked {str(checked)[:10]} "
            f"({age_days:.0f} days old, limit {F4_MAX_SNAPSHOT_AGE_DAYS})",
            "F4 is a trailing-30-day flow reading; a snapshot older than "
            f"{F4_MAX_SNAPSHOT_AGE_DAYS} days is not evidence about the "
            "current window. Refresh data/buyback_wallet_30d.json "
            "(see data/README.md).",
            snap.get("source", "data/buyback_wallet_30d.json"))

    thr = float(snap.get("threshold_near", bal * 0.05))
    pct = out_near / bal * 100
    in_n = snap.get("inbound_count", "?")
    in_near = snap.get("inbound_near_total", "?")
    in_near_txt = (f"{in_near:,.2f}"
                   if isinstance(in_near, (int, float)) else str(in_near))
    in_from = ", ".join(snap.get("inbound_counterparties", {}).keys()) or "?"
    recv_n = snap.get("receipts_examined", "?")
    return {
        "id": "F4",
        "name": "Buyback-wallet outflow > 5% / 30d",
        "threshold": "outflow > 5% of balance in 30d",
        "reading": {"outflow_near": out_near, "balance_near": bal,
                    "outflow_pct": pct, "threshold_near": thr,
                    "receipts_examined": recv_n,
                    "inbound_near_total": in_near},
        "reading_text": f"outflow {out_near:,.2f} NEAR "
                        f"({pct:.4f}% of {bal:,.2f} NEAR balance) over "
                        f"{str(snap.get('window_start_utc', '?'))[:10]}.."
                        f"{str(snap.get('window_end_utc', '?'))[:10]}",
        "status": "triggered" if pct > 5 else "not_triggered",
        "evidence": f"{recv_n} receipts examined ({in_n} inbound, "
                    f"{in_near_txt} NEAR from {in_from}; "
                    f"{snap.get('outbound_count', '?')} outbound). "
                    f"Snapshot checked {checked}. Counts native NEAR "
                    f"(action deposits) only, not token transfers.",
        "source": snap.get("source", "data/buyback_wallet_30d.json"),
    }


def main():
    today = datetime.date.today()
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    volume = read_series(DATA / "intents_volume_daily.csv", "volume_usd")
    fees = read_series(DATA / "intents_fees_daily.csv", "fees_usd")
    if volume is None or fees is None:
        print("falsifiers: ERROR - intents_volume_daily.csv and/or "
              "intents_fees_daily.csv missing from data/",
              file=sys.stderr)
        return 1
    rsc = _revenue_rsc()
    net_m = revenue_monthly(rsc) if rsc else None
    daily = revenue_daily(rsc) if rsc else None
    if net_m is None and OUT.exists():
        # Offline run must not silently degrade the committed file: F2 and
        # F6 would flip from computed to cannot_check. Keep the previous
        # readings (their generated_at_utc shows their age) and do not
        # touch the manifest either. A first run with no previous file
        # still writes the honest cannot_check version below.
        prev_age = ""
        try:
            prev = json.loads(OUT.read_text())
            prev_age = f" (generated {prev.get('generated_at_utc', '?')})"
        except Exception:
            pass
        print("falsifiers: revenue.near.org unreachable — keeping previous "
              f"data/falsifiers.json{prev_age}; F2/F6 readings stand.",
              file=sys.stderr)
        return 0
    results = []

    # ---- F1: volume < $75M/day x 30d -------------------------------------
    last30 = volume[-30:]
    avg30 = sum(v for _d, v in last30) / len(last30)
    results.append({
        "id": "F1",
        "name": "Intents volume falls below $75M/day (30d avg)",
        "threshold": "volume_30d_avg < $75,000,000/day",
        "reading": avg30,
        "reading_text": f"{usd(avg30)}/day over "
                        f"{last30[0][0]}..{last30[-1][0]}",
        "status": "triggered" if avg30 < 75_000_000 else "not_triggered",
        "evidence": f"30d mean of data/intents_volume_daily.csv "
                    f"({len(last30)} days).",
        "source": "DefiLlama daily Intents volume (shipped CSV)",
    })

    # ---- F2: take < 3 bps OR capture < 15% x 60d ------------------------
    end = fees[-1][0]
    start = end - datetime.timedelta(days=59)
    fmap = dict(fees)
    vmap = dict(volume)
    days = [d for d in sorted(fmap) if start <= d <= end]
    gross60 = sum(fmap[d] for d in days)
    vol60 = sum(vmap.get(d, 0.0) for d in days)
    if net_m is None:
        results.append({
            "id": "F2",
            "name": "Take < 3 bps or capture < 15% (60d)",
            "threshold": "take < 3 bps OR capture < 15%",
            "reading": None,
            "reading_text": "cannot compute: revenue.near.org unreachable",
            "status": "cannot_check",
            "evidence": "Take is net revenue / volume (PDF §4); net revenue "
                        "comes from revenue.near.org and the scrape failed. "
                        f"Gross fees 60d are {usd(gross60)} (DefiLlama CSV).",
            "source": "revenue.near.org (failed) + DefiLlama daily fees",
        })
    else:
        net60, used = net_in_window(net_m, start, end, daily, today)
        take_bps = net60 / vol60 * 10_000 if vol60 else float("nan")
        capture = net60 / gross60 * 100 if gross60 else float("nan")
        triggered = take_bps < 3 or capture < 15
        results.append({
            "id": "F2",
            "name": "Take < 3 bps or capture < 15% (60d)",
            "threshold": "take < 3 bps OR capture < 15%",
            "reading": {"take_bps": take_bps, "capture_pct": capture,
                        "net_60d_usd": net60, "gross_60d_usd": gross60,
                        "volume_60d_usd": vol60},
            "reading_text": f"take {take_bps:.2f} bps (net), capture "
                            f"{capture:.1f}% over {start}..{end}",
            "status": "triggered" if triggered else "not_triggered",
            "evidence": f"Net 60d {usd(net60)} (monthly net pro-rated: "
                        f"{'; '.join(used)}); gross 60d {usd(gross60)}; "
                        f"volume 60d {usd(vol60)}.",
            "source": "revenue.near.org monthly net + daily revenue series "
                      "+ DefiLlama daily fees/volume (shipped CSVs)",
        })

    # ---- F3: HSP-029 not live by mid-2027 --------------------------------
    if today < F3_DEADLINE:
        results.append({
            "id": "F3",
            "name": "HSP-029 not live by mid-2027",
            "threshold": "HSP-029 not live on 30 Jun 2027",
            "reading": None,
            "reading_text": f"deadline {F3_DEADLINE} not reached "
                            f"(today {today})",
            "status": "not_yet_decidable",
            "evidence": "HSP-029 passed 2 Nov 2026 (99.96%); 2.5% -> 1.6% "
                        "phased over 24 months; not yet live (needs Security "
                        "Council ratification + ~90-day grace + validator "
                        "adoption, earliest ~Feb 2027).",
            "source": "PDF §3.3 / HSP-029 vote record",
        })
    else:
        results.append({
            "id": "F3",
            "name": "HSP-029 not live by mid-2027",
            "threshold": "HSP-029 not live on 30 Jun 2027",
            "reading": None,
            "reading_text": f"deadline {F3_DEADLINE} passed",
            "status": "cannot_check",
            "evidence": "Deadline passed, but no liveness source is wired "
                        "into this repo (no HSP-029 status endpoint).",
            "source": "none wired",
        })

    # ---- F4: buyback outflow > 5% / 30d ----------------------------------
    # Snapshot-based: data/buyback_wallet_30d.json (Nearblocks, read-only
    # fetch; the fetch itself is NOT part of the rebuild). No live API call
    # here, so rebuild.sh stays deterministic offline. Without a valid
    # snapshot, fall back to cannot_check.
    try:
        snap = json.loads((DATA / "buyback_wallet_30d.json").read_text())
    except Exception:
        snap = None
    results.append(evaluate_f4(snap, now_utc))

    # ---- F5: ETF outflows 4+ weeks ---------------------------------------
    results.append({
        "id": "F5",
        "name": "ETF outflows for 4+ weeks",
        "threshold": "net ETF outflows in 4 consecutive weeks",
        "reading": None,
        "reading_text": "cannot compute: no public ETF-flow endpoint",
        "status": "cannot_check",
        "evidence": "No ETF flow data source is wired into this repo. The "
                    "PDF itself states this reading is NOT re-runnable "
                    "(\"All readings re-runnable except F5\", Table 5).",
        "source": "none (PDF Table 5: not re-runnable)",
    })

    # ---- F6: net-revenue run-rate not doubling in 4 quarters -------------
    if net_m is None:
        results.append({
            "id": "F6",
            "name": "Net-revenue run-rate not doubling in 4 quarters",
            "threshold": "current run-rate < 2x run-rate 4 quarters ago",
            "reading": None,
            "reading_text": "cannot compute: revenue.near.org unreachable",
            "status": "cannot_check",
            "evidence": "Run-rate needs the monthly net revenue series.",
            "source": "revenue.near.org (failed)",
        })
    else:
        months = sorted(net_m)
        # Last complete calendar month (exclude the current partial month).
        last_full = (today.year, today.month - 1) if today.month > 1 \
            else (today.year - 1, 12)

        def back_n(y, m, n):
            out = []
            for _ in range(n):
                out.append((y, m))
                m -= 1
                if m == 0:
                    m, y = 12, y - 1
            return out
        cur_q = back_n(*last_full, 3)
        base_q = back_n(last_full[0] - 1, last_full[1], 3)
        if all(k in net_m for k in cur_q) and all(k in net_m for k in base_q):
            cur = sum(net_m[k] for k in cur_q) * 4
            base = sum(net_m[k] for k in base_q) * 4
            ratio = cur / base if base else float("nan")
            results.append({
                "id": "F6",
                "name": "Net-revenue run-rate not doubling in 4 quarters",
                "threshold": "current run-rate < 2x run-rate 4 quarters ago",
                "reading": {"run_rate_now_usd": cur,
                            "run_rate_baseline_usd": base, "ratio": ratio},
                "reading_text": f"run-rate {usd(cur)}/yr vs baseline "
                                f"{usd(base)}/yr = {ratio:.1f}x",
                "status": "triggered" if ratio < 2 else "not_triggered",
                "evidence": f"Last 3 complete months "
                            f"{cur_q[-1][0]}-{cur_q[-1][1]:02d}.."
                            f"{cur_q[0][0]}-{cur_q[0][1]:02d} net "
                            f"{usd(sum(net_m[k] for k in cur_q))} (x4 "
                            f"annualised); baseline "
                            f"{base_q[-1][0]}-{base_q[-1][1]:02d}.."
                            f"{base_q[0][0]}-{base_q[0][1]:02d} net "
                            f"{usd(sum(net_m[k] for k in base_q))}.",
                "source": "revenue.near.org monthly net revenue",
            })
        else:
            results.append({
                "id": "F6",
                "name": "Net-revenue run-rate not doubling in 4 quarters",
                "threshold": "current run-rate < 2x run-rate 4 quarters ago",
                "reading": None,
                "reading_text": "cannot compute: baseline quarter not in "
                                "the monthly series",
                "status": "not_yet_decidable",
                "evidence": f"Monthly net series covers "
                            f"{months[0]}..{months[-1]}; the baseline "
                            f"quarter is not fully present.",
                "source": "revenue.near.org monthly net revenue",
            })

    triggered = [r["id"] for r in results if r["status"] == "triggered"]
    report = {
        "generated_at_utc": now_utc.isoformat(),
        "data_as_of": fees[-1][0].isoformat(),
        "falsifiers": results,
        "triggered": triggered,
        "summary": (
            f"{len(triggered)} of 6 falsifiers triggered: "
            f"{', '.join(triggered) if triggered else 'none'}. "
            f"{sum(1 for r in results if r['status'] == 'not_triggered')} "
            f"not triggered, "
            f"{sum(1 for r in results if r['status'] == 'not_yet_decidable')} "
            f"not yet decidable, "
            f"{sum(1 for r in results if r['status'] == 'cannot_check')} "
            f"cannot check."
        ),
    }
    OUT.write_text(json.dumps(report, indent=1))
    try:
        manifest = json.loads(MANIFEST.read_text())
        manifest["falsifiers.json"] = {
            "note": "Falsifier check (F1-F6) from shipped CSVs + "
                    "revenue.near.org live scrape.",
            "pulled_at_utc": now_utc.isoformat(),
            "rows": 6,
            "source": "scripts/check_falsifiers.py",
            "url": "scripts/check_falsifiers.py",
        }
        MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True))
    except Exception as exc:  # noqa: BLE001 - manifest is bookkeeping only
        print(f"falsifiers: manifest update failed ({exc})", file=sys.stderr)

    print("Falsifier check (F1-F6):")
    for r in results:
        mark = {"triggered": "TRIGGERED", "not_triggered": "ok",
                "not_yet_decidable": "not yet decidable",
                "cannot_check": "cannot check"}[r["status"]]
        print(f"  {r['id']}  {mark:>17}  {r['reading_text']}")
    print(f"  {report['summary']}")
    print(f"falsifiers: wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
