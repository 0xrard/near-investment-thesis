#!/usr/bin/env python3
"""
Generate the Chapter 4 figures (Figures 6-7) for the NEAR investment thesis
dashboard, from LIVE public data where applicable. Part of the repo build pipeline:

    python3 scripts/generate_chapter4_figures.py

re-fetches every endpoint and regenerates both PNGs in ../figures/.

Sources (all keyless / free, no credentials, no BigQuery):
  - revenue.near.org            (monthly net protocol revenue + the
                                  absoluteRevEmissions daily series, scraped
                                  from the server-rendered dashboard HTML, same
                                  approach as the thesis reproduce script)
  - Binance public data mirror  https://data-api.binance.vision  (NEARUSDT
                                  klines, monthly average price — used only to
                                  convert the Aug 2025-Jan 2026 USD revenue to
                                  NEAR, before the dashboard's daily NEAR
                                  series starts)

Figure content, annotations and layout follow Figures 6-7 of the v3 thesis PDF
(NEARProtocol_InvestmentThesis_BusinessProfessional_2026-11-11.pdf). The match
is about content / annotations / layout, not the PDF's white background:
styling here is the wireframe dark theme (#0a0a0a background, light-grey text,
terracotta #E07856 accent, teal series where the PDF uses teal).

Figure 6 method (monthly offset ratio = net revenue / token emissions):
  The dashboard's absoluteRevEmissions daily series gives cumulative
  revenueNear and emissionsNear in NEAR, so monthly offsets for Feb-Nov 2026
  are computed from its monthly deltas (on-chain NEAR, no price conversion).
  The series starts 2026-01-01 and its January revenue delta is 0 (a
  series-start artifact — January net revenue was $526K), so Aug 2025-Jan 2026
  use the independent computation instead: monthly net revenue in USD divided
  by that month's average Binance close, divided by monthly emissions at the
  dashboard's actual 87,604 NEAR/day. Both methods are printed for every month
  so the cross-check is visible; they agree to within ~0.5pp everywhere they
  overlap. Key values: Aug 2025 ~0.4%, Sep 2026 peak 25.2%, Nov 2026 17.7%
  (partial month, faded + '*').
Figure 7 method (deflation threshold model):
  A model chart, not a time series. Inputs are MEASURED and read from
  data/model_outputs.json (see _fig7_inputs): net take 4.72 bps (16 bps
  gross x 29.5% capture), NEAR price $3.72, mint 89,822 NEAR/day at 2.5%
  and 57,300 NEAR/day at 1.6% (HSP-029 target). V* markers at the model's
  $702M/day (2.5%) and $450M/day (1.6%); the formula
  V* = (i x S / 365 x P) / tau gives $708M and $453M, a touch above the
  markers because the model divides the issuance value ($121.0M) while the
  formula divides supply x price ($122.1M).

Requirements: python3 + requests + matplotlib. No API keys.
"""
import calendar
import datetime
import json
import math
import os
import re
import statistics
import sys
from pathlib import Path

import csv
import requests

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

UTC = datetime.timezone.utc
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "figures"
OUT.mkdir(parents=True, exist_ok=True)
FETCHED = datetime.datetime.now(UTC).strftime("%Y-%m-%d")
RETRIEVED_LABEL = datetime.datetime.strptime(FETCHED, "%Y-%m-%d").strftime("%d %b %Y")

# Shared captions file: every figure script merges its own captions here so
# the wireframe's figure captions refresh together with the PNGs on rebuild.
# Keyed by figure id ("fig1".."fig9"); "retrieved" is the last rebuild date.
# Caption text follows the v3 PDF captions, with the live values the figure
# itself computes substituted for the PDF's frozen values.
CAPTIONS_FILE = ROOT / "data" / "captions.json"
CAPTIONS = {}


def emit_captions(entries):
    """Merge this script's captions into the shared data/captions.json.

    Only this script's keys are updated, so a failed run leaves the other
    chapters' captions untouched (they keep their previous live values).
    """
    data = {}
    if CAPTIONS_FILE.exists():
        try:
            data = json.loads(CAPTIONS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
    data["retrieved"] = FETCHED
    data.update(entries)
    CAPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    CAPTIONS_FILE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"captions: wrote {len(entries)} entr{'y' if len(entries) == 1 else 'ies'} "
          f"to {CAPTIONS_FILE}")

