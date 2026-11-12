#!/usr/bin/env python3
"""
Generate the Chapter 3 figures (Figures 1-5) for the NEAR investment thesis
dashboard, from LIVE public data. Part of the repo build pipeline:

    python3 scripts/generate_chapter3_figures.py

re-fetches every endpoint and regenerates all five PNGs in ../figures/.

Sources (all keyless / free, no credentials, no BigQuery):
  - Binance public data mirror  https://data-api.binance.vision  (NEARUSDT klines)
  - DefiLlama                    https://api.llama.fi             (Intents volume/fees, chain TVL)
  - DefiLlama stablecoins       https://stablecoins.llama.fi     (stablecoin circulating)
  - NearBlocks                  https://api.nearblocks.io        (daily L1 activity)
  - revenue.near.org            (monthly net protocol revenue, scraped from the
                                  server-rendered dashboard HTML, same approach as
                                  the thesis reproduce script)

Figure content, annotations and layout follow Figures 1-5 of the v3 thesis PDF
(NEARProtocol_InvestmentThesis_BusinessProfessional_2026-11-11.pdf). The match
is about content / annotations / layout, not the PDF's white background:
styling here is the wireframe dark theme (#0a0a0a background, terracotta
#E07856 primary series, light-grey text).

Event annotation dates: the PDF gives month precision only for the fee switch
(Oct 2025) and the buyback wallet (Mar 2026); the plotted lines use
2025-10-20 and 2026-03-31 as the best-estimate dates and are labelled with the
month only, exactly as in the PDF. The NRR ETF launch (29 Sep 2026) and the
HSP-029 vote (2 Nov 2026) are exact dates from the PDF text.

Requirements: python3 + requests + matplotlib. No API keys.
"""
import datetime
import json
import math
import os
import re
import statistics
import sys
from pathlib import Path

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

# --- dark theme (wireframe: #0a0a0a + terracotta #E07856) ---
BG = "#0a0a0a"
TERRA = "#E07856"      # primary data series
GREY = "#8a9199"       # secondary series / bars
LIGHT = "#e8e8e8"      # second line series / light text
TEXT = "#d4d4d4"       # axis labels, titles
MUTED = "#a8a8a8"      # tick labels, source lines
SPINE = "#555555"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": BG,
    "savefig.facecolor": BG, "savefig.dpi": 150,
    "axes.edgecolor": SPINE, "axes.labelcolor": TEXT,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "text.color": TEXT, "font.family": "DejaVu Sans",
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False,
})

# Event annotation dates (see header note for precision).
FEE_SWITCH = datetime.datetime(2025, 10, 20, tzinfo=UTC)
BUYBACK_WALLET = datetime.datetime(2026, 3, 31, tzinfo=UTC)
NRR_ETF = datetime.datetime(2026, 9, 29, tzinfo=UTC)
HSP029 = datetime.datetime(2026, 11, 2, tzinfo=UTC)


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


def ma(values, n):
    """Simple moving average; None for the first n-1 points."""
    out = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def _plot_ma(ax, dates, values, **kw):
    xs = [d for d, v in zip(dates, values) if v is not None]
    ys = [v for v in values if v is not None]
    ax.plot(xs, ys, **kw)


