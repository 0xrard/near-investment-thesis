# NEAR Protocol — Beyond the Price

**Investment thesis — NEAR Hackathon 2026, track INV.**
Author: **0xrard**. Status: **filled with data as of 11–12 November 2026.**
Deadline: 14 November 2026, 23:59 UTC.

> Every number in this document traces to primary data or to a computation in `model/` whose assumptions are in `model/config.yaml`. Data as of: BigQuery 11 November 2026, DefiLlama / CoinGecko 11 November 2026, model run 13 November 2026 09:43 UTC. Re-run `bash rebuild.sh` to refresh; the judges can re-run for updated data. Where a number comes from Nino's PDF v3 (11 Nov 2026 08:36–09:00 UTC) rather than this repo's own computations, it is labelled as such.

## 1. The claim

NEAR is becoming the settlement layer for cross-chain value transfer — and Intents volume is the metric that proves it — but the market has already priced in the delivery.

More precisely, the testable claim is:

**Cross-chain volume through NEAR Intents is a better leading indicator of real network usage than token price.**

Three things have to be true for the claim to hold:

1. Intents volume **leads** price (it moves first; price follows) — tested by lead/lag correlation (G5).
2. Intents volume is **sticky** — mostly repeat swappers, not one-offs (sub-hypothesis A).
3. Intents grows **together with** on-chain activity, not by cannibalising it (sub-hypothesis B).

If any of the three fails, the claim weakens — see §7 (what would change our mind).

## 2. Sub-hypothesis A — Intents volume is sticky

**Claim:** most Intents volume comes from addresses that swap repeatedly, not from one-off users.

**Test:** repeat-swapper share of volume, per week — the share of volume from addresses that have swapped before.

**Falsifier:** if more than 80% of volume comes from addresses that never swap again, usage is not sticky and the thesis weakens.

**Data:** Intents Explorer API (swapper-level data). **Status: not available** — the API needs a JWT, which was not obtained (the partner-dashboard registration was not completed; Intents data in this repo comes from DefiLlama instead). If the API does not expose a swapper field, this sub-hypothesis stays uncomputed.

**Result:** cannot compute. The model returns `A_sticky: cannot_compute` for exactly this reason. This is a gap, not a pass — see §8.

## 3. Sub-hypothesis B — Intents grows with on-chain activity, not instead of it

**Claim:** rising Intents volume goes together with rising (or holding) daily active accounts and transaction counts on NEAR — Intents adds demand, it does not move existing activity off-chain.

**Test:** correlation of daily Intents volume vs daily active accounts + transaction counts (BigQuery) + calls to Intents contracts (`receipt_actions`).

**Falsifier:** if Intents volume rises while on-chain activity falls, Intents is cannibalising — this weakens the "NEAR as settlement layer" thesis. This is exactly the pattern reported by independent coverage (see §5, evidence against), so the test matters.

**Data:** BigQuery (`transactions`, `receipt_actions`) + DefiLlama Intents volume. Both computed 11–12 November 2026.