# Shared stats file: the Chapter 1 stat-strip values, emitted alongside the
# Chapter 4 figures so the wireframe's 5-stat strip refreshes together with
# the figures on rebuild (same pattern as captions.json). Only this script
# writes stats.json, because it owns the one live-computed value (the
# current-month offset ratio); the other four values are read from the
# already-fetched data files, never re-fetched — except the market-cap rank,
# which lives in no repo data file and comes from one keyless CoinPaprika GET.
STATS_FILE = ROOT / "data" / "stats.json"
STATS = {}


def _market_cap_rank():
    """NEAR market-cap rank from CoinPaprika (keyless); None on failure.

    Rank lives in no repo data file (near_market.json is the CoinGecko
    snapshot, which only kept price / market cap / supplies), so it is
    fetched live here. A failure returns None with a warning instead of
    breaking the stats emission.
    """
    try:
        r = requests.get("https://api.coinpaprika.com/v1/tickers/near-near-protocol",
                         headers={"User-Agent": "near-thesis/1.0"}, timeout=15)
        r.raise_for_status()
        return int(r.json()["rank"])
    except Exception as exc:  # noqa: BLE001 - rank is best-effort
        print(f"  warning: CoinPaprika rank fetch failed ({exc}); rank=None",
              file=sys.stderr)
        return None


def _stats_values(offset_pct):
    """The 5 Chapter 1 stat-strip values, derived from live data files.

    price / market cap: data/near_market.json (CoinGecko snapshot).
    30d avg Intents volume: data/defillama_intents_dexs.json total30d / 30.
    P/S (gross): market cap / (DefiLlama Intents fees total30d x 12).
    Emissions offset: the current-month offset computed by fig6() (passed in).
    Rank: CoinPaprika (live; None on failure).
    """
    market = json.loads((ROOT / "data" / "near_market.json").read_text())
    dexs = json.loads((ROOT / "data" / "defillama_intents_dexs.json").read_text())
    fees = json.loads((ROOT / "data" / "defillama_intents_fees.json").read_text())
    price = float(market["price_usd"])
    mcap = float(market["market_cap_usd"])
    vol30d_avg = float(dexs["total30d"]) / 30.0
    ann_fees = float(fees["total30d"]) * 12.0
    ps = mcap / ann_fees
    # Cross-check against the model outputs (same inputs, independent path).
    model = json.loads((ROOT / "data" / "model_outputs.json").read_text())
    print(f"  stats cross-check: model P/F {model['p_to_fees']:.2f}x vs "
          f"computed {ps:.2f}x; model price ${model['inputs']['near_price_usd']:.2f} "
          f"vs market ${price:.2f}; model mcap ${model['hero_stats']['market_cap_usd']:,.0f} "
          f"vs market ${mcap:,.0f}")
    return {
        "retrieved": FETCHED,
        "price_usd": round(price, 2),
        "market_cap_usd": int(mcap),
        "market_cap_rank": _market_cap_rank(),
        "intents_volume_30d_avg_usd": int(round(vol30d_avg)),
        "emissions_offset_pct": round(float(offset_pct), 1),
        "ps_gross_fees": round(ps, 1),
    }


def emit_stats(entries):
    """Write the Chapter 1 stat-strip values to data/stats.json."""
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATS_FILE.write_text(json.dumps(entries, indent=2) + "\n")
    print(f"stats: wrote {len(entries)} keys to {STATS_FILE}")