# ---------------------------------------------------------------- Figure 1 ---
def fig1():
    """NEAR/USDT daily closes, 500 days, with 50-/200-day MAs and event lines.

    Matches PDF Figure 1: dark price line, 50-day MA solid, 200-day MA
    dashed, 4 dotted event lines with staggered top labels.
    """
    kl = get("https://data-api.binance.vision/api/v3/klines"
             "?symbol=NEARUSDT&interval=1d&limit=1000")
    dates = [datetime.datetime.fromtimestamp(int(k[0]) / 1000, UTC) for k in kl]
    closes = [float(k[4]) for k in kl]
    d, c = dates[-500:], closes[-500:]
    ma50 = ma(closes, 50)[-500:]
    ma200 = ma(closes, 200)[-500:]
    ret365 = (closes[-1] / closes[-366] - 1) * 100

    top = max(8.0, math.ceil(max(c) * 1.15))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(d, c, color=TERRA, lw=1.2, label="NEAR/USDT close")
    _plot_ma(ax, d, ma50, color=LIGHT, lw=1.2, label="50-day MA")
    _plot_ma(ax, d, ma200, color=GREY, lw=1.1, ls="--", label="200-day MA")
    ax.set_ylim(0, top)
    ax.set_yticks(range(0, int(top) + 1))
    ax.set_ylabel("Price (USDT)", fontsize=11)
    ax.set_title("NEAR/USDT daily close — 500 days, with 50- and 200-day moving averages",
                 fontsize=12, color=TEXT, pad=10)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 3, 5, 7, 9, 11)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    # Room past the last data point so the HSP-029 label fits (as in the PDF).
    ax.set_xlim(d[0], d[-1] + datetime.timedelta(days=18))
    for ev, label, frac in ((FEE_SWITCH, "Fee switch live (Oct 2025)", 0.975),
                            (BUYBACK_WALLET, "Buyback wallet live (Mar 2026)", 0.90),
                            (NRR_ETF, "NRR ETF launch (Sep 29)", 0.975),
                            (HSP029, "HSP-029 cut passed (Nov 2)", 0.90)):
        ax.axvline(ev, color=GREY, lw=0.9, ls=":", alpha=0.8)
        ax.text(ev, top * frac, "  " + label, fontsize=9, color=TEXT,
                va="center", ha="left")
    ax.legend(loc="upper left", fontsize=10, labelcolor=TEXT)
    style_ax(ax)
    source_line(fig, f"Source: Binance data-api (data-api.binance.vision), retrieved {FETCHED}")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig1_price.png")
    plt.close(fig)
    print(f"fig1: last close ${closes[-1]:.2f} on {dates[-1].date()}, "
          f"365d return {ret365:+.1f}%, window {d[0].date()}..{d[-1].date()}, "
          f"MA50 {ma50[-1]:.2f}, MA200 {ma200[-1]:.2f}, max close ${max(c):.2f}")
    CAPTIONS["fig1"] = (
        "Figure 1: NEAR/USDT daily closes over 500 days with 50- and 200-day "
        "moving averages. Event lines mark the fee switch ramp, buyback wallet "
        "creation, the Bitwise NRR ETF launch, and the HSP-029 vote. Source: "
        f"Binance data-api (data-api.binance.vision), retrieved {FETCHED}."
    )


# ---------------------------------------------------------------- Figure 2 ---
def fig2():
    """NEAR Intents daily volume (grey) + 30-day moving average (terracotta).

    Matches PDF Figure 2, including the 'Fee switch live / Oct 2025'
    text annotation where volume takes off.
    """
    v = get("https://api.llama.fi/summary/dexs/near-intents?dataType=dailyVolume")
    chart = v["totalDataChart"]  # [unix seconds, volume USD]
    dates = [datetime.datetime.fromtimestamp(x[0], UTC) for x in chart]
    vols = [x[1] / 1e6 for x in chart]  # $M/day
    ma30 = ma(vols, 30)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, vols, color=GREY, lw=0.7, label="Daily volume")
    _plot_ma(ax, dates, ma30, color=TERRA, lw=2.0, label="30-day moving average")
    # Annotation exactly as in the PDF (text only, no vertical line).
    idx = min(range(len(dates)), key=lambda i: abs((dates[i] - FEE_SWITCH).days))
    y_at = ma30[idx] or 0.0
    ax.text(FEE_SWITCH, max(y_at + 12, 30), "Fee switch live\nOct 2025",
            fontsize=9, color=TEXT, ha="left", va="bottom",
            bbox=dict(facecolor=BG, alpha=0.9, edgecolor="none", pad=1.5))
    top = max(320.0, math.ceil(max(vols) * 1.08 / 50) * 50)
    ax.set_ylim(0, top)
    ax.set_yticks(range(0, int(top) + 1, 50))
    ax.set_ylabel("NEAR Intents volume ($M/day)", fontsize=11)
    ax.set_title("NEAR Intents daily volume and 30-day moving average",
                 fontsize=12, color=TEXT, pad=10)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_xlim(datetime.datetime(2025, 1, 1, tzinfo=UTC),
                dates[-1] + datetime.timedelta(days=5))
    ax.legend(loc="upper left", fontsize=10, labelcolor=TEXT)
    style_ax(ax)
    source_line(fig, f"Source: DefiLlama summary/dexs/near-intents, retrieved {FETCHED}")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig2_intents_volume.png")
    plt.close(fig)

    alltime = v["totalAllTime"] / 1e9
    avg30 = sum(vols[-30:]) / 30
    monthly = {}
    for dt_, val in zip(dates, vols):
        monthly[(dt_.year, dt_.month)] = monthly.get((dt_.year, dt_.month), 0.0) + val
    print(f"fig2: all-time ${alltime:.1f}B, 30d avg ${avg30:.0f}M/day, "
          f"Sep 2026 ${monthly.get((2026, 9), 0) / 1e3:.2f}B, "
          f"Oct 2026 ${monthly.get((2026, 10), 0) / 1e3:.2f}B, "
          f"last 30d MA ${ma30[-1]:.0f}M/day")
    CAPTIONS["fig2"] = (
        "Figure 2: NEAR Intents daily volume (gray) and 30-day moving average "
        f"(teal). All-time ${alltime:.1f}B; 30-day average ${avg30:.0f}M/day. "
        f"Source: DefiLlama summary/dexs/near-intents, retrieved {FETCHED}."
    )