**Result: not supported — the falsifier pattern is what the data shows.**
Correlation of Intents volume vs on-chain activity over ~363 common days (`model_outputs.json`, `B_additive`). On daily changes (primary test: volume growth vs activity growth) active accounts r = +0.02 and transaction count r = +0.20 — weak, so day-to-day Intents growth neither tracks nor opposes on-chain activity. On daily levels the correlations are r = −0.19 and −0.10 (`correlations_levels`), but those mostly reflect two opposite trends, not a day-to-day relationship, so they are descriptive only. The decisive evidence is the divergence of the trends: daily active signers fell 69.7% year over year (G1) while Intents volume stayed high (cumulative $37.3B, 30-day average $125.3M/day). On the evidence in this repo, sub-hypothesis B fails as stated. The Intents contracts are heavily used on-chain (G3: `intents.near` is the #2 contract by function calls), so Intents is real usage of NEAR — but it has not held on-chain activity up. The thesis must be read with that failure in mind; it is the main reason for the verdict in §6.

## 4. Evidence for

Each item cites its chart and query. All figures as of 11–12 November 2026 unless labelled otherwise.

- **G1: daily active accounts** (`queries/g1-daily-active-accounts.sql`, 365 days, 12 Nov 2025 → 11 Nov 2026, `data/bq_g1_daily_active_accounts.csv`). Average 138,756/day; maximum 592,250 (15 Feb 2026); minimum 42,517 (16 Sep 2026). The level is the evidence *against* (see §5); the series itself is the baseline the thesis is judged on.
- **G2: transaction counts** (`queries/g2-tx-counts.sql`, 365 days). Total 690,869,820 transactions; average 1,892,794/day; transactions per active account average 12.81. Signer counts match G1 exactly (0 mismatched rows) — two independent queries agree.
- **G3: contract usage** (`queries/g3-contract-usage.sql`, LEAN 7-day window 5–11 Nov 2026, `data/bq_g3_contract_usage.csv`). 9,963 rows, 3,761 contracts, 10,846,697 function calls (~1.55M/day). Top contracts: `game.hot.tg` 15.4%, **`intents.near` 12.3% — the #2 contract on NEAR**, `token.sweat` 9.2%, `wrap.near` 6.1%, Ref Finance 5.5% + 5.2%. Top 10 contracts = 70.2% of all calls: usage is concentrated. The full 365-day join needs 2.39 TB of scan, over the 1 TB/month BigQuery Sandbox quota, so G3 is a 7-day window with no `unique_signers` column — see §8. Function calls per transaction run 1.7–2.2 over the same 7 days, a sane cross-check against G2.
- **G4: Intents swap volume** (DefiLlama, `api.llama.fi/summary/dexs/near-intents`, 11 Nov 2026). Cumulative $37,324,522,122; 30-day average $125,257,736/day (12 Oct → 10 Nov 2026); annualised gross fees $71,529,432 (30-day run-rate × 12). The canonical Intents Explorer API series was not fetched (no JWT); DefiLlama is the source used here and is labelled as such wherever it appears.
- **G5: Intents volume vs NEAR price — the key chart.** Lead/lag correlation on daily *levels* (`model_outputs.json`, `lags_levels`): r ≈ 0.52 at every lag from −7 to +7 days; best lag +4 days (volume leads by 4 days) r = 0.549 vs lag 0 r = 0.518. The gap between the best lag and lag 0 is 0.031 — too small to claim a lead. A change-based test on the same question (PDF v3) found r = +0.01 at lag 0, max |r| = 0.075: no correlation. The honest reading is that **a lead is not established**: levels of two trending series correlate, changes do not. Do not cite r = 0.55 as "volume leads price". The repo's own change-based test (`lags`, daily log changes) agrees: strongest lag −3 days, r = −0.10, inside the ±0.10 95% noise band — no lag stands out.
- **G6: success rate + gas burnt** (`queries/g6-outcomes.sql`, LEAN 30-day window 13 Oct → 11 Nov 2026, `data/bq_g6_outcomes.csv`). Success rate averages 98.28% (range 97.57%–99.07%) — stable and high. Outcomes average 4,000,871/day; gas burnt totals 3.07e20 over the 30 days. One outlier, flagged not concluded: 15 Oct 2026 had 14,335,195 outcomes, 15.72× that day's transactions, against a normal ratio of ~5×. The `status` column name was verified via `INFORMATION_SCHEMA` (the draft query's `outcome_status` does not exist).
- **Pillar 3: the $3.8M exploit case** — detected, auto-paused, funds returned within 36 hours; see postmortem. A system that is attacked and recovers with funds returned is evidence of resilience — but the exploit itself is a real risk, listed in §5.

## 5. Evidence against

*Shown first and prominently on the dashboard. A thesis that hides its counter-evidence is not a thesis.*

