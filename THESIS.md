# NEAR Protocol — Beyond the Price

**Investment thesis — NEAR Hackathon 2026, track INV.**
Author: **0xrard**. Status: **filled with data as of 14 November 2026.**
Deadline: 14 November 2026, 23:59 UTC.

> Every number in this document traces to primary data or to a computation in `model/` whose assumptions are in `model/config.yaml`. Data as of: BigQuery 11 November 2026 (quoted, not re-run — see Appendix A.5), DefiLlama / CoinGecko / revenue.near.org / Nearblocks 14 November 2026, model run 14 November 2026 11:42 UTC. Re-run `bash rebuild.sh` to refresh; the judges can re-run for updated data. Where a number comes from Nino's PDF v3 (11 Nov 2026 08:36–09:00 UTC) rather than this repo's own computations, it is labelled as such.

## 1. The claim

NEAR is becoming the settlement layer for cross-chain value transfer — and Intents volume is the metric that proves it — but the market has already priced in the delivery.

More precisely, the testable claim is:

**Cross-chain volume through NEAR Intents is a better leading indicator of real network usage than token price.**

Three things have to be true for the claim to hold:

1. Intents volume **leads** price (it moves first; price follows) — tested by lead/lag correlation (G5).
2. Intents volume is **sticky** — mostly repeat swappers, not one-offs (sub-hypothesis A).
3. Intents grows **together with** on-chain activity, not by cannibalising it (sub-hypothesis B).

If any of the three fails, the claim weakens — see §7 (what would change our mind).

One fact about the claim's age: by its own kill lines, the thesis only became statable on 23 August 2026 — before that it would have been dead in 70% of historical windows (backtest, §7).

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

**Data:** BigQuery (`transactions`, `receipt_actions`) + DefiLlama Intents volume. BigQuery series quoted from the 11 November 2026 pull, not re-run (see Appendix A.5); Intents volume re-run 14 November 2026.