# ---------------------------------------------------------------- Figure 3 ---
def _revenue_monthly():
    """Monthly net protocol revenue from revenue.near.org (RSC payload scrape)."""
    html = requests.get("https://revenue.near.org",
                        headers={"User-Agent": "near-thesis/1.0"}, timeout=30).text
    chunks = re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', html)
    rsc = "".join(chunks).encode().decode("unicode_escape", errors="replace")
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


def fig3():
    """Monthly gross Intents fees (grey bars), net protocol revenue (terracotta
    bars), capture rate (line, right axis). Matches PDF Figure 3."""
    fees = get("https://api.llama.fi/summary/fees/near-intents?dataType=dailyFees")
    gross_m = {}
    for ts, val in fees["totalDataChart"]:
        dt_ = datetime.datetime.fromtimestamp(ts, UTC)
        k = (dt_.year, dt_.month)
        gross_m[k] = gross_m.get(k, 0.0) + val
    net = _revenue_monthly()
    months = sorted(net.keys())
    gross = [gross_m.get(k, 0.0) / 1e3 for k in months]   # $K
    netv = [net[k][0] / 1e3 for k in months]              # $K
    capture = [n / g * 100 if g > 0 else 0.0 for n, g in zip(netv, gross)]
    labels = [datetime.date(y, m, 1).strftime("%b '%y") for (y, m) in months]
    partial = months[-1] == (datetime.datetime.now(UTC).year,
                             datetime.datetime.now(UTC).month)
    if partial:
        labels[-1] = labels[-1] + "*"

    x = list(range(len(months)))
    w = 0.38
    fig, ax = plt.subplots(figsize=(10, 5))
    bars_g = ax.bar([i - w / 2 for i in x], gross, width=w, color=GREY,
                    label="Gross Intents fees ($K)")
    bars_n = ax.bar([i + w / 2 for i in x], netv, width=w, color=TERRA,
                    label="Net protocol revenue ($K)")
    if partial:  # current month is incomplete: fade its bars
        bars_g[-1].set_alpha(0.45)
        bars_n[-1].set_alpha(0.45)
    ax.set_ylabel("$ thousands / month", fontsize=11)
    top = max(8000.0, math.ceil(max(gross) * 1.3 / 2000) * 2000)
    ax.set_ylim(0, top)
    ax.set_title("Monthly gross Intents fees, net protocol revenue, and capture rate",
                 fontsize=12, color=TEXT, pad=10)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=9)
    ax2 = ax.twinx()
    ax2.plot(x, capture, color=LIGHT, lw=1.5, marker="o", ms=4,
             label="Capture rate (net/gross, %)")
    ax2.set_ylabel("Capture rate (%)", fontsize=11, color=TEXT)
    ax2.set_ylim(0, 100)
    ax2.tick_params(labelsize=9, colors=MUTED)
    ax2.grid(False)
    for s in ("top",):
        ax2.spines[s].set_visible(False)
    ax2.spines["right"].set_color(SPINE)
    handles = [bars_g, bars_n, ax2.lines[0]]
    ax.legend(handles, [h.get_label() for h in handles],
              loc="upper left", fontsize=10, labelcolor=TEXT)
    style_ax(ax)
    src = f"Sources: DefiLlama; revenue.near.org, retrieved {FETCHED}"
    if partial:
        src += f"  (* {labels[-1].replace(chr(42), '').strip()} is a partial month)"
    source_line(fig, src)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig3_fee_revenue.png")
    plt.close(fig)

    oct_i = months.index((2026, 10))
    cum_net = net[months[-1]][1]
    lifetime_cap = cum_net / (fees["totalAllTime"]) * 100
    print(f"fig3: Oct 2026 gross ${gross[oct_i]:,.0f}K, net ${netv[oct_i]:,.0f}K, "
          f"capture {capture[oct_i]:.1f}%; cumulative net ${cum_net / 1e6:.2f}M, "
          f"gross all-time ${fees['totalAllTime'] / 1e6:.1f}M, "
          f"lifetime capture {lifetime_cap:.1f}%; months {labels[0]}..{labels[-1]}")
    # Caption highlights the latest complete month (October 2026 at PDF time).
    now_ym = (datetime.datetime.now(UTC).year, datetime.datetime.now(UTC).month)
    latest_i = max(i for i, k in enumerate(months) if k < now_ym)
    latest_label = datetime.date(*months[latest_i], 1).strftime("%B %Y")
    CAPTIONS["fig3"] = (
        "Figure 3: Monthly gross Intents fees (gray bars), net protocol revenue "
        "(teal bars), and capture rate (line, right axis). "
        f"{latest_label}: ${gross[latest_i] / 1e3:.2f}M gross, "
        f"${netv[latest_i] / 1e3:.2f}M net, {capture[latest_i]:.1f}% captured. "
        f"Sources: DefiLlama; revenue.near.org, retrieved {FETCHED}."
    )