G1/G2 now confirm the reported figures, so they are stated here as measured, not merely reported:

- **Confirmed: NEAR lost about two-thirds of its daily active users in a year, and transactions fell by about four-fifths.** Daily active signers: 257,073 on 12 Nov 2025 → 77,831 on 11 Nov 2026, **−69.7%** on endpoints; November monthly averages 238,347 (2025) → 81,139 (2026, 11 days), −66%. Transactions: first 7 days average 4,328,307/day → last 7 days 802,188/day, **−81.5%**. There is also a cliff inside the year: March 2026 averaged 3,479,269 tx/day, April 2026 averaged 946,610/day. This is precisely the falsifier pattern of sub-hypothesis B (§3): activity fell while Intents volume held up. (The day-to-day correlation test is weak rather than negative — see §3.)
- **Reported:** "Buying NEAR for its usage does not buy a share of NEAR's users. It buys a fee on swaps between other chains." (tradingstrategies.work, independent coverage.) The fee-capture mechanism is real but partial: the repo model now uses the **measured** 60-day figures (2026-09-12..2026-11-10, falsifier F2): gross take 16.4 bps and capture 32.6% (net $4.55M of gross $13.95M), i.e. a net take of 5.35 bps. PDF v3's October figures are higher — capture 39.2% (vs 19.5% lifetime) and net take 6.28 bps — because they cover October alone; they are different windows of the same measurement, not a conflict (see §6).
- **Reported:** NEAR's own on-chain fees fell from $5.18M to $1.27M over the reported period. Not recomputed in this repo (G6 measures success rate and gas, not USD fees); cited as reported, not as measured.
- **Buybacks offset only a fraction of issuance.** Emissions offset is about 17.5% month-to-date (12 Nov 2026 scrape of revenue.near.org, the source of Figure 6 and `data/stats.json`). It moves as the month accrues — earlier readings on 11–12 Nov ranged from 17.2% to 18.5% (17.8% on the frozen 11 Nov dashboard; 17.5% in PDF v3) — and the September peak was 25.2%. Bought tokens are held, not burned — "buyback offsets issuance" is not the same as "supply shrinks". The model threshold (§6) makes the same point in volume terms.
- Structural risks: Rhea concentrates NEAR DEX volume (a single point of failure); Across, UniswapX and 1inch Fusion compete with Intents; solver/attestor centralisation is unverified; one recovered exploit is not a guarantee against the next.

**Result of the check:** confirmed by G1/G2 as measured above. The counter-evidence is not a footnote to the thesis; it is the reason for the verdict in §6.

## 6. The model

The model (`model/model.py`, assumptions in `model/config.yaml`) computes three things from primary data. Outputs below are from `data/model_outputs.json`, generated 13 November 2026 09:43 UTC from the shipped CSVs. No input is a placeholder any more: **gross take 16 bps** (measured 16.4 bps, 60-day gross fees / volume), **fee capture rate 32.6%** (measured, 60-day net / gross, falsifier F2) and **total NEAR supply 1,311,421,234** (CoinGecko, 11 Nov 2026) all come from shipped data. The scenario growth rates (0% / 15% / 30%) are assumptions, not measurements; the 30% bull rate is illustrative.

