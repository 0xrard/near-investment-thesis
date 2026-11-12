#!/usr/bin/env python3
"""Fetch primary data -> data/.

Sources (all free except the two credential-gated ones):
  - CoinGecko Keyless API (no key): NEAR/SOL/ETH price history + NEAR market snapshot.
  - DefiLlama API (no key): Intents volume + fees, chain DEX volumes.
  - NEAR Intents Explorer API (JWT-gated): canonical Intents volume series.
  - BigQuery (GCP project + credentials): queries/*.sql -> data/bq_*.csv.

Every fetched file is recorded in data/manifest.json with source, URL and
pull date (UTC) — the audit trail for every number on the dashboard.

Exit codes: 0 ok; 1 missing credentials/config (clear message); 2 fetch error.
Use --allow-partial to skip credential-gated sources instead of failing.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MANIFEST = DATA / "manifest.json"


class MissingCredential(Exception):
    """A credential or config value needed for a fetch is absent."""


class FetchError(Exception):
    """A fetch failed (HTTP error, bad response, ...)."""


# ---------------------------------------------------------------- .env ---

def load_dotenv(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if not value:
            # Empty means unset: never carry an empty string into env.
            # (An empty GOOGLE_APPLICATION_CREDENTIALS would make Google's
            # auth library fail on a file named "" instead of ADC fallback.)
            continue
        env[key.strip()] = value
    return env


# ---------------------------------------------------------------- http ---

def http_get_json(url: str, headers: dict | None = None, timeout: int = 60):
    req = urllib.request.Request(
        url, headers={"User-Agent": "near-thesis-fetch/1.0", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read()[:300].decode("utf-8", "replace")
        raise FetchError(f"HTTP {e.code} for {url}: {body}")
    except urllib.error.URLError as e:
        raise FetchError(f"network error for {url}: {e.reason}")


def _to_date(ts) -> str:
    """Unix timestamp (seconds or milliseconds) -> YYYY-MM-DD (UTC)."""
    ts = float(ts)
    if ts > 1e12:
        ts /= 1000.0
    return datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()


def extract_daily_chart(obj, value_keys=("volume", "fees", "value")):
    """Best-effort extraction of a daily [[timestamp, value], ...] series.

    Tries common shapes: {"totalDataChart": [...]}, {"chart": [...]},
    {"dailyVolume": [...]}, a bare list, or {"data": <one of the above>}.
    Returns a list of {"date": ..., "value": ...} sorted by date, or None.
    """
    if isinstance(obj, dict) and "data" in obj:
        obj = obj["data"]
    chart = None
    if isinstance(obj, dict):
        for key in ("totalDataChart", "chart", "dailyVolume", "dailyFees"):
            if isinstance(obj.get(key), list):
                chart = obj[key]
                break
    elif isinstance(obj, list):
        chart = obj
    if not chart:
        return None
    rows = []
    for item in chart:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                rows.append({"date": _to_date(item[0]), "value": float(item[1])})
            elif isinstance(item, dict):
                ts = item.get("date") or item.get("timestamp") or item.get("time")
                val = None
                for k in value_keys:
                    if k in item:
                        val = item[k]
                        break
                if ts is not None and val is not None:
                    date = ts if isinstance(ts, str) and len(ts) == 10 else _to_date(ts)
                    rows.append({"date": date, "value": float(val)})
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda r: r["date"])
    return rows or None


# ------------------------------------------------------------ writers ---

def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})
    return len(rows)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True))


def load_manifest() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def record_manifest(manifest: dict, filename: str, source: str, url: str, rows: int | None) -> None:
    manifest[filename] = {
        "source": source,
        "url": url,
        "pulled_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": rows,
    }


# ---------------------------------------------------------- CoinGecko ---

def fetch_coingecko(env: dict, manifest: dict) -> None:
    """NEAR/SOL/ETH price history + NEAR market snapshot. Keyless; ~5 calls/min."""
    print("[coingecko] fetching price history (keyless, one call per coin)...")
    api_key = env.get("COINGECKO_API_KEY", "")
    headers = {"x-cg-demo-api-key": api_key} if api_key else {}
    for coin in ("near", "solana", "ethereum"):
        url = (
            f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
            f"?vs_currency=usd&days=365&interval=daily"
        )
        data = http_get_json(url, headers)
        prices = {int(ts // 1000): p for ts, p in data.get("prices", [])}
        vols = {int(ts // 1000): v for ts, v in data.get("total_volumes", [])}
        # CoinGecko's daily interval appends a live "now" point after the last
        # 00:00 UTC point, so the final calendar date can appear twice. Keep
        # one row per date: the most recent timestamp wins.
        by_date = {}
        for ts in sorted(prices):
            day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
            by_date[day] = {
                "date": day,
                "price_usd": prices[ts],
                "volume_usd": vols.get(ts, ""),
            }
        rows = [by_date[d] for d in sorted(by_date)]
        n = write_csv(DATA / f"{coin}_price_daily.csv", rows, ["date", "price_usd", "volume_usd"])
        record_manifest(manifest, f"{coin}_price_daily.csv", "CoinGecko market_chart", url, n)
        print(f"[coingecko] {coin}: {n} days -> {coin}_price_daily.csv")
        time.sleep(15)  # keyless rate limit

    url = (
        "https://api.coingecko.com/api/v3/coins/near"
        "?localization=false&tickers=false&community_data=false&developer_data=false"
    )
    snap = http_get_json(url, headers)
    md = snap.get("market_data", {})
    snapshot = {
        "price_usd": md.get("current_price", {}).get("usd"),
        "market_cap_usd": md.get("market_cap", {}).get("usd"),
        "total_supply": md.get("total_supply"),
        "circulating_supply": md.get("circulating_supply"),
        "last_updated": snap.get("last_updated"),
        "source": "CoinGecko /coins/near",
    }
    write_json(DATA / "near_market.json", snapshot)
    record_manifest(manifest, "near_market.json", "CoinGecko /coins/near", url, None)
    if snapshot["market_cap_usd"]:
        print(f"[coingecko] near market snapshot -> near_market.json "
              f"(market cap ${snapshot['market_cap_usd']:,})")
    else:
        print("[coingecko] near market snapshot -> near_market.json")


# ---------------------------------------------------------- DefiLlama ---

def fetch_defillama(env: dict, manifest: dict) -> None:
    """Intents volume + fees. No key needed."""
    slug = env.get("DEFILLAMA_INTENTS_SLUG", "near-intents")
    print(f"[defillama] slug={slug} ...")

    url = f"https://api.llama.fi/summary/dexs/{slug}"
    try:
        dexs = http_get_json(url)
    except FetchError as e:
        raise FetchError(
            f"{e}\n  -> Check DEFILLAMA_INTENTS_SLUG in .env "
            f"(try https://api.llama.fi/summary/dexs/<slug> in a browser)."
        )
    write_json(DATA / "defillama_intents_dexs.json", dexs)
    record_manifest(manifest, "defillama_intents_dexs.json", "DefiLlama /summary/dexs", url, None)
    rows = extract_daily_chart(dexs)
    if rows:
        n = write_csv(
            DATA / "intents_volume_daily.csv",
            [{"date": r["date"], "volume_usd": r["value"]} for r in rows],
            ["date", "volume_usd"],
        )
        record_manifest(manifest, "intents_volume_daily.csv", "DefiLlama /summary/dexs", url, n)
        print(f"[defillama] intents volume: {n} days, "
              f"totalAllTime=${dexs.get('totalAllTime', 0):,}")
    else:
        print("[defillama] WARNING: could not parse a daily volume series from /summary/dexs")

    url = f"https://api.llama.fi/summary/fees/{slug}"
    fees = http_get_json(url)
    write_json(DATA / "defillama_intents_fees.json", fees)
    record_manifest(manifest, "defillama_intents_fees.json", "DefiLlama /summary/fees", url, None)
    rows = extract_daily_chart(fees)
    if rows:
        n = write_csv(
            DATA / "intents_fees_daily.csv",
            [{"date": r["date"], "fees_usd": r["value"]} for r in rows],
            ["date", "fees_usd"],
        )
        record_manifest(manifest, "intents_fees_daily.csv", "DefiLlama /summary/fees", url, n)
        print(f"[defillama] intents fees: {n} days, total30d=${fees.get('total30d', 0):,}")
    else:
        print("[defillama] WARNING: could not parse a daily fees series from /summary/fees")

    # NOTE: the per-chain /overview/dexs leg (defillama_chain_<chain>.json
    # and chain_dex_volume_<chain>.csv) was removed 2026-11-12: nothing in
    # the repo reads those files, so a FULL fetch no longer re-creates them.


# ---------------------------------------------- NEAR Intents Explorer ---

def fetch_intents(env: dict, manifest: dict) -> None:
    """Canonical Intents volume series. JWT-gated — fails clearly if unset."""
    jwt = env.get("INTENTS_EXPLORER_JWT", "")
    base = env.get("INTENTS_EXPLORER_API_URL", "").rstrip("/")
    path = env.get("INTENTS_EXPLORER_VOLUME_PATH", "")
    if not jwt:
        raise MissingCredential(
            "INTENTS_EXPLORER_JWT is not set in .env.\n"
            "  -> Get a JWT from the Intents partner dashboard, put it in .env,\n"
            "     or run with --allow-partial to skip the Intents leg."
        )
    if not base:
        raise MissingCredential(
            "INTENTS_EXPLORER_API_URL is not set in .env.\n"
            "  -> Base URL of the Intents Explorer API, from the partner dashboard/docs."
        )
    if not path:
        raise MissingCredential(
            "INTENTS_EXPLORER_VOLUME_PATH is not set in .env.\n"
            "  -> Endpoint path for the daily volume series (relative to the base URL),\n"
            "     from the API docs. fetch.py will not guess it."
        )
    url = base + path
    print(f"[intents] GET {url} (JWT auth)...")
    data = http_get_json(url, {"Authorization": f"Bearer {jwt}"})
    write_json(DATA / "intents_explorer_raw.json", data)
    record_manifest(manifest, "intents_explorer_raw.json", "Intents Explorer API", url, None)
    rows = extract_daily_chart(data)
    if rows:
        n = write_csv(
            DATA / "intents_volume_api_daily.csv",
            [{"date": r["date"], "volume_usd": r["value"]} for r in rows],
            ["date", "volume_usd"],
        )
        record_manifest(manifest, "intents_volume_api_daily.csv", "Intents Explorer API", url, n)
        print(f"[intents] volume series: {n} days -> intents_volume_api_daily.csv")
    else:
        print("[intents] WARNING: response saved to intents_explorer_raw.json but no "
              "daily series could be parsed from it — check the response shape.")


# ------------------------------------------------------------- BigQuery ---

def fetch_bigquery(env: dict, manifest: dict) -> None:
    """Run queries/*.sql -> data/bq_*.csv. Needs GCP project + credentials."""
    try:
        from google.cloud import bigquery
    except ImportError:
        raise MissingCredential(
            "google-cloud-bigquery is not installed.\n"
            "  -> pip install -r requirements.txt\n"
            "     or run with --allow-partial to skip the BigQuery leg."
        )
    project = env.get("GCP_PROJECT_ID", "")
    if not project:
        raise MissingCredential(
            "GCP_PROJECT_ID is not set in .env.\n"
            "  -> Create a GCP project with the BigQuery API enabled and put its ID in .env.\n"
            "     Credentials: GOOGLE_APPLICATION_CREDENTIALS (service-account JSON) or\n"
            "     `gcloud auth application-default login`."
        )
    print(f"[bigquery] project={project} ...")
    try:
        client = bigquery.Client(project=project, location="US")
    except Exception as exc:  # noqa: BLE001 - credential discovery fails many ways
        raise MissingCredential(
            "BigQuery client could not authenticate.\n"
            f"  -> Underlying error: {exc}\n"
            "     Set GOOGLE_APPLICATION_CREDENTIALS to a service-account JSON key,\n"
            "     or run `gcloud auth application-default login`,\n"
            "     or run with --allow-partial to skip the BigQuery leg."
        ) from exc
    # Explicit job list (SQL file -> output CSV). Not a glob: the full g3
    # (365-day join, ~2.4 TB) exceeds the free quota, g4 is a placeholder
    # without verified contract addresses, and g5 duplicates g2. g3/g6 run
    # as the LEAN variants that produced the shipped CSVs. The output names
    # are what model.py and build_dashboard.py read.
    bq_jobs = [
        ("00-freshness.sql", "bq_00_freshness.csv"),
        ("g1-daily-active-accounts.sql", "bq_g1_daily_active_accounts.csv"),
        ("g2-tx-counts.sql", "bq_g2_tx_counts.csv"),
        ("g3-contract-usage-lean.sql", "bq_g3_contract_usage.csv"),
        ("g6-outcomes-lean.sql", "bq_g6_outcomes.csv"),
    ]
    for sql_name, out_name in bq_jobs:
        sql_file = ROOT / "queries" / sql_name
        sql = sql_file.read_text()
        print(f"[bigquery] running {sql_file.name} ...")
        try:
            rows = list(client.query(sql).result())
        except Exception as exc:  # noqa: BLE001 - quota, permission, schema errors
            raise FetchError(f"BigQuery query {sql_file.name} failed: {exc}") from exc
        # Underscore names: model.py and build_dashboard.py read
        # bq_g1_daily_active_accounts.csv etc. (hyphen stems would never match).
        if rows:
            fieldnames = list(rows[0].keys())
            n = write_csv(
                DATA / out_name,
                [dict(r) for r in rows],
                fieldnames,
            )
        else:
            write_csv(DATA / out_name, [], [])
            n = 0
        record_manifest(manifest, out_name, "BigQuery crypto_near_mainnet_us",
                        f"queries/{sql_file.name}", n)
        print(f"[bigquery] {sql_file.name}: {n} rows -> {out_name}")
        if sql_file.name == "00-freshness.sql" and rows:
            max_date = str(rows[0].get("max_block_date"))
            age_days = (datetime.now(timezone.utc).date()
                        - datetime.fromisoformat(max_date).date()).days
            print(f"[bigquery] MAX(block_date) = {max_date} ({age_days} days ago)")
            if age_days > 90:
                print("[bigquery] WARNING: on-chain data is >90 days stale — "
                      "the on-chain leg cannot speak about current usage; "
                      "the Intents API is the fresh leg (see README).")


# ----------------------------------------------------------------- main ---

SOURCES = {
    "coingecko": fetch_coingecko,
    "defillama": fetch_defillama,
    "intents": fetch_intents,
    "bigquery": fetch_bigquery,
}


def main() -> int:
    global DATA, MANIFEST
    parser = argparse.ArgumentParser(description="Fetch primary data -> data/")
    parser.add_argument("--only", default="",
                        help="comma-separated sources: coingecko,defillama,intents,bigquery")
    parser.add_argument("--allow-partial", action="store_true",
                        help="skip credential-gated sources instead of failing")
    parser.add_argument("--env", default=str(ROOT / ".env"),
                        help="path to .env (default: repo-root .env)")
    parser.add_argument("--out-dir", default=str(DATA), help="output dir (default: data/)")
    args = parser.parse_args()

    DATA = Path(args.out_dir)
    MANIFEST = DATA / "manifest.json"
    DATA.mkdir(parents=True, exist_ok=True)

    env = {**load_dotenv(Path(args.env)), **os.environ}
    # .env values must also reach libraries that read the process
    # environment directly: google-cloud-bigquery reads
    # GOOGLE_APPLICATION_CREDENTIALS from os.environ, not from this dict,
    # so a key path set only in .env would otherwise be silently ignored.
    # Real environment values win (setdefault); .env only fills gaps.
    for k, v in env.items():
        os.environ.setdefault(k, v)
    manifest = load_manifest()
    selected = [s.strip() for s in args.only.split(",") if s.strip()] or list(SOURCES)
    unknown = [s for s in selected if s not in SOURCES]
    if unknown:
        print(f"unknown source(s): {', '.join(unknown)} (choose from {', '.join(SOURCES)})")
        return 2

    failed = []
    for name in selected:
        try:
            SOURCES[name](env, manifest)
            write_json(MANIFEST, manifest)  # persist progress after each source
        except MissingCredential as e:
            if args.allow_partial:
                print(f"[{name}] SKIPPED (missing credentials):\n{e}")
                continue
            print(f"\n[{name}] FAILED — missing credentials/config:\n{e}\n")
            print("Fix it, or run with --allow-partial to skip this source, "
                  "or bash rebuild.sh --model-only to rebuild from shipped CSVs.")
            return 1
        except FetchError as e:
            if args.allow_partial:
                print(f"[{name}] SKIPPED (fetch error): {e}")
                failed.append(name)
                continue
            print(f"\n[{name}] FAILED — fetch error:\n{e}\n")
            return 2

    write_json(MANIFEST, manifest)
    print(f"\nDone. Manifest: {MANIFEST}"
          + (f" (skipped: {', '.join(failed)})" if failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