# --- dark theme (wireframe: #0a0a0a + terracotta #E07856), as in Ch3 script ---
BG = "#0a0a0a"
TERRA = "#E07856"      # accent / Figure 7 mint-1.6% line
GREY = "#8a9199"       # secondary series / bars
LIGHT = "#e8e8e8"      # second line series / light text
TEXT = "#d4d4d4"       # axis labels, titles
MUTED = "#a8a8a8"      # tick labels, source lines
SPINE = "#555555"
TEAL = "#3DBDB0"       # Figure 7 revenue line (the PDF's "teal line")
TEAL_BAR = "#4FB3A4"   # Figure 6 bars
TEAL_PEAK = "#1E8A7A"  # Figure 6 peak bar (Sep 2026, darker as in the PDF)
RED = "#D64545"        # threshold line (Fig 6) / current marker (Fig 7)

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG,
    "savefig.facecolor": BG, "savefig.dpi": 150,
    "axes.edgecolor": SPINE, "axes.labelcolor": TEXT,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": TEXT, "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False,
})

# Dashboard actual daily emissions (NEAR/day), from revenue.near.org's
# on-chain accounting (PDF §3.1: 87,604 NEAR/day actually emitted).
DAILY_EMISSIONS = 87604.0

# Figure 7 model inputs — MEASURED, read from the model outputs (the model
# runs before the figures in rebuild.sh, so this file is always fresh).
# Net take = base gross take x capture (model inputs); V* markers come
# straight from the model's deflationary threshold, so Figure 7 can never
# disagree with THESIS.md section 6 again. The 1.6% marker scales the 2.5%
# threshold by the issuance ratio (1.6/2.5). Fallbacks are the same measured
# values (12 Nov 2026), used only if model_outputs.json is absent (cold
# start before the first model run).
def _fig7_inputs():
    fallback = {"take_bps": 4.72, "price": 3.72,
                "vstar_25": 702.0, "vstar_16": 450.0, "current_vol": 125.3}
    try:
        m = json.loads((ROOT / "data" / "model_outputs.json").read_text())
        inp = m["inputs"]
        take = (float(inp["base_take_rate_bps"]) / 10000.0
                * float(inp["fee_capture_rate"]))
        v25 = float(m["deflationary_threshold"]
                    ["daily_volume_usd_by_take_rate_bps"]
                    [str(int(inp["base_take_rate_bps"]))]) / 1e6
        return {"take_bps": take * 10000.0,
                "price": float(inp["near_price_usd"]),
                "vstar_25": v25,
                "vstar_16": v25 * 1.6 / 2.5,
                "current_vol": float(inp["daily_intents_volume_usd"]) / 1e6}
    except Exception:
        return fallback


_FIG7 = _fig7_inputs()
TAKE_BPS = _FIG7["take_bps"]   # net take rate, basis points (measured)
PRICE = _FIG7["price"]         # NEAR price, USD (model inputs)
MINT_25 = 89822.0      # NEAR/day at 2.5% max inflation (formula: S*i/365)
MINT_16 = 57300.0      # NEAR/day at 1.6% HSP-029 target (HSP-029: 89.5K -> 57.3K)
VSTAR_25 = _FIG7["vstar_25"]   # $M/day, model V* at 2.5% (measured inputs)
VSTAR_16 = _FIG7["vstar_16"]   # $M/day, model V* at 1.6% (scaled by 1.6/2.5)
CURRENT_VOL = _FIG7["current_vol"]  # $M/day, current 30-day run-rate (model)