**Result: not supported — the falsifier pattern is what the data shows.**
Correlation of Intents volume vs on-chain activity over ~364 common days (`model_outputs.json`, `B_additive`). On daily changes (primary test: volume growth vs activity growth) active accounts r = +0.03 and transaction count r = +0.20 — weak, so day-to-day Intents growth neither tracks nor opposes on-chain activity. On daily levels the correlations are r = −0.19 and −0.10 (`correlations_levels`), but those mostly reflect two opposite trends, not a day-to-day relationship, so they are descriptive only. The decisive evidence is the divergence of the trends: daily active signers fell 69.7% year over year (G1) while Intents volume stayed high (cumulative $37.78B, 30-day average $126.58M/day). On the evidence in this repo, sub-hypothesis B fails as stated. The Intents contracts are heavily used on-chain (G3: `intents.near` is the #2 contract by function calls), so Intents is real usage of NEAR — but it has not held on-chain activity up. The thesis must be read with that failure in mind; it is the main reason for the verdict in §6.

## 4. Evidence for

Each item cites its chart and query. All figures as of 14 November 2026 unless labelled otherwise. BigQuery series (G1–G3, G6) were last pulled 11 November 2026 and are quoted, not re-run — see Appendix A.5.

- **Market snapshot, 14 Nov 2026** (CoinGecko). NEAR price **$3.33**, market cap **$4,362,731,157 ($4.36B)**, rank **#22**. Spot 24h volume $503M. Price is 83.7% below the all-time high of $20.40, and +36.5% year over year (vs the $2.44 close on 14 Nov 2025). The previous day's close (13 Nov 2026) was $3.51 — that figure appears in this document only as the 13 Nov close in the price history (Fig1), never as the current price.
- **G1: daily active accounts** (`queries/g1-daily-active-accounts.sql`, 365 days, 12 Nov 2025 → 11 Nov 2026, `data/bq_g1_daily_active_accounts.csv`). Average 138,756/day; maximum 592,250 (15 Feb 2026); minimum 42,517 (16 Sep 2026). The level is the evidence *against* (see §5); the series itself is the baseline the thesis is judged on.
- **G2: transaction counts** (`queries/g2-tx-counts.sql`, 365 days). Total 690,869,820 transactions; average 1,892,794/day; transactions per active account average 12.81. Signer counts match G1 exactly (0 mismatched rows) — two independent queries agree.
- **G3: contract usage** (`queries/g3-contract-usage.sql`, LEAN 7-day window 5–11 Nov 2026, `data/bq_g3_contract_usage.csv`). 9,963 rows, 3,761 contracts, 10,846,697 function calls (~1.55M/day). Top contracts: `game.hot.tg` 15.4%, **`intents.near` 12.3% — the #2 contract on NEAR**, `token.sweat` 9.2%, `wrap.near` 6.1%, Ref Finance 5.5% + 5.2%. Top 10 contracts = 70.2% of all calls: usage is concentrated. The full 365-day join needs 2.39 TB of scan, over the 1 TB/month BigQuery Sandbox quota, so G3 is a 7-day window with no `unique_signers` column — see §8. Function calls per transaction run 1.7–2.2 over the same 7 days, a sane cross-check against G2.
- **G4: Intents swap volume** (DefiLlama, `api.llama.fi/summary/dexs/near-intents`, 14 Nov 2026). Cumulative **$37,782,828,302 ($37.78B)**, 87.3% of it in the trailing 12 months; 30-day average **$126,582,068/day ($126.58M/day**, 15 Oct → 13 Nov 2026; DefiLlama total30d $3,797,462,047 / 30); annualised gross fees **$69,983,196 ($69.98M**, 30-day run-rate × 12; 30-day gross fees $5,831,933). The canonical Intents Explorer API series was not fetched (no JWT); DefiLlama is the source used here and is labelled as such wherever it appears.
- **G5: Intents volume vs NEAR price — the key chart.** Lead/lag correlation on daily *levels* (`model_outputs.json`, `lags_levels`): r ≈ 0.52 at every lag from −7 to +7 days; best lag +4 days (volume leads by 4 days) r = 0.551 vs lag 0 r = 0.525. The gap between the best lag and lag 0 is 0.027 — too small to claim a lead. A change-based test on the same question is the honest one: on daily log changes (`lags`, n = 364 days) the strongest lag is −3 days at r = −0.098, inside the ±0.103 95% noise band — no lag stands out. A placebo (permutation) test confirms it: shuffling the price log-returns 1000× (seed 20261113) and re-running the same lag scan gives a mean max |r| of 0.107 — larger than the observed 0.098 — with **p = 0.592**, so the observed best lag is exactly what random shuffling produces. No exploitable timing edge. PDF v3's separate change-based test on its own series agrees (r = +0.01 at lag 0, max |r| = 0.07 at lag −4, placebo p = 0.554) — two independent runs, same conclusion: **a lead is not established**: levels of two trending series correlate, changes do not. Do not cite r = 0.55 as "volume leads price".
- **G6: success rate + gas burnt** (`queries/g6-outcomes.sql`, LEAN 30-day window 13 Oct → 11 Nov 2026, `data/bq_g6_outcomes.csv`). Success rate averages 98.28% (range 97.57%–99.07%) — stable and high. Outcomes average 4,000,871/day; gas burnt totals 3.07e20 over the 30 days. One outlier, flagged not concluded: 15 Oct 2026 had 14,335,195 outcomes, 15.72× that day's transactions, against a normal ratio of ~5×. The `status` column name was verified via `INFORMATION_SCHEMA` (the draft query's `outcome_status` does not exist).
- **Fig1: price history.** Last close $3.51 (13 Nov 2026); MA50 $4.62 / MA200 $2.66; plus the snapshot point for 14 Nov 2026 at $3.33 — the price has fallen below both the 13 Nov close and the 50-day average.
- **Fig5: TVL and stablecoins (14 Nov 2026, DefiLlama).** NEAR TVL $159.15M; stablecoins $132.03M, i.e. 83.0% of TVL. Stablecoin dominance of TVL is consistent with NEAR being used as a settlement rail rather than as a DeFi destination.
- **Fig7: the deflationary threshold.** Marker at V\* $573M/day (2.5% issuance) and $367M/day (1.6% issuance); new issuance runs at 89.82K NEAR/day at 2.5% and 57.49K NEAR/day at 1.6% (see §6).
- **Fig8: peer multiples (14 Nov 2026).** P/F (market cap / annualised gross fees): Tron 101.4×, ARB 151.6×, SOL 229.8×, BNB 575.2×, AVAX 807.8×, ETH 979.3×, median 402×; NEAR is the cheapest on gross fees at **62.3× gross / 145.3× net**. Cheap on fees is not the same as cheap on value — §6 explains why the net multiple and the failed sub-hypothesis B matter more.
- **Pillar 3: the $3.8M exploit case** — detected, auto-paused, funds returned within 36 hours; see postmortem. A system that is attacked and recovers with funds returned is evidence of resilience — but the exploit itself is a real risk, listed in §5.

