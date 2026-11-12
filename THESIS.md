# NEAR Protocol — Beyond the Price

**Investment thesis — NEAR Hackathon 2026, track INV.**
Author: **0xrard**. Status: **filled with data as of 11–12 November 2026.**
Deadline: 14 November 2026, 23:59 UTC.

> Every number in this document traces to primary data or to a computation in `model/` whose assumptions are in `model/config.yaml`. Data as of: BigQuery 11 November 2026, DefiLlama / CoinGecko 11 November 2026, model run 12 November 2026 00:48 UTC. Re-run `bash rebuild.sh` to refresh; the judges can re-run for updated data. Where a number comes from Nino's PDF v3 (11 Nov 2026 08:36–09:00 UTC) rather than this repo's own computations, it is labelled as such.

## 1. The claim

NEAR is becoming the settlement layer for cross-chain value transfer — and Intents volume is the metric that proves it, while the market hasn't priced it in yet.

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
Correlation of daily Intents volume vs on-chain activity over 364 common days (`model_outputs.json`, `B_additive`): active accounts r = −0.19, transaction count r = −0.10. Intents volume does not rise together with on-chain activity; if anything it moves slightly the other way. And the levels confirm it: daily active signers fell 69.7% year over year (G1) while Intents volume stayed high (cumulative $37.3B, 30-day average $125.3M/day). On the evidence in this repo, sub-hypothesis B fails as stated. The Intents contracts are heavily used on-chain (G3: `intents.near` is the #2 contract by function calls), so Intents is real usage of NEAR — but it has not held on-chain activity up. The thesis must be read with that failure in mind; it is the main reason for the verdict in §6.

## 4. Evidence for

Each item cites its chart and query. All figures as of 11–12 November 2026 unless labelled otherwise.

- **G1: daily active accounts** (`queries/g1-daily-active-accounts.sql`, 365 days, 12 Nov 2025 → 11 Nov 2026, `data/bq_g1_daily_active_accounts.csv`). Average 138,756/day; maximum 592,250 (15 Feb 2026); minimum 42,517 (16 Sep 2026). The level is the evidence *against* (see §5); the series itself is the baseline the thesis is judged on.
- **G2: transaction counts** (`queries/g2-tx-counts.sql`, 365 days). Total 690,869,820 transactions; average 1,892,794/day; transactions per active account average 12.81. Signer counts match G1 exactly (0 mismatched rows) — two independent queries agree.
- **G3: contract usage** (`queries/g3-contract-usage.sql`, LEAN 7-day window 5–11 Nov 2026, `data/bq_g3_contract_usage.csv`). 9,963 rows, 3,761 contracts, 10,846,697 function calls (~1.55M/day). Top contracts: `game.hot.tg` 15.4%, **`intents.near` 12.3% — the #2 contract on NEAR**, `token.sweat` 9.2%, `wrap.near` 6.1%, Ref Finance 5.5% + 5.2%. Top 10 contracts = 70.2% of all calls: usage is concentrated. The full 365-day join needs 2.39 TB of scan, over the 1 TB/month BigQuery Sandbox quota, so G3 is a 7-day window with no `unique_signers` column — see §8. Function calls per transaction run 1.7–2.2 over the same 7 days, a sane cross-check against G2.
- **G4: Intents swap volume** (DefiLlama, `api.llama.fi/summary/dexs/near-intents`, 11 Nov 2026). Cumulative $37,324,522,122; 30-day average $125,257,736/day (12 Oct → 10 Nov 2026); annualised gross fees $71,529,432 (30-day run-rate × 12). The canonical Intents Explorer API series was not fetched (no JWT); DefiLlama is the source used here and is labelled as such wherever it appears.
- **G5: Intents volume vs NEAR price — the key chart.** Lead/lag correlation on daily *levels* (`model_outputs.json`): r ≈ 0.52 at every lag from −7 to +7 days; best lag +4 days (volume leads by 4 days) r = 0.549 vs lag 0 r = 0.518. The gap between the best lag and lag 0 is 0.031 — too small to claim a lead. A change-based test on the same question (PDF v3) found r = +0.01 at lag 0, max |r| = 0.075: no correlation. The honest reading is that **a lead is not established**: levels of two trending series correlate, changes do not. Do not cite r = 0.55 as "volume leads price".
- **G6: success rate + gas burnt** (`queries/g6-outcomes.sql`, LEAN 30-day window 13 Oct → 11 Nov 2026, `data/bq_g6_outcomes.csv`). Success rate averages 98.28% (range 97.57%–99.07%) — stable and high. Outcomes average 4,000,871/day; gas burnt totals 3.07e20 over the 30 days. One outlier, flagged not concluded: 15 Oct 2026 had 14,335,195 outcomes, 15.72× that day's transactions, against a normal ratio of ~5×. The `status` column name was verified via `INFORMATION_SCHEMA` (the draft query's `outcome_status` does not exist).
- **Pillar 3: the $3.8M exploit case** — detected, auto-paused, funds returned within 36 hours; see postmortem. A system that is attacked and recovers with funds returned is evidence of resilience — but the exploit itself is a real risk, listed in §5.