def get(url, timeout=30):
    r = requests.get(url, headers={"User-Agent": "near-thesis/1.0"}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def style_ax(ax):
    ax.grid(axis="y", color="white", alpha=0.08, lw=0.8)
    ax.tick_params(labelsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(SPINE)
    ax.spines["bottom"].set_color(SPINE)


def source_line(fig, text):
    fig.text(0.01, 0.005, text, fontsize=8, color=MUTED)


def _revenue_monthly_csv():
    """Monthly net revenue from the shipped CSV, or None when missing.

    Returns {(year, month): (value, cumulative)}, the same shape as
    _revenue_monthly(rsc). Written by scripts/fetch.py on a full rebuild.
    """
    csv_path = ROOT / "data" / "intents_revenue_monthly.csv"
    if not csv_path.exists():
        return None
    out = {}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            out[(int(row["year"]), int(row["month"]))] = (
                float(row["net_revenue_usd"]), float(row["cumulative_usd"]))
    return out or None


def _abs_rev_emissions_csv():
    """Daily cumulative (revenueNear, emissionsNear) from the shipped CSV.

    Returns a list of (date, revenue_near, emissions_near) sorted by date,
    the same shape as _abs_rev_emissions(rsc), or None when missing.
    """
    csv_path = ROOT / "data" / "intents_revenue_daily.csv"
    if not csv_path.exists():
        return None
    out = []
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            out.append((datetime.date.fromisoformat(row["date"]),
                        float(row["cumulative_revenue_near"]),
                        float(row["cumulative_emissions_near"])))
    out.sort()
    return out or None


def _revenue_rsc():
    """Server-rendered dashboard HTML -> decoded RSC payload text."""
    html = requests.get("https://revenue.near.org",
                        headers={"User-Agent": "near-thesis/1.0"}, timeout=30).text
    chunks = re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', html)
    return "".join(chunks).encode().decode("unicode_escape", errors="replace")


def _revenue_monthly(rsc):
    """Monthly net protocol revenue (USD): {(year, month): (value, cumulative)}."""
    rows = re.findall(r'\{"date":"([^"]+)","value":([\d.]+),"cumulative":([\d.]+)\}', rsc)
    if not rows:
        raise RuntimeError("revenue.near.org: no monthly revenue rows parsed")
    mon = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
           "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
    out = {}
    for label, value, cum in rows:
        m, y = label.split()
        out[(2000 + int(y.strip("'")), mon[m])] = (float(value), float(cum))
    return out


def _abs_rev_emissions(rsc):
    """Daily cumulative (revenueNear, emissionsNear) from absoluteRevEmissions.

    Returns a list of (date, revenue_near, emissions_near) sorted by date.
    """
    m = re.search(r'"absoluteRevEmissions":\[(.*?)\]', rsc, re.S)
    if not m:
        raise RuntimeError("revenue.near.org: no absoluteRevEmissions array parsed")
    arr = json.loads("[" + re.sub(r',\{"date[^\}]*$', "", m.group(1)) + "]")
    out = [(datetime.date.fromisoformat(e["date"]), float(e["revenueNear"]),
            float(e["emissionsNear"])) for e in arr]
    out.sort()
    return out


def _binance_monthly_avg():
    """Monthly average NEARUSDT daily close: {(year, month): avg price}."""
    kl = get("https://data-api.binance.vision/api/v3/klines"
             "?symbol=NEARUSDT&interval=1d&limit=1000")
    by_month = {}
    for k in kl:
        d = datetime.datetime.fromtimestamp(int(k[0]) / 1000, UTC)
        by_month.setdefault((d.year, d.month), []).append(float(k[4]))
    return {k: statistics.mean(v) for k, v in by_month.items()}


def _monthly_offsets():
    """Monthly offset % (net revenue / token emissions) for Aug 2025-Nov 2026.

    Returns (months, offsets, methods) where months is a list of (year, month),
    offsets a list of percentages, and methods a list of 'dashboard' or
    'computed' per month. Dashboard deltas (on-chain NEAR) are used where the
    daily series covers the month; the independent computation (USD revenue /
    monthly avg price / (87,604 x days)) is used for Aug 2025-Jan 2026, because
    the daily series starts 2026-01-01 and its January revenue delta is 0
    (series-start artifact).
    """
    # Prefer the shipped files (written by scripts/fetch.py on a full
    # rebuild); fall back to the live scrape when they are missing.
    net = _revenue_monthly_csv()
    daily = _abs_rev_emissions_csv()
    if net is None or daily is None:
        rsc = _revenue_rsc()
        net = _revenue_monthly(rsc)
        daily = _abs_rev_emissions(rsc)
    else:
        print("  revenue: using shipped data/intents_revenue_monthly.csv + "
              "data/intents_revenue_daily.csv")
    avg_price = _binance_monthly_avg()

    # Dashboard monthly deltas from the daily cumulative series.
    dash = {}
    prev = None
    for d, rev, emi in daily:
        if prev is not None:
            key = (d.year, d.month)
            r, e = dash.get(key, (0.0, 0.0))
            dash[key] = (r + (rev - prev[1]), e + (emi - prev[2]))
        prev = (d, rev, emi)

    now = datetime.datetime.now(UTC)
    months = sorted(net.keys())
    offsets, methods = [], []
    for (y, mo) in months:
        # Independent computation (always available): USD / avg price / emissions.
        days = calendar.monthrange(y, mo)[1]
        if (y, mo) == (now.year, now.month):
            days = now.day  # partial current month
        price = avg_price[(y, mo)]
        computed = (net[(y, mo)][0] / price) / (DAILY_EMISSIONS * days) * 100
        # Dashboard delta, when the daily series covers the month with real
        # revenue movement (Jan 2026 delta is 0 — series-start artifact).
        d = dash.get((y, mo))
        if d is not None and d[0] > 0 and d[1] > 0 and (y, mo) >= (2026, 2):
            offsets.append(d[0] / d[1] * 100)
            methods.append("dashboard")
        else:
            offsets.append(computed)
            methods.append("computed")
        print(f"  offset {y}-{mo:02d}: {offsets[-1]:.2f}% [{methods[-1]}] "
              f"(computed {computed:.2f}%)")
    return months, offsets, methods


# ---------------------------------------------------------------- Figure 6 ---
def fig6():
    """Monthly net revenue as a % of token emissions, since the fee switch.

    Matches PDF Figure 6: monthly bars with whole-% labels, the September
    2026 peak bar darker, and a dashed red 100% line labelled as the
    deflation threshold. November 2026 is a partial month: faded bar + '*'.
    """
    months, offsets, methods = _monthly_offsets()
    labels = [datetime.date(y, m, 1).strftime("%b %y") for (y, m) in months]
    now = datetime.datetime.now(UTC)
    partial = months[-1] == (now.year, now.month)
    if partial:
        labels[-1] = labels[-1] + "*"
    peak_i = max(range(len(offsets)), key=lambda i: offsets[i])

    x = list(range(len(months)))
    fig, ax = plt.subplots(figsize=(10, 5))
    colors = [TEAL_PEAK if i == peak_i else TEAL_BAR for i in range(len(months))]
    bars = ax.bar(x, offsets, width=0.62, color=colors)
    if partial:
        bars[-1].set_alpha(0.45)
    for i, v in enumerate(offsets):
        ax.text(i, v + 2.5, f"{v:.0f}%", ha="center", va="bottom",
                fontsize=9, color=TEXT)
    ax.axhline(100, color=RED, lw=1.2, ls="--", alpha=0.9)
    ax.text(0.1, 104, "Deflation threshold: revenue = 100% of emissions",
            fontsize=9, color=RED, ha="left", va="bottom")
    ax.set_ylim(0, 118)
    ax.set_ylabel("Net revenue as % of token emissions", fontsize=11)
    ax.set_title("Net protocol revenue as a percentage of token emissions, "
                 "monthly since the fee switch", fontsize=12, color=TEXT, pad=10)
    ax.set_xticks(x[1::2])
    ax.set_xticklabels(labels[1::2], fontsize=9)
    style_ax(ax)
    src = f"Source: revenue.near.org (on-chain derived), retrieved {FETCHED}"
    if partial:
        src += f"  (* {labels[-1].replace(chr(42), '').strip()} is a partial month)"
    source_line(fig, src)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig6_offset_ratio.png")
    plt.close(fig)

    sep = months.index((2026, 9))
    nov = months.index((2026, 11))
    print(f"fig6: {len(months)} months {labels[0]}..{labels[-1]}; "
          f"Aug 2025 {offsets[0]:.2f}%, Sep 2026 peak {offsets[sep]:.2f}%, "
          f"Nov 2026 {offsets[nov]:.2f}% (partial); methods: "
          f"{methods.count('dashboard')} dashboard, {methods.count('computed')} computed")
    # Latest-month offset feeds data/stats.json (the Chapter 1 stat strip).
    STATS["emissions_offset_pct"] = offsets[-1]
    peak_label = datetime.date(*months[peak_i], 1).strftime("%B %Y")
    latest_label = datetime.date(*months[-1], 1).strftime("%B %Y")
    latest_txt = f"{latest_label} to date" if partial else latest_label
    CAPTIONS["fig6"] = (
        "Figure 6: Net protocol revenue as a percentage of token emissions, "
        "monthly since the fee switch. "
        f"{peak_label} peak: {offsets[peak_i]:.1f}%; "
        f"{latest_txt}: {offsets[-1]:.1f}%. "
        "The 100% line is the deflation threshold. Source: revenue.near.org "
        f"(on-chain derived), retrieved {FETCHED}."
    )


# ---------------------------------------------------------------- Figure 7 ---
def fig7():
    """The deflation threshold model (PDF §3.3, Figure 7).

    Model chart from the MEASURED inputs (see _fig7_inputs, read from
    data/model_outputs.json): net take rate 4.72 bps (16 bps gross x 29.5%
    capture), NEAR $3.72, mint 89,822 NEAR/day at 2.5% and 57,300 NEAR/day
    at 1.6%. Teal line = NEAR removed/day via revenue; dashed lines = the
    two mints; X markers = the two V* intersections; red dot = the current
    $125M/day run-rate.
    """
    take = TAKE_BPS / 1e4
    # NEAR removed per $M of daily volume, in thousands of NEAR/day.
    per_m = 1e6 * take / PRICE / 1e3
    xs = [0.0, 800.0]
    ys = [x * per_m for x in xs]
    # Formula cross-check: same inputs through V* = (i x S / 365 x P) / tau.
    # It lands a touch above the model markers ($708M vs $702M) because the
    # model divides the issuance VALUE ($121.0M) while the formula divides
    # supply x price ($122.1M) — same inputs, different rounding base.
    supply = 1311.4e6
    v25 = supply * 0.025 / 365 * PRICE / take / 1e6
    v16 = supply * 0.016 / 365 * PRICE / take / 1e6
    print(f"fig7: formula V* = ${v25:.1f}M/day at 2.5%, ${v16:.1f}M/day at 1.6% "
          f"(model markers ${VSTAR_25:.0f}M / ${VSTAR_16:.0f}M); removed/day per $1M volume = "
          f"{per_m * 1e3:.0f} NEAR")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(xs, ys, color=TEAL, lw=2.0,
            label=f"NEAR removed/day via revenue (take = {TAKE_BPS:.2f} bps net)")
    ax.axhline(MINT_25 / 1e3, color=LIGHT, lw=1.3, ls="--",
               label="Mint @ 2.5% inflation: 90K NEAR/day")
    ax.axhline(MINT_16 / 1e3, color=TERRA, lw=1.3, ls="--",
               label="Mint @ 1.6% (HSP-029 target): 57K NEAR/day")
    # V* intersections (model values, on their mint lines).
    ax.plot([VSTAR_25], [MINT_25 / 1e3], marker="x", ms=10, mew=2.5,
            color=LIGHT, linestyle="none")
    ax.plot([VSTAR_16], [MINT_16 / 1e3], marker="x", ms=10, mew=2.5,
            color=TERRA, linestyle="none")
    bbox = dict(facecolor=BG, alpha=0.9, edgecolor="none", pad=1.5)
    ax.text(VSTAR_25 - 8, MINT_25 / 1e3 - 14,
            f"V* @ 2.5%: ${VSTAR_25:.0f}M/day\n({VSTAR_25 / CURRENT_VOL:.1f}x current volume)",
            fontsize=9, color=TEXT, ha="right", va="top", bbox=bbox)
    ax.text(VSTAR_16 - 8, MINT_16 / 1e3 - 13,
            f"V* @ 1.6%: ${VSTAR_16:.0f}M/day\n({VSTAR_16 / CURRENT_VOL:.1f}x current volume)",
            fontsize=9, color=TEXT, ha="right", va="top", bbox=bbox)
    # Current run-rate: label above-LEFT of the dot so it cannot collide with
    # the V* @ 1.6% label (which sits below-left of its X marker).
    cur_y = CURRENT_VOL * per_m
    ax.plot([CURRENT_VOL], [cur_y], marker="o", ms=7, color=RED, linestyle="none")
    ax.text(CURRENT_VOL - 10, cur_y + 6,
            f"Current: ${CURRENT_VOL:.0f}M/day\n{cur_y:.0f}K NEAR/day removed\n({cur_y / (MINT_25 / 1e3) * 100:.0f}% of mint)",
            fontsize=9, color=RED, ha="right", va="bottom", bbox=bbox)
    ax.set_xlim(0, 800)
    ax.set_ylim(0, 125)
    ax.set_xlabel("NEAR Intents daily volume ($M/day)", fontsize=11)
    ax.set_ylabel("NEAR per day (thousands)", fontsize=11)
    ax.set_title("The deflation threshold model", fontsize=12, color=TEXT, pad=10)
    ax.legend(loc="lower right", fontsize=9, labelcolor=TEXT)
    style_ax(ax)
    source_line(fig, f"Model inputs (measured 12 Nov 2026): net take {TAKE_BPS:.2f} bps "
                     f"(16 bps gross x 29.5% capture), NEAR ${PRICE:.2f}, "
                     f"mint {MINT_25:,.0f} NEAR/day (2.5%) / {MINT_16:,.0f} (1.6%). "
                     f"Retrieved {FETCHED}")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig7_deflation_threshold.png")
    plt.close(fig)
    print(f"fig7: V* markers at ${VSTAR_25:.0f}M/day (2.5%, mint {MINT_25 / 1e3:.1f}K) "
          f"and ${VSTAR_16:.0f}M/day (1.6%, mint {MINT_16 / 1e3:.1f}K); "
          f"current {CURRENT_VOL:.0f}M/day -> {cur_y:.1f}K NEAR/day removed")
    # Model chart: inputs are read from the model outputs (see _fig7_inputs),
    # so the caption re-states the measured values (it only moves with a
    # model re-run).
    CAPTIONS["fig7"] = (
        "Figure 7: The deflation threshold model. The teal line is NEAR removed "
        f"per day via revenue at the measured net take rate ({TAKE_BPS:.2f} bps); "
        "dashed lines are the mint at 2.5% and at the 1.6% HSP-029 target. "
        f"V* is ${VSTAR_25:.0f}M/day at 2.5% and ${VSTAR_16:.0f}M/day at 1.6% "
        f"({VSTAR_16 / CURRENT_VOL:.1f}x current volume). Sources: DefiLlama, "
        f"NEAR RPC, CoinPaprika, revenue.near.org; retrieved {FETCHED}."
    )


def main():
    jobs = [("fig6_offset_ratio.png", fig6),
            ("fig7_deflation_threshold.png", fig7)]
    failed = []
    for name, fn in jobs:
        try:
            fn()
        except Exception as exc:
            failed.append(name)
            print(f"FAILED {name}: {exc}", file=sys.stderr)
    for name, _ in jobs:
        p = OUT / name
        if name in failed:
            # Never print OK for a file this run did not generate: a stale
            # file still on disk is KEPT, not OK.
            if p.exists():
                print(f"KEPT  {p} {p.stat().st_size} (previous file, not regenerated)",
                      file=sys.stderr)
            else:
                print(f"MISS  {p}", file=sys.stderr)
        else:
            print("OK   ", p, p.stat().st_size if p.exists() else "")
    if CAPTIONS:
        emit_captions(CAPTIONS)
    if "emissions_offset_pct" in STATS:
        try:
            emit_stats(_stats_values(STATS["emissions_offset_pct"]))
        except Exception as exc:  # noqa: BLE001 - stats must not fail figures
            print(f"stats: FAILED ({exc}); figures unaffected", file=sys.stderr)
    else:
        print("stats: skipped (fig6 did not produce an offset)", file=sys.stderr)
    if failed:
        print(f"{len(failed)} figure(s) failed: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)
    print("Both Chapter 4 figures written to", OUT)


if __name__ == "__main__":
    main()