# ---------------------------------------------------------------- Figure 4 ---
def fig4():
    """NEAR L1 daily transactions (left) and daily active accounts (right),
    400 days. Matches PDF Figure 4 (two side-by-side panels, bold panel titles).
    Falls back to a Nov 1-10 comparison chart from the PDF's verified values
    if NearBlocks is unreachable.
    """
    try:
        act = get("https://api.nearblocks.io/v1/charts", timeout=45)["charts"]
    except Exception as exc:
        print(f"fig4: NearBlocks unreachable ({exc}) — using PDF fallback values")
        return _fig4_fallback()
    rows = []
    for x in act:
        d = datetime.datetime.fromisoformat(x["date"].replace("Z", "+00:00")).date()
        rows.append((d, int(float(x["txns"])), int(float(x["active_accounts"]))))
    rows.sort()
    end = rows[-1][0]
    start = end - datetime.timedelta(days=399)
    sel = [r for r in rows if start <= r[0] <= end]
    dates = [datetime.datetime.combine(r[0], datetime.time()) for r in sel]
    tx = [r[1] / 1e6 for r in sel]
    ac = [r[2] / 1e3 for r in sel]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5), sharex=True)
    ax1.plot(dates, tx, color=TERRA, lw=1.0)
    ax1.set_title("Daily transactions (M/day)", fontsize=11, fontweight="bold", color=TEXT)
    ax1.set_ylabel("Million txns/day", fontsize=11)
    ax1.set_ylim(0, max(5.0, math.ceil(max(tx) * 1.1)))
    ax2.plot(dates, ac, color=LIGHT, lw=1.0)
    ax2.set_title("Daily active accounts (K/day)", fontsize=11, fontweight="bold", color=TEXT)
    ax2.set_ylabel("Thousand accounts/day", fontsize=11)
    ax2.set_ylim(0, max(650.0, math.ceil(max(ac) / 100) * 100))
    for ax in (ax1, ax2):
        ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
        style_ax(ax)
    fig.suptitle("NEAR L1 activity — 400 days", fontsize=12, color=TEXT, y=0.98)
    source_line(fig, f"Source: NearBlocks /v1/charts, retrieved {FETCHED}")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(OUT / "fig4_l1_contraction.png")
    plt.close(fig)

    def avg(rows_, y0, m0, y1, m1, idx):
        vals = [r[idx] for r in rows_
                if (y0, m0) <= (r[0].year, r[0].month) <= (y1, m1)
                and 1 <= r[0].day <= 10]
        return statistics.mean(vals) if vals else float("nan")
    t25 = avg(rows, 2025, 11, 2025, 11, 1)
    t26 = avg(rows, 2026, 11, 2026, 11, 1)
    a25 = avg(rows, 2025, 11, 2025, 11, 2)
    a26 = avg(rows, 2026, 11, 2026, 11, 2)
    tx_chg = (t26 / t25 - 1) * 100
    ac_chg = (a26 / a25 - 1) * 100
    print(f"fig4: window {start}..{end}; Nov 1-10 txns {t25 / 1e6:.2f}M (2025) vs "
          f"{t26 / 1e6:.2f}M (2026) = {tx_chg:+.0f}% YoY; "
          f"active accounts {a25 / 1e3:.0f}K vs {a26 / 1e3:.0f}K = "
          f"{ac_chg:+.0f}% YoY")
    CAPTIONS["fig4"] = (
        "Figure 4: NEAR L1 daily transactions (left) and daily active accounts "
        f"(right), 400 days to {end.strftime('%d %b %Y')}. "
        f"Transactions {tx_chg:+.0f}% YoY; active accounts {ac_chg:+.0f}% YoY. "
        f"Source: NearBlocks /v1/charts, retrieved {FETCHED}."
    )