## 5. Evidence against

*Shown first and prominently on the dashboard. A thesis that hides its counter-evidence is not a thesis.*

G1/G2 now confirm the reported figures, so they are stated here as measured, not merely reported:

- **Confirmed: NEAR lost about two-thirds of its daily active users in a year, and transactions fell by about four-fifths.** Daily active signers: 257,073 on 12 Nov 2025 → 77,831 on 11 Nov 2026, **−69.7%** on endpoints; November monthly averages 238,347 (2025) → 81,139 (2026, 11 days), −66%. Transactions: first 7 days average 4,328,307/day → last 7 days 802,188/day, **−81.5%**. There is also a cliff inside the year: March 2026 averaged 3,479,269 tx/day, April 2026 averaged 946,610/day. This is precisely the falsifier pattern of sub-hypothesis B (§3): activity fell while Intents volume held up. (The day-to-day correlation test is weak rather than negative — see §3.)
- **Reported:** "Buying NEAR for its usage does not buy a share of NEAR's users. It buys a fee on swaps between other chains." (tradingstrategies.work, independent coverage.) The fee-capture mechanism is real but partial: the repo model now uses the **measured** 60-day figures (15 Sep–13 Nov 2026, falsifier F2): gross take 16.3 bps and capture 31.5% (net $4.43M of gross $14.07M on $8.63B volume), i.e. a net take of **5.13 bps**. PDF v3's October figures are higher — capture 39.2% (net $2,502,470 / gross $6,388,076) and net take 6.28 bps — because they cover October alone; they are different windows of the same measurement, not a conflict (see §6). Over the last 30 days the capture is 31.0% (gross take 15.36 bps, net take 4.76 bps).
- **Reported:** NEAR's own on-chain fees fell from $5.18M to $1.27M over the reported period. Not recomputed in this repo (G6 measures success rate and gas, not USD fees); cited as reported, not as measured.
- **Buybacks offset only a fraction of issuance.** Emissions offset: September 25.2%, October 18.4%, November month-to-date 18.8% (14 Nov 2026 scrape of revenue.near.org, the source of Figure 6 and `data/stats.json`). It moves as the month accrues. Bought tokens are held, not burned — "buyback offsets issuance" is not the same as "supply shrinks". The model threshold (§6) makes the same point in volume terms.
- **Buyback wallet, full history — corrected.** A full-history Nearblocks pull (3,408 receipts, 18 Mar–14 Nov 2026) replaces the earlier incomplete reading: inflows total **2,293,097 NEAR** (3,391 inbound receipts, 3,360 of them from `intents.near`); outflow is exactly **3 transactions totalling 12,025 NEAR** — 20 NEAR on 20 Mar 2026, 5 NEAR on 20 Mar 2026, and the only material outflow, 12,000 NEAR on 10 Jul 2026; balance **2,281,071.57 NEAR**. The widely quoted "1.74M NEAR" is the revenue dashboard's attribution of buybacks, **not** the on-chain total — do not cite it as the wallet balance. In the trailing 30 days (falsifier F4, §7) outflow is 0.00 NEAR.

**Buyback wallet staircase** — cumulative balance of `buybacks.multisignature.near` at each month-end, from the full-history NearBlocks pull (3,408 receipts, 18 Mar–14 Nov 2026), checked 14 Nov 2026:

| End of | Cumulative balance (NEAR) |
|---|---:|
| Mar 2026 | 40 |
| Apr 2026 | 34,649 |
| May 2026 | 262,591 |
| Jun 2026 | 486,475 |
| Jul 2026 | 662,716 |
| Aug 2026 | 940,842 |
| Sep 2026 | 1,847,720 |
| Oct 2026 | 2,144,977 |
| 14 Nov 2026 | 2,281,072 |