## 5. Evidence against

*Shown first and prominently on the dashboard. A thesis that hides its counter-evidence is not a thesis.*

G1/G2 now confirm the reported figures, so they are stated here as measured, not merely reported:

- **Confirmed: NEAR lost about two-thirds of its daily active users in a year, and transactions fell by about four-fifths.** Daily active signers: 257,073 on 12 Nov 2025 → 77,831 on 11 Nov 2026, **−69.7%** on endpoints; November monthly averages 238,347 (2025) → 81,139 (2026, 11 days), −66%. Transactions: first 7 days average 4,328,307/day → last 7 days 802,188/day, **−81.5%**. There is also a cliff inside the year: March 2026 averaged 3,479,269 tx/day, April 2026 averaged 946,610/day. This is precisely the falsifier pattern of sub-hypothesis B (§3), and B fails on the correlation test as well.
- **Reported:** "Buying NEAR for its usage does not buy a share of NEAR's users. It buys a fee on swaps between other chains." (tradingstrategies.work, independent coverage.) The fee-capture mechanism is real but partial: PDF v3 puts October capture at 39.2% (vs 19.5% lifetime) and take at 6.28 bps in October; the repo model uses a **placeholder** capture rate of 26% (see §6) — the two are not reconciled.
- **Reported:** NEAR's own on-chain fees fell from $5.18M to $1.27M over the reported period. Not recomputed in this repo (G6 measures success rate and gas, not USD fees); cited as reported, not as measured.
- **Buybacks offset only a fraction of issuance.** Emissions offset is 18.5% on 12 November 2026 (17.8% on the 11 Nov snapshot; 17.5% in PDF v3, peak 25.2% in September). Bought tokens are held, not burned — "buyback offsets issuance" is not the same as "supply shrinks". The model threshold (§6) makes the same point in volume terms.
- Structural risks: Rhea concentrates NEAR DEX volume (a single point of failure); Across, UniswapX and 1inch Fusion compete with Intents; solver/attestor centralisation is unverified; one recovered exploit is not a guarantee against the next.

**Result of the check:** confirmed by G1/G2 as measured above. The counter-evidence is not a footnote to the thesis; it is the reason for the verdict in §6.

## 6. The model

The model (`model/model.py`, assumptions in `model/config.yaml`) computes three things from primary data. Outputs below are from `data/model_outputs.json`, generated 12 November 2026 00:48 UTC from the shipped CSVs. Two inputs are placeholders and are labelled as such wherever they matter: **fee capture rate 26%** and **total NEAR supply 1.3B**.