1. **Scenario table (bear / base / bull), 5-year horizon, at 16 bps take:** Bear (0% annual growth) $45.72B annual settlement volume / $73.15M annual fee revenue; Base (15%/yr) $91.96B / $147.13M; Bull (30%/yr) $169.75B / $271.60M. The bear case is today's run-rate by construction (16 bps × $45.72B ≈ $73M, against $71.5M annualised gross fees on DefiLlama's 30-day run-rate). Fee revenue scales linearly with the take rate (5 / 10 / 16 / 20 bps in `model_outputs.json`).
2. **Deflationary threshold (V\*):** daily Intents volume at which buybacks offset new issuance, V\* = annual issuance value / (365 × gross take × capture). Annual issuance value is $122,078,362 (supply 1,311,421,234 × 2.5% × $3.7235). At the base 16 bps take and 32.6% capture, **V\* = $641,221,753/day at 2.5% issuance — 5.1× the current $125,257,736/day** (30-day average) — and **$410,381,922/day, 3.3×, at the 1.6% issuance that HSP-029 phases in**. Other take rates at 2.5%: $2,051,909,608/day at 5 bps, $1,025,954,804/day at 10 bps, $512,977,402/day at 20 bps. Against the scenarios: Bull year-5 volume ($169.75B/year ≈ $465M/day) is below the 2.5% threshold (0.73×) but **above the 1.6% threshold (1.13×)**; Base year-5 volume ($252M/day) is below both (0.39× / 0.61×), as is Bear. So buybacks do not offset issuance in the bear or base scenarios; they do in the bull case only if HSP-029 goes live (earliest ~Feb 2027, phased over 24 months) and 30% annual growth is sustained for five years.
   *Reconciliation with PDF v3.* PDF v3 gives V\* of $516M/day (at 2.5% issuance) and $330M/day (at 1.6%). That is the same formula on October's inputs: its 6.28 bps "take" is net of capture (39.2% of roughly 16 bps gross) — the same definition as F2's 5.35 bps — and the repo formula with a 6.28 bps net take gives ≈$533M / $341M on this repo's supply and price, within about 3% of the PDF. The difference from the table above is the measurement window (October alone vs the 60-day average, net 5.22 bps at 16 bps × 32.6%; 5.35 bps measured), not a conflict. Read the threshold as a range: **roughly 2.7–5.1× current volume**, depending on the window and the issuance rate.
