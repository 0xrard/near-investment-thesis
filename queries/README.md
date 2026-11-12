# queries/ — BigQuery SQL, one file per chart

Dataset: `bigquery-public-data.crypto_near_mainnet_us`
Docs: https://docs.near.org/data-infrastructure/big-query

## Rules (non-negotiable)

- **Every query filters on `block_date`.** The tables are partitioned by
  it; filtering keeps the bill small (free tier: 1 TB/month).
- Run `00-freshness.sql` FIRST, on every run. It returns `MAX(block_date)`
  for the dataset. (An older draft warned NEAR Lake was deprecated on
  24 March 2026 and might stop indexing new blocks; that warning is
  outdated — `MAX(block_date)` was 2026-11-11 when checked live on
  12 Nov 2026, so the dataset is still updating.) If `MAX(block_date)` is
  months old, the on-chain leg cannot speak about current usage — the
  dashboard says so, and the Intents API becomes the fresh leg.
- Column names follow docs.near.org's example queries. `execution_outcomes`
  in `g6` uses the verified column `status` (not `outcome_status` as the
  draft assumed) — confirmed via INFORMATION_SCHEMA on 12 Nov 2026;
  `queries/g6-outcomes.sql` already uses it.

## Files

| File | Chart | What it returns |
|---|---|---|
| `00-freshness.sql` | — | `MAX(block_date)` + block count (freshness gate) |
| `g1-daily-active-accounts.sql` | G1 | Daily active signers |
| `g2-tx-counts.sql` | G2 | Daily transaction counts (+ tx per active account) |
| `g3-contract-usage.sql` | G3 | Daily FUNCTION_CALL counts, top contracts |
| `g4-intents-volume.sql` | G4 | Daily calls/gas to Intents contracts (BigQuery proxy) |
| `g5-key-chart.sql` | G5 | Daily on-chain activity (context leg of the key chart) |
| `g6-outcomes.sql` | G6 | Daily success rate + gas burnt |

## Notes on G4 and G5

- **G4 (Intents swap volume):** the canonical series comes from the
  Intents Explorer API / DefiLlama via `scripts/fetch.py`
  (`data/intents_volume_daily.csv`). The SQL file is the BigQuery proxy:
  daily FUNCTION_CALL counts and gas to the Intents contracts. The
  contract list is a **placeholder** — fill it with verified Intents
  contract addresses from the docs before running; until then the query
  returns zero rows, which is honest, not a bug.
- **G5 (key chart: Intents volume vs NEAR price):** a two-source chart.
  Volume comes from the Intents API / DefiLlama, price from CoinGecko.
  The SQL file returns the on-chain activity series (tx counts + active
  accounts) that the dashboard draws as the context line; the join of
  the three series happens in `scripts/build_dashboard.py`.

## How to run

BigQuery console, or via `scripts/fetch.py` (needs `GCP_PROJECT_ID` +
credentials in `.env` and `pip install -r requirements.txt`).
