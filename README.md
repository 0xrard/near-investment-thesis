# NEAR Protocol — Beyond the Price

**Investment Thesis track (INV), NEAR Hackathon 2026.**
Submission deadline: **14 November 2026, 23:59 UTC**.

## The thesis, in one sentence

> NEAR is becoming the settlement layer for cross-chain value transfer — and Intents volume is the metric that proves it — but the market has already priced in the delivery.

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
fetched. `bash rebuild.sh --model-only` rebuilds model + figures + dashboard +
falsifier checks from the shipped CSVs with no credentials.

**Known gaps (see also THESIS.md §8, "What we couldn't compute").**
Sub-hypothesis A is `cannot_compute`: the canonical Intents Explorer API
needs a JWT from the partner dashboard, not yet obtained — the lead/lag test
in the model uses DefiLlama + CoinGecko series instead. G4 (Intents volume
by swapper) is a placeholder for the same reason. G5 was deliberately
skipped: it duplicates G2 (same transaction counts), so it is not missing
work, it is the same chart twice.

## How to re-run (one command)

Run it via `bash` (not `./rebuild.sh`): files uploaded through the GitHub web UI lose the executable bit, so the bare form fails with Permission denied in a fresh clone.

```bash
bash rebuild.sh            # full rebuild: fetch -> model -> figures -> dashboard -> falsifiers
bash rebuild.sh --model-only   # Level 2: model + figures + dashboard + falsifiers, NO credentials needed
```

### Level 1 — full rebuild (needs credentials)

- A Google Cloud project with BigQuery API enabled (`GCP_PROJECT_ID`, credentials via `GOOGLE_APPLICATION_CREDENTIALS`).
- An Intents Explorer API JWT (`INTENTS_EXPLORER_JWT`, `INTENTS_EXPLORER_API_URL`).
- Copy `.env.example` to `.env` and fill it in. Keys never enter the repo.

```bash
cp .env.example .env   # fill in your credentials
bash rebuild.sh
```

If credentials are missing, `fetch` fails with a clear message telling you exactly what is missing — and you can still run `bash rebuild.sh --model-only`.

### Level 2 — model only (no credentials, needs Python packages + internet)

Needs Python 3.10+ and `pip install -r requirements.txt` (requests +
matplotlib, for the figure scripts; the BigQuery package in the same file is
only needed for Level 1). Use a virtual environment — on Debian/Ubuntu
system Python, plain `pip install` is refused (PEP 668).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
bash rebuild.sh --model-only
```

The model runs on the CSVs already shipped in `data/`; if no CSVs exist yet it runs on the clearly-labelled placeholder
assumptions in `model/config.yaml` and every output is marked as a
placeholder. Steps 3 (figures) and 5 (falsifiers) also fetch live keyless
data — Binance, DefiLlama, CoinGecko, NearBlocks, and the monthly net
revenue scrape from revenue.near.org — so this mode needs internet, and a
re-run can shift the live numbers slightly from the ones printed in this
README. What a re-run guarantees is the method, the same model outputs from
the shipped CSVs, and the same falsifier verdicts.

This is the level the AI judges check: clone → install → run one command →
the dashboard builds and the falsifier verdicts match this README (live
figure values may differ slightly from the frozen numbers here).

### Falsifier checks (step 5 of every rebuild)

`scripts/check_falsifiers.py` evaluates the six falsifiers (F1–F6, listed in
THESIS.md §7, "What would change our mind") from the shipped CSVs plus the
monthly net revenue series scraped live from revenue.near.org (keyless, same
scrape the figure scripts use), and writes `data/falsifiers.json`. F1, F2,
F4, and F6 are computed (F4 from the buyback-wallet snapshot
`data/buyback_wallet_30d.json`); F3 reports not-yet-decidable until its
30 Jun 2027 deadline; F5 reports cannot-check (no public ETF-flow endpoint
— so the F5 reading is not re-runnable). A triggered
falsifier is a finding, not a build error, and never breaks the build. (The
"PDF v3" cited in THESIS.md is Nino's own thesis dossier, *NEAR Protocol
Investment Thesis*, 11 Nov 2026 — it is not in this repo; THESIS.md is the
repo's own write-up of the same thesis.)

## Repo layout

```
README.md               this file
THESIS.md               the thesis: claim, sub-hypotheses, evidence for/against, model, falsifiers
queries/                one BigQuery SQL file per chart (G1-G6) + freshness check; all filter on block_date
data/                   raw CSVs (shipped, with source + pull date in manifest.json) + model outputs
scripts/
  fetch.py              pulls BigQuery / Intents API / CoinGecko / DefiLlama -> data/
  build_dashboard.py    builds dashboard/index-generated.html from data/ + model outputs
  check_falsifiers.py   evaluates falsifiers F1-F6 -> data/falsifiers.json
  generate_chapter3_figures.py   fig1-price, fig2-intents-volume, fig3-fee-revenue (live, keyless)
  generate_chapter4_figures.py   fig4-L1-contraction, fig5-TVL/stablecoins, fig6-offset-ratio, fig7-threshold
  generate_chapter5_figures.py   fig8-fee-multiples, fig9-lead-lag
figures/                fig1-fig9 PNGs (regenerated by the figure scripts) + captions in data/captions.json
model/
  config.yaml           ALL model assumptions in one file (fee take rate, growth, issuance)
  model.py              scenario model + deflationary-threshold recomputation + hypothesis tests
dashboard/
  index.html            thesis page served by GitHub Pages — frozen 11 Nov 2026 snapshot; rebuild never overwrites it
  index-generated.html  regenerated dashboard from the pipeline (data/ + model outputs)
rebuild.sh              ONE command: fetch -> model -> figures -> dashboard -> falsifiers
.env.example            credential placeholders (no real values)
LICENSE                 MIT licence for this repo
```

## Data sources

| Source | What it feeds | Key / cost |
|---|---|---|
| BigQuery `bigquery-public-data.crypto_near_mainnet_us` | G1-G3, G6 (accounts, tx, contracts, success rate, gas) | GCP project, free tier 1 TB/month |
| NEAR Intents Explorer API | G4, G5, sub-hypothesis A (swapper-level data) | JWT from partner dashboard |
| DefiLlama API (`api.llama.fi`) | Intents volume + fees (cross-check), chain volumes for comparisons | none, free |
| CoinGecko Keyless API | NEAR price (+ SOL/ETH for comparisons) | none, free (~5 calls/min keyless) |
| Open Dev Data | Developer comparison (P7, secondary, cited) | none, free |

**Freshness (verified, not assumed).** An older draft warned that NEAR Lake
(the AWS S3 source behind the BigQuery dataset) was deprecated on 24 March
2026 and might stop indexing new blocks. That warning is outdated for this
dataset: `MAX(block_date)` in `bigquery-public-data.crypto_near_mainnet_us`
is **2026-11-11** (checked live 12 Nov 2026, block height 224,135,609) — the
dataset is still updating. The first query of every run is still
`queries/00-freshness.sql` (`MAX(block_date)`): if that date ever goes
months stale, the on-chain leg cannot speak about current usage and the
Intents API becomes the fresh leg — the dashboard says so.

## The model

`model/model.py` computes, from primary data only:

- **Scenario table** (bear / base / bull): implied annual settlement volume + implied annual fee revenue, with the fee take rate as an **open parameter** (base case 16 bps = the measured 60-day gross take of 16.4 bps; sensitivity at 5 / 10 / 16 / 20 bps — the exact rate is verified from Intents docs, never invented).
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