3. **Sensitivity table:** fee take rate (5 / 10 / 16 / 20 bps) × growth (0% / 15% / 30%) → annual fee revenue; see `model_outputs.json`.
4. **P / F** (market cap / annualised fees): **68.26×** gross (market cap $4,882,342,987 / annualised gross fees $71,529,432, both 11 Nov 2026). Cross-check: Nino's input P/F 58.8× (9 Nov 2026) was computed from the same inputs at that date. On a net basis (PDF v3, October net revenue $2.50M/month × 12 = $30M/year) the multiple is ≈163×.
5. **Net issuance after burn (2027E)** ~1.5% (Nino's estimate, 9 Nov 2026) — a scenario cross-check, not a model input; verify from on-chain burn data before citing.

**Current outputs:** computed, 13 November 2026 09:43 UTC — see `data/model_outputs.json`. `placeholder: false`; every input is fetched or measured data.

### Verdict: priced for delivery

The settlement mechanism is real — Intents is the #2 contract on NEAR by function calls (12.3%), cumulative volume is $37.3B at $125M/day — but the price already reflects it. At 68.3× gross fees (163× net on October run-rate), with on-chain activity down ~70–80% year over year, sub-hypothesis B failed, no lead established, and the deflationary threshold 3.3–5.1× above current volume (reached only in the bull case, and only after the 1.6% issuance cut), the market is paying for delivery that has not arrived. That is the thesis: **priced for delivery, not priced for failure.** What would overturn it is in §7.

### No price target

The model does **not** output a NEAR price target. A price target from Intents volume alone would need a valuation multiple (what the market pays per dollar of fee revenue) that is too far removed from the data — it would be an assumption dressed up as a conclusion. What the model does output is volume and fee revenue under stated scenarios, and the volume threshold at which issuance is offset. Anyone who wants a price target must supply their own multiple, openly, in `model/config.yaml`.

## 7. What would change our mind

The thesis is wrong — or not worth holding — if any of these show up in the data:

- Intents volume **only follows** price (no lead at any lag in the lead/lag test), i.e. volume is a consequence of speculation, not of usage. **Status: not established either way on levels; on changes there is no correlation (PDF v3 r ≈ 0.01). The lead leg is unproven, which already weakens the claim.**
- Sub-hypothesis A fails: >80% of volume is one-off addresses. **Status: uncomputed (no JWT).**
- Sub-hypothesis B fails: Intents volume rises while on-chain activity falls (cannibalisation). **Status: failed on the evidence in §3 and §5.**
- The deflationary threshold sits so far above realistic volume growth that buybacks do not offset issuance in the bear or base scenarios. **Status: holds for bear and base (threshold 5.1× current volume at 2.5% issuance, 3.3× at 1.6%; Base year-5 volume reaches 0.39× / 0.61× of it). It does not hold in the bull case, whose year-5 volume (≈$465M/day) is 1.13× the 1.6% threshold — so "never" is too strong.**
- Fee capture collapses (the share of gross Intents fees reaching NEAR falls toward zero). **Status: not observed — October capture 39.2% per PDF v3, 32.6% over 60 days measured in-repo (checker F2). The capture is now a measured input, so this leg is nailed down as far as the data goes.**

## 8. What we couldn't compute

*(Honest list. Anything here is a gap, not a hidden assumption.)*

- Sub-hypothesis A (sticky volume): needs swapper-level data from the Intents Explorer API — no JWT obtained, and the partner-dashboard registration was not completed. If the API has no swapper field, this stays uncomputed.
- Intents volume series (G4/G5) canonical version: pending Intents Explorer API (JWT). The series used here is DefiLlama (`near-intents`, verified live), labelled as such.
- G3 full window: the 365-day contract-usage join needs 2.39 TB of BigQuery scan, over the 1 TB/month Sandbox quota. The shipped file is a 7-day window (5–11 Nov 2026) with no `unique_signers` column. G6 is a 30-day window for the same quota reason.
- HSP-029 status (proposed issuance cut 2.5% → 1.6%): PDF v3 records it as passed 2 Nov 2026, with Security Council ratification plus a ~90-day grace period still ahead (earliest effect ~Feb 2027). Do not cite it as in force.
- TVL: published figures conflict (DefiLlama vs Rhea). No TVL figure is quoted anywhere in this thesis.
- Freshness: **resolved.** NEAR Lake was deprecated 24 Mar 2026, and the draft warned the dataset might stop updating. It has not: `MAX(block_date)` in `bigquery-public-data.crypto_near_mainnet_us.blocks` is **2026-11-11** (checked 12 Nov 2026, block height 224,135,609). The deprecation warning is outdated for this dataset. Re-check on every run with `queries/00-freshness.sql`.
- Two flagged outliers, not conclusions: daily active signers spiked to 177,510 on 10 Nov 2026 against ~77,000 on neighbouring days (G1); execution outcomes spiked to 14,335,195 on 15 Oct 2026, 15.72× that day's transactions (G6). Neither is explained yet.

## 9. Sources

- BigQuery `bigquery-public-data.crypto_near_mainnet_us` (queries in `queries/`, each file names its table). Sandbox projects: `near-thesis-514500` (freshness, G1, G2), `near-thesis-2` (G3, G6). No billing, no card.
- NEAR Intents Explorer API (JWT-gated; see `.env.example`) — not used; see §8.
- DefiLlama API (`api.llama.fi`) — Intents volume/fees, chain volumes. Volume is raw (unadjusted) — labelled as such on the dashboard.
- CoinGecko Keyless API — NEAR/SOL/ETH price history.
- Open Dev Data — developer comparison (secondary, cited).
- NEAR Intents postmortem ($3.8M exploit) — official postmortem.
- PDF v3, *NEAR Protocol Investment Thesis* (BusinessProfessional, 11 Nov 2026) — Nino's own dossier; figures from it are labelled "PDF v3" where used.
- Method note: the bottom-up structure (tokenomics → fee mechanism → threshold → what changes it) follows the method of published bottom-up NEAR research; the numbers, tests and conclusions are our own, recomputed from primary data.