Inflows of 2,293,097 NEAR minus the three outflows totalling 12,025 NEAR reconcile to the 2,281,072 NEAR balance (2,281,071.57 NEAR at fetch time).

- Structural risks: Rhea concentrates NEAR DEX volume (a single point of failure); Across, UniswapX and 1inch Fusion compete with Intents; solver/attestor centralisation is unverified; one recovered exploit is not a guarantee against the next.

**Result of the check:** confirmed by G1/G2 as measured above. The counter-evidence is not a footnote to the thesis; it is the reason for the verdict in §6.

## 6. The model

The model (`model/model.py`, assumptions in `model/config.yaml`) computes three things from primary data. Outputs below are from `data/model_outputs.json`, generated 14 November 2026 11:42 UTC from the shipped CSVs. No input is a placeholder any more: **gross take 16 bps** (measured 16.3 bps, 60-day gross fees / volume), **fee capture rate 32.6%** (measured, 60-day net / gross, falsifier F2 — the calibration rate retained from the 60-day measurement; the 14 Nov re-run reads 31.5% over the same window definition, see F2) and **total NEAR supply 1,311,421,234** (CoinGecko, 11 Nov 2026) all come from shipped data. The scenario growth rates (0% / 15% / 30%) are assumptions, not measurements; the 30% bull rate is illustrative.

1. **Scenario table (bear / base / bull), 5-year horizon, at 16 bps take:** Bear (0% annual growth) $46.20B annual settlement volume / $73.92M annual fee revenue; Base (15%/yr) $92.93B / $148.69M; Bull (30%/yr) $171.55B / $274.47M. The bear case is today's run-rate by construction (16 bps × $46.20B ≈ $74M, against $69.98M annualised gross fees on DefiLlama's 30-day run-rate). Fee revenue scales linearly with the take rate (5 / 10 / 16 / 20 bps in `model_outputs.json`).
2. **Deflationary threshold (V\*):** daily Intents volume at which buybacks offset new issuance, V\* = annual issuance value / (365 × gross take × capture). Annual issuance value is $109,175,818 (supply 1,311,421,234 × 2.5% × $3.33). At the base 16 bps take and 32.6% capture, **V\* = $573,450,593/day at 2.5% issuance — 4.5× the current $126,582,068/day** (30-day average) — and **$367,008,379/day, 2.9×, at the 1.6% issuance that HSP-029 phases in**. Other take rates at 2.5%: $1,835,041,898/day at 5 bps, $917,520,949/day at 10 bps, $458,760,475/day at 20 bps. Against the scenarios: Bull year-5 volume ($171.55B/year ≈ $470M/day) is below the 2.5% threshold (0.82×) but **above the 1.6% threshold (1.28×)**; Base year-5 volume ($255M/day) is below both (0.44× / 0.69×), as is Bear ($127M/day; 0.22× / 0.34×). So buybacks do not offset issuance in the bear or base scenarios; they do in the bull case only if HSP-029 goes live (earliest ~Feb 2027, phased over 24 months) and 30% annual growth is sustained for five years.
   *Reconciliation with PDF v3.* PDF v3 gives V\* of $516M/day (at 2.5% issuance) and $330M/day (at 1.6%). That is the same formula on October's inputs: its 6.28 bps "take" is net of capture (39.2% of roughly 16 bps gross) — the same definition as F2's 5.13 bps — and the repo formula with a 6.28 bps net take gives ≈$476M / $305M on this repo's supply and price, within about 8% of the PDF (the gap is the price, $3.33 vs the $3.51 close the PDF used, and the window). The difference from the table above is the measurement window (October alone vs the 60-day average, net 5.13 bps at 16 bps × 32.6% capture), not a conflict. Read the threshold as a range: **roughly 2.9–4.5× current volume**, depending on the window and the issuance rate.