def _fig4_fallback():
    """Two-point Nov 1-10 comparison using the PDF's verified values.

    Only used when NearBlocks cannot be reached. Values are the PDF's
    (Section 2.3), not live data — the figure says so.
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    cats = ["Daily transactions\n(M/day)", "Daily active accounts\n(K/day)"]
    v25 = [4.26, 249.0]
    v26 = [0.706, 81.0]
    x = [0, 1]
    w = 0.35
    ax.bar([i - w / 2 for i in x], v25, width=w, color=GREY, label="Nov 1-10, 2025")
    ax.bar([i + w / 2 for i in x], v26, width=w, color=TERRA, label="Nov 1-10, 2026")
    for i, (a, b) in enumerate(zip(v25, v26)):
        ax.text(i - w / 2, a * 1.05, f"{a:g}", ha="center", fontsize=10, color=TEXT)
        ax.text(i + w / 2, b * 1.05, f"{b:g}", ha="center", fontsize=10, color=TEXT)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, fontsize=11)
    ax.set_title("NEAR L1 activity, Nov 1-10 averages — transactions -83% YoY, "
                 "active accounts -67% YoY", fontsize=12, color=TEXT, pad=10)
    ax.legend(loc="upper right", fontsize=10, labelcolor=TEXT)
    style_ax(ax)
    source_line(fig, "NearBlocks unreachable at generation time — Nov 1-10 averages "
                     "from the v3 thesis PDF (Section 2.3), NOT live data")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig4_l1_contraction.png")
    plt.close(fig)
    print("fig4 FALLBACK used: Nov 1-10 values from PDF (txns 4.26M -> 0.706M, "
          "accounts 249K -> 81K); NOT live data")
    CAPTIONS["fig4"] = (
        "Figure 4: NEAR L1 daily transactions and daily active accounts, "
        "Nov 1-10 averages. Transactions -83% YoY; active accounts -67% YoY. "
        "Source: NearBlocks unreachable at generation time — Nov 1-10 averages "
        f"from the v3 thesis PDF (Section 2.3), NOT live data. Retrieved {FETCHED}."
    )


# ---------------------------------------------------------------- Figure 5 ---
def fig5():
    """NEAR chain TVL and stablecoin circulating, two years.
    Matches PDF Figure 5, including the light fill under the stablecoin line."""
    tvl = get("https://api.llama.fi/v2/historicalChainTvl/Near")
    st = get("https://stablecoins.llama.fi/stablecoincharts/near")
    t_dates = [datetime.datetime.fromtimestamp(x["date"], UTC) for x in tvl]
    t_vals = [x["tvl"] / 1e6 for x in tvl]
    s_dates = [datetime.datetime.fromtimestamp(int(x["date"]), UTC) for x in st]
    s_vals = [x["totalCirculating"]["peggedUSD"] / 1e6 for x in st]
    end = max(t_dates[-1], s_dates[-1])
    start = end - datetime.timedelta(days=729)
    t = [(d, v) for d, v in zip(t_dates, t_vals) if d >= start]
    s = [(d, v) for d, v in zip(s_dates, s_vals) if d >= start]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot([d for d, _ in t], [v for _, v in t], color=TERRA, lw=1.2,
            label="NEAR chain TVL")
    ax.plot([d for d, _ in s], [v for _, v in s], color=LIGHT, lw=1.2,
            label="Stablecoin circulating")
    ax.fill_between([d for d, _ in s], [v for _, v in s], 0,
                    color=LIGHT, alpha=0.08)
    top = max(500.0, math.ceil(max(max(v for _, v in t), max(v for _, v in s)) / 100) * 100)
    ax.set_ylim(0, top)
    ax.set_ylabel("$ millions", fontsize=11)
    ax.set_title("NEAR chain TVL and stablecoin circulating", fontsize=12, color=TEXT, pad=10)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 4, 7, 10)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_xlim(start, end + datetime.timedelta(days=5))
    ax.legend(loc="upper right", fontsize=10, labelcolor=TEXT)
    style_ax(ax)
    source_line(fig, f"Source: DefiLlama historicalChainTvl and stablecoins.llama.fi, "
                     f"retrieved {FETCHED}")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig5_tvl_stablecoins.png")
    plt.close(fig)

    def yoy(series, end_dt):
        now = series[-1][1]
        past = min(series, key=lambda p: abs((p[0] - (end_dt - datetime.timedelta(days=365))).days))
        return now, past[1], (now / past[1] - 1) * 100
    tvl_now, tvl_1y, tvl_chg = yoy(t, end)
    st_now, st_1y, st_chg = yoy(s, end)
    print(f"fig5: TVL now ${tvl_now:.0f}M vs ${tvl_1y:.0f}M 1y ago ({tvl_chg:+.0f}% YoY); "
          f"stablecoins now ${st_now:.0f}M vs ${st_1y:.0f}M ({st_chg:+.0f}% YoY); "
          f"stablecoins = {st_now / tvl_now * 100:.0f}% of TVL")
    CAPTIONS["fig5"] = (
        "Figure 5: NEAR chain TVL and stablecoin circulating, two years to "
        f"{end.strftime('%d %b %Y')}. TVL ${tvl_now:.0f}M ({tvl_chg:+.0f}% YoY); "
        f"stablecoins ${st_now:.0f}M ({st_now / tvl_now * 100:.0f}% of TVL). "
        "Source: DefiLlama historicalChainTvl and stablecoins.llama.fi, "
        f"retrieved {FETCHED}."
    )


def main():
    jobs = [("fig1_price.png", fig1), ("fig2_intents_volume.png", fig2),
            ("fig3_fee_revenue.png", fig3), ("fig4_l1_contraction.png", fig4),
            ("fig5_tvl_stablecoins.png", fig5)]
    failed = []
    for name, fn in jobs:
        try:
            fn()
        except Exception as exc:
            failed.append(name)
            print(f"FAILED {name}: {exc}", file=sys.stderr)
    for name, _ in jobs:
        p = OUT / name
        print(("OK   " if p.exists() else "MISS "), p, p.stat().st_size if p.exists() else "")
    if CAPTIONS:
        emit_captions(CAPTIONS)
    if failed:
        print(f"{len(failed)} figure(s) failed: {', '.join(failed)}", file=sys.stderr)
        sys.exit(1)
    print("All 5 Chapter 3 figures written to", OUT)


if __name__ == "__main__":
    main()
