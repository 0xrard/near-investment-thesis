#!/usr/bin/env bash
# ONE command: fetch -> model -> figures -> build dashboard.
#   ./rebuild.sh              full rebuild (needs .env credentials for BigQuery + Intents)
#   ./rebuild.sh --model-only model + figures + dashboard from the shipped CSVs (no credentials)
# Figures (scripts/generate_chapter*_figures.py) fetch live data (keyless, no
# credentials) and regenerate figures/ + data/captions.json + data/stats.json.
# They run after the model so the Chapter 4 stats cross-check reads fresh
# model outputs. A figure failure never breaks the build: the previous
# figures/captions/stats are kept and the rebuild continues (both modes).
# BigQuery freshness (queries/00-freshness.sql, MAX(block_date)) runs inside
# fetch.py's BigQuery leg, first, and lands in data/bq_00_freshness.csv,
# which build_dashboard.py reads for its freshness display. With no GCP
# credentials the fetch fails clearly (see below) — never silently fresh.
set -euo pipefail
cd "$(dirname "$0")"

usage() {
  echo "Usage: ./rebuild.sh [--model-only]"
  echo "  (no args)    full rebuild: fetch -> model -> figures -> build dashboard"
  echo "  --model-only model + figures + dashboard from the shipped CSVs (no credentials)"
}

MODE="full"
for arg in "$@"; do
  case "$arg" in
    --model-only) MODE="model-only" ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $arg" >&2; usage; exit 2 ;;
  esac
done

if [ "$MODE" = "full" ]; then
  echo "== [1/4] Fetching data (needs .env credentials for BigQuery + Intents) =="
  if ! python3 scripts/fetch.py; then
    echo ""
    echo "Fetch failed. Either fix the credentials (see the message above),"
    echo "or rebuild from the shipped CSVs with no credentials:"
    echo "  ./rebuild.sh --model-only"
    exit 1
  fi
else
  echo "== [1/4] Skipping fetch (--model-only: no credentials needed) =="
fi

echo "== [2/4] Running model =="
python3 model/model.py

echo "== [3/4] Generating figures (captions + stats) =="
for script in generate_chapter3_figures.py generate_chapter4_figures.py generate_chapter5_figures.py; do
  if ! python3 "scripts/$script"; then
    echo "WARNING: $script failed; keeping previous figures/captions/stats." >&2
  fi
done

echo "== [4/4] Building dashboard =="
python3 scripts/build_dashboard.py

echo ""
echo "Done: dashboard/index.html"