3. **Sensitivity table:** fee take rate (5 / 10 / 16 / 20 bps) × growth (0% / 15% / 30%) → annual fee revenue; see `model_outputs.json`.
4. **P / F** (market cap / annualised fees): **62.3×** gross (market cap $4,362,731,157 / annualised gross fees $69,983,196, both 14 Nov 2026). Cross-check: Nino's input P/F 58.8× (9 Nov 2026) was computed from the same inputs at that date. On a net basis (October net revenue $2.50M/month × 12 = $30.03M/year) the multiple is ≈145×.
5. **Net issuance after burn (2027E)** ~1.5% (Nino's estimate, 9 Nov 2026) — a scenario cross-check, not a model input; verify from on-chain burn data before citing.

**Current outputs:** computed, 14 November 2026 11:42 UTC — see `data/model_outputs.json`. `placeholder: false`; every input is fetched or measured data.

### The threshold, measured through time

One measurement this report adds is the threshold tracked through time. V* is usually quoted once, on the day of writing; recomputed per calendar month through 2026 — monthly-average Intents volume and NEAR price, with the model's inputs held constant (gross take 16 bps, capture 32.6%, a net take of 5.22 bps; issuance 2.5%) — the multiple is not a fixed target. It stood at 3.2x in January, fell to its closest point of the year in February (2.2x, at an average price of $1.07), and widened again as the price recovered: 3.4x in September, 6.6x in October, 4.9x in November. October is the instructive month: volume was near its record ($129M/day average) yet deflation was furthest away all year, because V* scales with the price and the average price reached $4.90. A rising price therefore raises the volume the plan must deliver before net issuance turns negative — the market paying for delivery raises the cost of delivering. The two conventions agree where they should: November's monthly average (4.9x) sits beside Figure 7's single-date reading at the 14 November snapshot (4.5x) — the same model, evaluated two ways; the gap is the month's higher average price ($3.80 against $3.33).

| Month | Volume (avg $M/day) | Price (avg $) | V* ($M/day) | Distance |
|---|---|---|---|---|
| Jan | 87.9 | 1.62 | 279 | 3.2x |
| Feb | 84.9 | 1.07 | 184 | 2.2x |
| Mar | 67.1 | 1.28 | 221 | 3.3x |
| Apr | 63.2 | 1.34 | 230 | 3.7x |
| May | 64.4 | 1.77 | 305 | 4.7x |
| Jun | 78.5 | 2.13 | 367 | 4.7x |
| Jul | 71.1 | 1.89 | 325 | 4.6x |
| Aug | 89.6 | 1.73 | 299 | 3.3x |
| Sep | 160.1 | 3.19 | 550 | 3.4x |
| Oct | 128.6 | 4.90 | 844 | 6.6x |
| Nov | 133.6 | 3.80 | 654 | 4.9x |

### Verdict: priced for delivery

The settlement mechanism is real — Intents is the #2 contract on NEAR by function calls (12.3%), cumulative volume is $37.78B at $126.58M/day — but the price already reflects it. At **145× captured fees (62.3× gross)**, with on-chain activity down ~70–80% year over year, sub-hypothesis B failed, no lead established, and the deflationary threshold 2.9–4.5× above current volume (reached only in the bull case, and only after the 1.6% issuance cut), the market is paying for delivery that has not arrived. That is the thesis: **priced for delivery, not priced for failure.** What would overturn it is in §7.

### No price target

The model does **not** output a NEAR price target. A price target from Intents volume alone would need a valuation multiple (what the market pays per dollar of fee revenue) that is too far removed from the data — it would be an assumption dressed up as a conclusion. What the model does output is volume and fee revenue under stated scenarios, and the volume threshold at which issuance is offset. Anyone who wants a price target must supply their own multiple, openly, in `model/config.yaml`.

## 7. What would change our mind

The thesis is wrong — or not worth holding — if any of these show up in the data. Falsifier readings below are from `data/falsifiers.json`, generated 14 November 2026 11:42 UTC; **0 of 6 falsifiers triggered** (4 not triggered, 1 not yet decidable, 1 cannot check).

| ID | Falsifier | Threshold | Reading, 14 Nov 2026 | Status |
|----|-----------|-----------|----------------------|--------|
| F1 | Intents volume falls | 30d avg < $75M/day | $126.58M/day (15 Oct–13 Nov 2026) | Not triggered |
| F2 | Take or capture collapses | take < 3 bps or capture < 15% (60d) | net take 5.13 bps, capture 31.5% (15 Sep–13 Nov 2026) | Not triggered |
| F3 | HSP-029 not live by mid-2027 | not live on 30 Jun 2027 | deadline not reached | Not yet decidable |
| F4 | Buyback-wallet outflow | outflow > 5% of balance in 30d | outflow 0.00 NEAR; balance 2,280,770.08 NEAR; 768 receipts; inbound 287,393.71 NEAR (15 Oct–14 Nov 2026) | Not triggered |
| F5 | ETF outflows 4+ weeks | net outflows 4 consecutive weeks | no public ETF-flow endpoint | Cannot check |
| F6 | Net-revenue run-rate stalls | current run-rate < 2× run-rate 4 quarters ago | $22.28M/yr vs $1.41M/yr = 15.8× | Not triggered |

Note on F4: the balance/receipts figures above are the frozen dashboard snapshot (2,280,770.08 NEAR / 768 receipts). The fresh `buyback_wallet_30d.json` pull in this repo reads 2,281,071.57 NEAR / 767 receipts — the wallet accrues inbound transfers intraday, so the two differ by drift, not by error. Either reading leaves F4 untriggered (outflow 0.00 in both). The full-history census (§5) read all 3,408 receipts: only three outflows totalling 12,025 NEAR (0.5% of inflows) across the wallet's whole life, so the sink characterization holds beyond the 30-day window.

### The falsifiers, backtested

**Honesty label — read this first.** The F1/F2 kill lines were written in **November 2026**. Applying them to earlier dates is a **counterfactual**: "had these lines been watched since Intents launched, when would the thesis have died?" It is NOT a claim the thesis existed then.

**F1 — the volume floor, run backwards.** 30-day rolling mean of `data/intents_volume_daily.csv` (704 daily rows, 2024-12-10..2026-11-13), kill line $75M/day — the same definition as `scripts/check_falsifiers.py` F1. 675 windows (first window ends 2025-01-08). Data as of 2026-11-13.

- **473 of 675 windows (70%) below the floor.** By its own kill line, the thesis would have been dead for most of Intents' history.
- **Longest below-floor run: 304 consecutive windows, ending 2025-11-07.**
- **Last below-floor window: 2026-08-22 (30d mean $74.66M).**
- **First date after which the 30d mean never drops below again: 2026-08-23.** That is 83 consecutive above-floor windows through 2026-11-13.
- **Today: $126.58M/day = 1.69× the floor** (matches `data/falsifiers.json` exactly).

Monthly mean daily volume ($M): Dec-24 0.1, Jan-25 0.2, Feb 0.5, Mar 0.8, Apr 1.5, May 2.9, Jun 6.1, Jul 7.6, Aug 10.7, Sep 16.1, Oct 55.6, Nov 122.0, Dec 64.8, Jan-26 87.9, Feb 84.9, Mar 67.1, Apr 63.2, May 64.4, Jun 78.5, Jul 71.1, Aug 89.6, Sep 160.1, Oct 128.6, Nov (13d) 136.3.

**The takeaway:** the thesis is young — by its own standard it only became statable on **23 Aug 2026**, under three months before submission. That is a strength to state, not a weakness to hide: the verdict rests on the recent regime, and the backtest proves the kill line has teeth (it would have killed this thesis for most of its own history).

**F2 — the take/capture floor, monthly approximation.** Monthly net revenue (`intents_revenue_monthly.csv`, Aug 2025..Nov 2026) divided by monthly gross fees and monthly volume (both aggregated from the shipped daily DefiLlama CSVs). Kill line: take < 3 bps OR capture < 15%. This is a **monthly approximation** of the checker's 60-day rolling window, not an exact replication — do not present monthly figures as checker readings.

| Month | Net ($M) | Capture | Take (bps) | vs kill line |
|---|---|---|---|---|
| 2025-08 | 0.03 | 6.6% | 0.83 | TRIGGERED |
| 2025-09 | 0.03 | 4.0% | 0.59 | TRIGGERED |
| 2025-10 | 0.30 | 11.8% | 1.72 | TRIGGERED |
| 2025-11 | 0.66 | 8.5% | 1.80 | TRIGGERED |
| 2025-12 | 0.28 | 6.8% | 1.40 | TRIGGERED |
| 2026-01 | 0.53 | 11.9% | 1.93 | TRIGGERED |
| 2026-02 | 0.43 | 10.4% | 1.81 | TRIGGERED |
| 2026-03 | 0.40 | 11.0% | 1.90 | TRIGGERED |
| 2026-04 | 0.40 | 12.5% | 2.12 | TRIGGERED |
| 2026-05 | 0.82 | 27.4% | 4.13 | ok |
| 2026-06 | 0.94 | 30.3% | 4.01 | ok |
| 2026-07 | 0.65 | 20.0% | 2.97 | TRIGGERED (take leg only) |
| 2026-08 | 0.87 | 22.7% | 3.14 | ok |
| 2026-09 | 2.20 | 30.0% | 4.57 | ok |
| 2026-10 | 2.50 | 39.2% | 6.28 | ok |
| 2026-11 (MTD) | 0.75 | 31.3% | 4.71 | ok |

**Takeaway:** F2 would have been dead for 9 straight months (Aug 2025–Apr 2026), crossed into life in **May 2026**, and relapsed once in Jul 2026 on the take leg alone (2.97 bps vs the 3 bps line — a near-miss worth naming). The monetisation pillar is five months old, not a long-run fact.

- Intents volume **only follows** price (no lead at any lag in the lead/lag test), i.e. volume is a consequence of speculation, not of usage. **Status: not established either way on levels; on changes there is no correlation (repo test r = −0.098 best lag, placebo p = 0.592; PDF v3 r ≈ 0.01). The lead leg is unproven, which already weakens the claim.**
- Sub-hypothesis A fails: >80% of volume is one-off addresses. **Status: uncomputed (no JWT).**
- Sub-hypothesis B fails: Intents volume rises while on-chain activity falls (cannibalisation). **Status: failed on the evidence in §3 and §5.**
- The deflationary threshold sits so far above realistic volume growth that buybacks do not offset issuance in the bear or base scenarios. **Status: holds for bear and base (threshold 4.5× current volume at 2.5% issuance, 2.9× at 1.6%; Base year-5 volume reaches 0.44× / 0.69× of it). It does not hold in the bull case, whose year-5 volume (≈$470M/day) is 1.28× the 1.6% threshold — so "never" is too strong.**
- Fee capture collapses (the share of gross Intents fees reaching NEAR falls toward zero). **Status: not observed — October capture 39.2% per PDF v3, 31.5% over 60 days measured in-repo (checker F2). The capture is now a measured input, so this leg is nailed down as far as the data goes.**

## 8. What we couldn't compute

*(Honest list. Anything here is a gap, not a hidden assumption.)*

- Sub-hypothesis A (sticky volume): needs swapper-level data from the Intents Explorer API — no JWT obtained, and the partner-dashboard registration was not completed. If the API has no swapper field, this stays uncomputed.
- Intents volume series (G4/G5) canonical version: pending Intents Explorer API (JWT). The series used here is DefiLlama (`near-intents`, verified live), labelled as such.
- G3 full window: the 365-day contract-usage join needs 2.39 TB of BigQuery scan, over the 1 TB/month Sandbox quota. The shipped file is a 7-day window (5–11 Nov 2026) with no `unique_signers` column. G6 is a 30-day window for the same quota reason.
- HSP-029 status (proposed issuance cut 2.5% → 1.6%): PDF v3 records it as passed 2 Nov 2026, with Security Council ratification plus a ~90-day grace period still ahead (earliest effect ~Feb 2027). Do not cite it as in force.
- TVL: Fig5 quotes DefiLlama TVL $159.15M and stablecoins $132.03M (14 Nov 2026). Published figures conflict across sources (DefiLlama vs Rhea); the Fig5 numbers are DefiLlama's, labelled as such.
- F5 (ETF flows): no public ETF-flow endpoint is wired into this repo. The PDF itself states this reading is NOT re-runnable.
- Freshness: **resolved.** NEAR Lake was deprecated 24 Mar 2026, and the draft warned the dataset might stop updating. It has not: `MAX(block_date)` in `bigquery-public-data.crypto_near_mainnet_us.blocks` is **2026-11-11** (checked 12 Nov 2026, block height 224,135,609). The deprecation warning is outdated for this dataset. Re-check on every run with `queries/00-freshness.sql`.
- Two flagged outliers, not conclusions: daily active signers spiked to 177,510 on 10 Nov 2026 against ~77,000 on neighbouring days (G1); execution outcomes spiked to 14,335,195 on 15 Oct 2026, 15.72× that day's transactions (G6). Neither is explained yet.

## 9. Sources

- BigQuery `bigquery-public-data.crypto_near_mainnet_us` (queries in `queries/`, each file names its table). Sandbox projects: `near-thesis-514500` (freshness, G1, G2), `near-thesis-2` (G3, G6). No billing, no card. Series quoted from the 11 November 2026 pull, not re-run for this snapshot — see Appendix A.5.
- NEAR Intents Explorer API (JWT-gated; see `.env.example`) — not used; see §8.
- DefiLlama API (`api.llama.fi`) — Intents volume/fees, chain volumes, TVL/stablecoins. Volume is raw (unadjusted) — labelled as such on the dashboard.
- CoinGecko Keyless API — NEAR/SOL/ETH price history; NEAR price $3.33 and market cap $4,362,731,157 at 14 Nov 2026.
- Nearblocks API (read-only) — buyback-wallet balance and receipts (F4, full history).
- revenue.near.org — monthly net Intents revenue (F2, F6, emissions offset).
- Open Dev Data — developer comparison (secondary, cited).
- NEAR Intents postmortem ($3.8M exploit) — official postmortem.
- PDF v3, *NEAR Protocol Investment Thesis* (BusinessProfessional, 11 Nov 2026) — Nino's own dossier; figures from it are labelled "PDF v3" where used.
- Method note: the bottom-up structure (tokenomics → fee mechanism → threshold → what changes it) follows the method of published bottom-up NEAR research; the numbers, tests and conclusions are our own, recomputed from primary data.

## Appendix A. Method notes

### A.1. What was re-run on 14 November 2026

DefiLlama Intents volume and fees, CoinGecko NEAR price/market cap, revenue.near.org monthly net revenue, Nearblocks buyback-wallet snapshot and full history, `model/model.py` (`data/model_outputs.json`, 14 Nov 2026 11:42 UTC), and the falsifier checker (`data/falsifiers.json`, 14 Nov 2026 11:42 UTC). Every headline number in §§4–7 comes from this re-run.

### A.2. The threshold formula

V\* = annual issuance value / (365 × gross take × capture). Annual issuance value = total supply × issuance rate × price. At 14 Nov 2026: 1,311,421,234 × 2.5% × $3.33 = $109,175,818/yr, i.e. 89.82K NEAR/day of new issuance; at 1.6% the rate is 57.49K NEAR/day and the annual value $69,872,523. The threshold is price-dependent: the higher the NEAR price, the further the threshold.

### A.3. The placebo test (Fig9 / G5)

Method (repo, `model_outputs.json`): Pearson r of daily log changes, volume growth[t−k] vs price return[t], lags −7…+7; k > 0 means volume leads. Placebo: price log-returns shuffled across dates (1000 permutations, seed 20261113); the same lag scan (max |r| over lags −7…+7) re-run on each shuffle. Observed best |r| = 0.098 (lag −3); placebo mean max |r| = 0.107; p = 0.592. The observed best lag is not distinguishable from noise.

### A.4. What PDF v3 contributes

October-only windows (capture 39.2%, net take 6.28 bps, V\* $516M/$330M), the HSP-029 vote record, the reported on-chain fee decline ($5.18M → $1.27M), and the F5 "not re-runnable" note. All PDF v3 figures are labelled as such where used.

### A.5. Quoted vs re-run — read this before citing a BigQuery number

| Series | Status in this snapshot | Last pulled |
|--------|------------------------|-------------|
| G1 daily active accounts, G2 tx counts, G3 contract usage, G6 outcomes, freshness (`MAX(block_date)`) | **Quoted** from the 11 Nov 2026 BigQuery pull (11–12 Nov 2026); NOT re-run — no GCP credentials were available for this re-run | 11 Nov 2026 |
| G4/G5 Intents volume, fees, price, market cap, F1, F2, F6, emissions offset | **Re-run** 14 Nov 2026 | 14 Nov 2026 |
| F4 buyback wallet (30d + full history) | **Re-run** 14 Nov 2026 (Nearblocks, read-only) | 14 Nov 2026 |
| F3 HSP-029, F5 ETF flows | Documentary / cannot check (see §7) | — |

Any BigQuery figure in this document (G1–G3, G6, the −69.7% / −81.5% activity declines, the 12.3% `intents.near` share) is therefore a quoted 11 Nov reading, while every market, volume, fee, threshold and falsifier headline is a 14 Nov re-run. The snapshot date of this document is 14 November 2026.
