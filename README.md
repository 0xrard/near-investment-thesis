# NEAR Protocol — Beyond the Price

**Investment Thesis track (INV), NEAR Hackathon 2026.**
Submission deadline: **14 November 2026, 23:59 UTC**.

## The thesis, in one sentence

> NEAR is becoming the settlement layer for cross-chain value transfer — and Intents volume is the metric that proves it, while the market hasn't priced it in yet.

## The hypothesis we test

Cross-chain volume through NEAR Intents is a better **leading indicator** of real network usage than token price. We test it three ways:

1. Does Intents volume **lead** price (lead/lag correlation), or only follow it?
2. Is Intents volume **sticky** — mostly repeat swappers, not one-offs? (Sub-hypothesis A)
3. Does Intents grow **together with** on-chain activity, or cannibalise it? (Sub-hypothesis B)

Every number in this repo traces to primary data (BigQuery, Intents Explorer API, DefiLlama, CoinGecko) or to a computation in `model/` whose assumptions are all in `model/config.yaml`. Anything we could not compute is listed in [`THESIS.md`](THESIS.md#what-we-couldnt-compute) — not hidden, not invented.

## Status

Data fetched 11–12 November 2026. BigQuery leg complete (lean): freshness
MAX(block_date) = 2026-11-11, G1 + G2 over 365 days, G3 lean 7 days,
G6 lean 30 days — all in `data/`, see `data/manifest.json` and
`data/README.md`. Intents volume + fees come from DefiLlama (keyless);
the canonical Intents Explorer API series needs a JWT and is not yet
fetched. `./rebuild.sh --model-only` rebuilds model + figures + dashboard
from the shipped CSVs with no credentials.

## How to re-run (one command)

```bash
./rebuild.sh            # full rebuild: fetch -> model -> build dashboard
./rebuild.sh --model-only   # Level 2: model + dashboard only, NO credentials needed
```

### Level 1 — full rebuild (needs credentials)

- A Google Cloud project with BigQuery API enabled (`GCP_PROJECT_ID`, credentials via `GOOGLE_APPLICATION_CREDENTIALS`).
- An Intents Explorer API JWT (`INTENTS_EXPLORER_JWT`, `INTENTS_EXPLORER_API_URL`).
- Copy `.env.example` to `.env` and fill it in. Keys never enter the repo.

```bash
cp .env.example .env   # fill in your credentials
./rebuild.sh
```

If credentials are missing, `fetch` fails with a clear message telling you exactly what is missing — and you can still run `./rebuild.sh --model-only`.

### Level 2 — model only (no credentials, zero setup)

Only Python 3.10+ (standard library) is needed. The model runs on the CSVs already shipped in `data/`; if no CSVs exist yet it runs on the clearly-labelled placeholder assumptions in `model/config.yaml` and every output is marked as a placeholder.

```bash
./rebuild.sh --model-only
```

This is the level the AI judges check: clone → run one command → the dashboard builds and matches this README.

## Repo layout

```
README.md               this file
THESIS.md               the thesis: claim, sub-hypotheses, evidence for/against, model, falsifiers
queries/                one BigQuery SQL file per chart (G1-G6) + freshness check; all filter on block_date
data/                   raw CSVs (shipped, with source + pull date in manifest.json) + model outputs
scripts/
  fetch.py              pulls BigQuery / Intents API / CoinGecko / DefiLlama -> data/
  build_dashboard.py    builds dashboard/index-generated.html from data/ + model outputs
model/
  config.yaml           ALL model assumptions in one file (fee take rate, growth, issuance)
  model.py              scenario model + deflationary-threshold recomputation + hypothesis tests
dashboard/
  index.html            thesis page served by GitHub Pages — frozen 11 Nov 2026 snapshot; rebuild never overwrites it
  index-generated.html  regenerated dashboard from the pipeline (data/ + model outputs)
rebuild.sh              ONE command: fetch -> model -> build dashboard
.env.example            credential placeholders (no real values)
```

## Data sources

| Source | What it feeds | Key / cost |
|---|---|---|
| BigQuery `bigquery-public-data.crypto_near_mainnet_us` | G1-G3, G6 (accounts, tx, contracts, success rate, gas) | GCP project, free tier 1 TB/month |
| NEAR Intents Explorer API | G4, G5, sub-hypothesis A (swapper-level data) | JWT from partner dashboard |
| DefiLlama API (`api.llama.fi`) | Intents volume + fees (cross-check), chain volumes for comparisons | none, free |
| CoinGecko Keyless API | NEAR price (+ SOL/ETH for comparisons) | none, free (~5 calls/min keyless) |
| Open Dev Data | Developer comparison (P7, secondary, cited) | none, free |

**Freshness warning:** NEAR Lake (the AWS S3 source behind the BigQuery dataset) was deprecated on 24 March 2026 and no longer indexes new blocks. The dataset itself remains available, but the first query of any run is `queries/00-freshness.sql` (`MAX(block_date)`). If the data stops months ago, the on-chain leg cannot speak about current usage and the Intents API becomes the fresh leg — the dashboard says so.

## The model

`model/model.py` computes, from primary data only:

- **Scenario table** (bear / base / bull): implied annual settlement volume + implied annual fee revenue, with the fee take rate as an **open parameter** (sensitivity at 5 / 10 / 20 bps — the exact rate is verified from Intents docs, never invented).
- **Deflationary threshold**: the daily Intents volume at which buybacks offset new issuance, **recomputed from primary data** (current fee rate, current issuance, current price). It is price-dependent: the higher the NEAR price, the further away the threshold.
- **Hypothesis tests**: lead/lag correlation of Intents volume vs NEAR price; sub-hypothesis B correlation (volume vs on-chain activity). Sub-hypothesis A needs swapper-level data from the Intents API.

**The model does NOT output a NEAR price target.** A price target from Intents volume alone would need a valuation multiple that is too far removed from the data — see [`THESIS.md`](THESIS.md#no-price-target) for the reasoning.

## The dashboard

`dashboard/index.html` is a static page (GitHub Pages). Every chart shows the query or source behind it, with one plain sentence on what it shows. Evidence **against** the thesis is shown first and prominently — a thesis that hides its counter-evidence is not a thesis.

## Author

**0xrard** — independent research, NEAR Hackathon 2026.

## What this is not

- Not financial advice. Not a price prediction.
- Not a copy of anyone else's research: the structure follows the bottom-up method (tokenomics → fee mechanism → threshold → what changes it); every number is recomputed from primary data or our own computation.
