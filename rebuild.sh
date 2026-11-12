#!/usr/bin/env bash
# ONE command: fetch -> model -> figures -> build dashboard -> check falsifiers.
#   bash rebuild.sh              full rebuild (needs .env credentials for BigQuery + Intents)
#   bash rebuild.sh --model-only model + figures + dashboard + falsifiers from the shipped CSVs (no credentials)
# Figures (scripts/generate_chapter*_figures.py) fetch live data (keyless, no
# credentials) and regenerate figures/ + data/captions.json + data/stats.json.
# They run after the model so the Chapter 4 stats cross-check reads fresh
# model outputs. A figure failure never breaks the build: the previous
# figures/captions/stats are kept and the rebuild continues (both modes).
# The falsifier check (scripts/check_falsifiers.py, step 5) evaluates F1-F6
# from the shipped CSVs + the monthly net revenue scrape; a TRIGGERED
# falsifier is a finding, not a build error, and never breaks the build.
# BigQuery freshness (queries/00-freshness.sql, MAX(block_date)) runs inside
# fetch.py's BigQuery leg, first, and lands in data/bq_00_freshness.csv,
# which build_dashboard.py reads for its freshness display. With no GCP
# credentials the fetch fails clearly (see below) — never silently fresh.
set -euo pipefail
cd "$(dirname "$0")"

# Python 3.10+ is required (README, Level 2). Fail fast with a clear
# message instead of a confusing traceback halfway through the build.
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  echo "rebuild.sh needs Python 3.10+ (found: $(python3 --version 2>&1 || echo 'no python3'))." >&2
  echo "Install Python 3.10+ and re-run." >&2
  exit 1
fi

# The figure scripts and the falsifier checker are required files: if one is
# missing the repo is incomplete, and that must fail loudly — not hide as a
# WARNING that silently leaves stale figures/falsifiers behind.
for f in scripts/generate_chapter3_figures.py scripts/generate_chapter4_figures.py scripts/generate_chapter5_figures.py scripts/check_falsifiers.py; do
  [ -f "$f" ] || { echo "Missing required script: $f — the repo copy is incomplete; re-download it." >&2; exit 1; }
done

usage() {
  echo "Usage: bash rebuild.sh [--model-only]"
  echo "  (no args)    full rebuild: fetch -> model -> figures -> build dashboard -> check falsifiers"
  echo "  --model-only model + figures + dashboard + falsifiers from the shipped CSVs (no credentials)"
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
  echo "== [1/5] Fetching data (needs .env credentials for BigQuery + Intents) =="
  if ! python3 scripts/fetch.py; then
    echo ""
    echo "Fetch failed. Either fix the credentials (see the message above),"
    echo "or rebuild from the shipped CSVs with no credentials:"
    echo "  bash rebuild.sh --model-only"
    exit 1
  fi
else
  echo "== [1/5] Skipping fetch (--model-only: no credentials needed) =="
fi

echo "== [2/5] Running model =="
python3 model/model.py

echo "== [3/5] Generating figures (captions + stats) =="
for script in generate_chapter3_figures.py generate_chapter4_figures.py generate_chapter5_figures.py; do
  if ! python3 "scripts/$script"; then
    echo "WARNING: $script failed; keeping previous figures/captions/stats." >&2
  fi
done

echo "== [4/5] Building dashboard =="
python3 scripts/build_dashboard.py

echo "== [5/5] Checking falsifiers (F1-F6) =="
if ! python3 scripts/check_falsifiers.py; then
  echo "WARNING: check_falsifiers.py failed; keeping previous data/falsifiers.json." >&2
fi

echo ""
echo "Done: dashboard/index-generated.html (thesis page dashboard/index.html untouched)"