1. **Scenario table (bear / base / bull), 5-year horizon, at 10 bps take:** Bear (0% annual growth) $45.72B annual settlement volume / $45.72M annual fee revenue; Base (15%/yr) $91.96B / $91.96M; Bull (30%/yr) $169.75B / $169.75M. At 5 bps halve the fee figures; at 20 bps double them (full sensitivity table in `model_outputs.json`).
2. **Deflationary threshold (V\*):** daily Intents volume at which buybacks offset new issuance — **$1,275,186,254/day at 10 bps**, $2,550,372,508/day at 5 bps, $637,593,127/day at 20 bps; annual issuance value $121,015,176. Current volume is $125,257,736/day (30-day average) — **10.2× below the 10 bps threshold**. Even the Bull year-5 volume ($169.75B/year ≈ $465M/day) stays below it. Under the model's assumptions the threshold is out of reach in every scenario. Note: PDF v3 gives V\* of $516M/day (at 2.5% issuance) / $330M/day (at 1.6%), computed with different capture assumptions; the two V\* figures are not directly comparable until the capture rate is reconciled — the model uses the 26% placeholder, PDF v3 implies a higher October capture (39.2%). Treat the threshold as assumption-dependent, not as a single number.
3. **Sensitivity table:** fee take rate (5 / 10 / 20 bps) × growth (0% / 15% / 30%) → annual fee revenue; see `model_outputs.json`.
4. **P / F** (market cap / annualised fees): **68.26×** gross (market cap $4,882,342,987 / annualised gross fees $71,529,432, both 11 Nov 2026). Cross-check: Nino's input P/F 58.8× (9 Nov 2026) was computed from the same inputs at that date. On a net basis (PDF v3, October net revenue $2.50M/month × 12 = $30M/year) the multiple is ≈163×.
5. **Net issuance after burn (2027E)** ~1.5% (Nino's estimate, 9 Nov 2026) — a scenario cross-check, not a model input; verify from on-chain burn data before citing.

**Current outputs:** computed, 12 November 2026 00:48 UTC — see `data/model_outputs.json`. `placeholder: true` only because the fee capture rate and total supply are placeholders; every other input is fetched data.

### Verdict: priced for delivery

The settlement mechanism is real — Intents is the #2 contract on NEAR by function calls (12.3%), cumulative volume is $37.3B at $125M/day — but the price already reflects it. At 68.3× gross fees (163× net on October run-rate), with on-chain activity down ~70–80% year over year, sub-hypothesis B failed, no lead established, and the deflationary threshold 10× above current volume in every scenario, the market is paying for delivery that has not arrived. That is the thesis: **priced for delivery, not priced for failure.** What would overturn it is in §7.

### No price target

The model does **not** output a NEAR price target. A price target from Intents volume alone would need a valuation multiple (what the market pays per dollar of fee revenue) that is too far removed from the data — it would be an assumption dressed up as a conclusion. What the model does output is volume and fee revenue under stated scenarios, and the volume threshold at which issuance is offset. Anyone who wants a price target must supply their own multiple, openly, in `model/config.yaml`.

## 7. What would change our mind

The thesis is wrong — or not worth holding — if any of these show up in the data:

- Intents volume **only follows** price (no lead at any lag in the lead/lag test), i.e. volume is a consequence of speculation, not of usage. **Status: not established either way on levels; on changes there is no correlation (PDF v3 r ≈ 0.01). The lead leg is unproven, which already weakens the claim.**
- Sub-hypothesis A fails: >80% of volume is one-off addresses. **Status: uncomputed (no JWT).**
- Sub-hypothesis B fails: Intents volume rises while on-chain activity falls (cannibalisation). **Status: failed on the evidence in §3 and §5.**
- The deflationary threshold sits so far above realistic volume growth that buybacks can never offset issuance under any plausible scenario. **Status: holds under the model's assumptions (threshold 10.2× current volume; Bull year-5 still below it).**
- Fee capture collapses (the share of gross Intents fees reaching NEAR falls toward zero). **Status: not observed — October capture 39.2% per PDF v3 — but the model's 26% capture is a placeholder, so this leg is not nailed down.**

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
