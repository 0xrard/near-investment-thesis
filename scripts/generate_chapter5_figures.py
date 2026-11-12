#!/usr/bin/env python3
"""
Generate the Chapter 5 figures (Figures 8-9) for the NEAR investment thesis
dashboard, from LIVE public data. Part of the repo build pipeline:

    python3 scripts/generate_chapter5_figures.py

re-fetches every endpoint and regenerates both PNGs in ../figures/.

Sources (all keyless / free, no credentials, no BigQuery):
  - DefiLlama                    https://api.llama.fi             (30-day
                                  chain fees, near-intents daily volume)
  - CoinPaprika                 https://api.coinpaprika.com      (market caps)
  - Binance public data mirror  https://data-api.binance.vision  (NEARUSDT
                                  daily closes)
  - revenue.near.org            (monthly net protocol revenue, scraped from
                                  the server-rendered dashboard HTML, same
                                  approach as the thesis reproduce script and
                                  the Chapter 3/4 figure scripts)

Figure content, annotations and layout follow Figures 8-9 of the v3 thesis PDF
(NEARProtocol_InvestmentThesis_BusinessProfessional_2026-11-11.pdf). The match
is about content / annotations / layout, not the PDF's white background:
styling here is the wireframe dark theme (#0a0a0a background, light-grey text,
terracotta #E07856 accent).

Figure 8 method (fee multiples, log-log):
  One point per chain: x = annualized fees (30-day DefiLlama fees x 365/30),
  y = market cap (CoinPaprika). NEAR appears twice — gross Intents fees
  (DefiLlama near-intents 30d fees) and captured net revenue (latest complete
  month's net revenue from revenue.near.org x 12) — both at NEAR's market cap.
  Diagonal dashed lines are constant P/S multiples; the peer-median line is
  computed LIVE from the six peer chains (excluding NEAR) and labelled with
  the computed value (the PDF's value was 429x). NEAR is a terracotta diamond;
  peers are light-grey circles.
Figure 9 method (lead-lag correlogram):
  Daily NEAR log returns (Binance closes) vs daily Intents volume log growth
  (DefiLlama near-intents daily volume), over the last 527 days of overlapping
  data (the PDF's window: 527 days since June 2025). Cross-correlation at
  lags -14..+14 days, where a positive lag means volume leads price:
  r(k) = corr(return[t], volume_growth[t-k]). Dashed lines at +/-1.96/sqrt(n)
  mark the approximate 95% noise level. Lag 0 and the max-|r| lag are
  highlighted and labelled. Nothing is forced to match the PDF's values
  (r = +0.01 at lag 0, max |r| = 0.075 at +14 days) — the live computation is
  reported as it comes out.

Requirements: python3 + requests + matplotlib. No API keys.
"""
import datetime
import json
import math
import re
import statistics
import sys
from pathlib import Path

import requests

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

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

# --- dark theme (wireframe: #0a0a0a + terracotta #E07856), as in Ch3/Ch4 ---
BG = "#0a0a0a"
TERRA = "#E07856"      # primary / NEAR markers
GREY = "#8a9199"       # secondary series / peer markers
LIGHT = "#e8e8e8"      # light text / lines
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

ANNUALIZE = 365.0 / 30.0   # 30-day fees -> annualized
WINDOW_DAYS = 527          # lead-lag window, as in the PDF
MAX_LAG = 14


def get(url, timeout=30):
    r = requests.get(url, headers={"User-Agent": "near-thesis/1.0"}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def style_ax(ax, grid_both=False):
    ax.grid(axis="y" if not grid_both else "both", color="white", alpha=0.08, lw=0.8)
    ax.tick_params(labelsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(SPINE)
    ax.spines["bottom"].set_color(SPINE)


def source_line(fig, text):
    fig.text(0.01, 0.005, text, fontsize=8, color=MUTED)


def _revenue_monthly():
    """Monthly net protocol revenue (USD) from revenue.near.org (RSC scrape)."""
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


# ---------------------------------------------------------------- Figure 8 ---
def fig8():
    """Market cap vs annualized fees (log-log), with P/S reference lines.

    Matches PDF Figure 8: NEAR as a terracotta diamond (gross and net), peers
    as grey circles, diagonal constant-multiple lines, peer median labelled.
    All values are live (DefiLlama 30d fees annualized, CoinPaprika mcap,
    revenue.near.org net revenue for NEAR net).
    """
    # (label, DefiLlama fees slug, CoinPaprika ticker id)
    chains = [
        ("Tron", "tron", "trx-tron"),
        ("Arbitrum", "arbitrum", "arb-arbitrum"),
        ("Solana", "solana", "sol-solana"),
        ("BNB Chain", "bsc", "bnb-binance-coin"),
        ("Avalanche", "avalanche", "avax-avalanche"),
        ("Ethereum", "ethereum", "eth-ethereum"),
    ]
    points = []   # (label, annualized fees $M, mcap $B, P/S)
    for label, slug, tid in chains:
        fees = get(f"https://api.llama.fi/summary/fees/{slug}?dataType=dailyFees")
        ann = fees["total30d"] * ANNUALIZE / 1e6
        tick = get(f"https://api.coinpaprika.com/v1/tickers/{tid}")
        mcap = tick["quotes"]["USD"]["market_cap"] / 1e9
        points.append((label, ann, mcap, mcap * 1e3 / ann))
        print(f"  fig8 {label}: 30d fees ${fees['total30d'] / 1e6:.2f}M -> "
              f"annualized ${ann:.1f}M, mcap ${mcap:.2f}B, P/S {mcap * 1e3 / ann:.0f}x")

    # NEAR: gross Intents fees + captured net revenue, both at NEAR's mcap.
    near_tick = get("https://api.coinpaprika.com/v1/tickers/near-near-protocol")
    near_mcap = near_tick["quotes"]["USD"]["market_cap"] / 1e9
    intents = get("https://api.llama.fi/summary/fees/near-intents?dataType=dailyFees")
    near_gross = intents["total30d"] * ANNUALIZE / 1e6
    net = _revenue_monthly()
    now = datetime.datetime.now(UTC)
    # Latest complete month (the current month is partial).
    latest = max(k for k in net.keys() if k < (now.year, now.month))
    near_net = net[latest][0] * 12 / 1e6
    print(f"  fig8 NEAR: mcap ${near_mcap:.2f}B, gross Intents annualized "
          f"${near_gross:.1f}M (P/S {near_mcap * 1e3 / near_gross:.0f}x), "
          f"net revenue {latest[0]}-{latest[1]:02d} ${net[latest][0] / 1e6:.2f}M x12 = "
          f"${near_net:.1f}M annualized (P/S {near_mcap * 1e3 / near_net:.0f}x)")

    # Peer median P/S (peers only, excluding NEAR), computed live.
    peer_ps = sorted(p[3] for p in points)
    n = len(peer_ps)
    peer_median = (peer_ps[n // 2 - 1] + peer_ps[n // 2]) / 2 if n % 2 == 0 \
        else peer_ps[n // 2]
    print(f"  fig8 peer P/S values: {[f'{p:.0f}x' for p in peer_ps]}, "
          f"peer median {peer_median:.0f}x (PDF: 429x)")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(3, 500)
    ax.set_ylim(0.7, 450)
    ax.set_xlabel("Annualized fees ($M, 30-day fees x 365/30)", fontsize=11)
    ax.set_ylabel("Market cap ($B)", fontsize=11)
    ax.set_title("Market cap versus annualized fees (log-log)", fontsize=12,
                 color=TEXT, pad=10)
    ax.set_xticks([10, 100])
    ax.set_xticklabels(["10", "100"])
    ax.set_yticks([1, 10, 100])
    ax.set_yticklabels(["1", "10", "100"])

    # Constant P/S reference lines: mcap($B) = multiple x fees($M) / 1000.
    xs = [3.0, 500.0]
    for mult, color, lw, label, lx in (
            (100, GREY, 1.0, "100x", 470),
            (1000, GREY, 1.0, "1000x", 380),
            (peer_median, TERRA, 1.4, f"Peer median {peer_median:.0f}x", 470)):
        ys = [mult * x / 1000.0 for x in xs]
        ax.plot(xs, ys, color=color, lw=lw, ls="--", alpha=0.85)
        ax.text(lx, mult * lx / 1000.0 * 1.18, label, fontsize=9, color=color,
                ha="right", va="bottom",
                bbox=dict(facecolor=BG, alpha=0.9, edgecolor="none", pad=1.5))

    bbox = dict(facecolor=BG, alpha=0.9, edgecolor="none", pad=1.5)

    def tag(x, y, text, dx, dy, ha="left"):
        ax.annotate(text, xy=(x, y), xytext=(dx, dy),
                    textcoords="offset points", fontsize=9, color=TEXT,
                    ha=ha, va="center", bbox=bbox)

    # Peers: grey circles, labels at the live-fetched positions.
    by_label = {p[0]: p for p in points}
    for label, ann, mcap, _ in points:
        ax.plot([ann], [mcap], marker="o", ms=7, color=GREY,
                markerfacecolor=GREY, linestyle="none")
    tag(by_label["Tron"][1], by_label["Tron"][2], "Tron", 0, 12)
    tag(by_label["Arbitrum"][1], by_label["Arbitrum"][2], "Arbitrum", 0, -13)
    tag(by_label["Solana"][1], by_label["Solana"][2], "Solana", -8, 10, ha="right")
    tag(by_label["BNB Chain"][1], by_label["BNB Chain"][2], "BNB Chain", 0, 12)
    tag(by_label["Avalanche"][1], by_label["Avalanche"][2], "Avalanche", -8, 10, ha="right")
    tag(by_label["Ethereum"][1], by_label["Ethereum"][2], "Ethereum", -8, 10, ha="right")

    # NEAR: terracotta diamonds (gross filled, net hollow).
    ax.plot([near_gross], [near_mcap], marker="D", ms=9, color=TERRA,
            markerfacecolor=TERRA, linestyle="none")
    ax.plot([near_net], [near_mcap], marker="D", ms=9, color=TERRA,
            markerfacecolor=BG, markeredgewidth=1.6, linestyle="none")
    tag(near_gross, near_mcap, "NEAR (gross)", 10, 0)
    tag(near_net, near_mcap, "NEAR (net)", -10, 0, ha="right")

    style_ax(ax, grid_both=True)
    source_line(fig, f"Sources: DefiLlama 30d fees (annualized x 365/30); "
                     f"CoinPaprika market caps; revenue.near.org net revenue "
                     f"({latest[0]}-{latest[1]:02d} x 12 for NEAR net). "
                     f"Retrieved {FETCHED}")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig8_fee_multiples.png")
    plt.close(fig)
    print(f"fig8: {len(points)} peers + NEAR gross/net; peer median P/S "
          f"{peer_median:.0f}x; NEAR gross P/S {near_mcap * 1e3 / near_gross:.0f}x, "
          f"NEAR net P/S {near_mcap * 1e3 / near_net:.0f}x")
    CAPTIONS["fig8"] = (
        "Figure 8: Market cap versus annualized fees (log-log), "
        f"{RETRIEVED_LABEL}. NEAR (diamond) sits below the peer pack on gross "
        f"fees; the peer median multiple is {peer_median:.0f}x. Sources: "
        f"DefiLlama, CoinPaprika; retrieved {FETCHED}."
    )


# ---------------------------------------------------------------- Figure 9 ---
def _pearson(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) *
                    sum((y - my) ** 2 for y in ys))
    return num / den if den > 0 else float("nan")


def fig9():
    """Cross-correlation of daily NEAR price returns vs Intents volume growth,
    lags -14..+14 days (positive lag = volume leads). Matches PDF Figure 9:
    bars per lag, r = 0 line, lag 0 and max |r| highlighted. Window: the last
    527 days of overlapping data (the PDF's window)."""
    kl = get("https://data-api.binance.vision/api/v3/klines"
             "?symbol=NEARUSDT&interval=1d&limit=1000")
    price = {}
    for k in kl:
        d = datetime.datetime.fromtimestamp(int(k[0]) / 1000, UTC).date()
        price[d] = float(k[4])
    v = get("https://api.llama.fi/summary/dexs/near-intents?dataType=dailyVolume")
    vol = {}
    for ts, val in v["totalDataChart"]:
        d = datetime.datetime.fromtimestamp(ts, UTC).date()
        vol[d] = float(val)

    common = sorted(set(price) & set(vol))
    window = common[-WINDOW_DAYS:]
    start, end = window[0], window[-1]
    print(f"  fig9 window: {start}..{end} ({len(window)} days, "
          f"overlap {common[0]}..{common[-1]})")

    # Daily log returns and log volume growth, aligned by date.
    ret, vg = {}, {}
    for i in range(1, len(window)):
        d, prev = window[i], window[i - 1]
        if (d - prev).days != 1:
            continue
        if price[d] > 0 and price[prev] > 0:
            ret[d] = math.log(price[d] / price[prev])
        if vol[d] > 0 and vol[prev] > 0:
            vg[d] = math.log(vol[d] / vol[prev])

    lags = list(range(-MAX_LAG, MAX_LAG + 1))
    rs = []
    for k in lags:
        # Positive lag = volume leads: return[t] vs volume growth[t-k].
        pairs = [(ret[t], vg[t - datetime.timedelta(days=k)])
                 for t in ret
                 if (t - datetime.timedelta(days=k)) in vg]
        rs.append(_pearson([p[0] for p in pairs], [p[1] for p in pairs]))
        if k in (0,):
            n0 = len(pairs)
    r0 = rs[lags.index(0)]
    max_i = max(range(len(rs)), key=lambda i: abs(rs[i]))
    max_lag, max_r = lags[max_i], rs[max_i]
    band = 1.96 / math.sqrt(n0)
    print(f"  fig9 r at lag 0: {r0:+.3f} (n={n0}); max |r| = {max_r:+.3f} at lag "
          f"{max_lag:+d}; 95% noise band +/-{band:.3f} (PDF: r=+0.01 at lag 0, "
          f"max |r|=0.075 at +14)")
    for k, r in zip(lags, rs):
        print(f"    lag {k:+3d}: r = {r:+.3f}")

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = [TERRA if (k == 0 or k == max_lag) else GREY for k in lags]
    ax.bar(lags, rs, width=0.7, color=colors)
    ax.axhline(0, color=LIGHT, lw=1.0)
    ax.axhline(band, color=GREY, lw=1.0, ls="--", alpha=0.8)
    ax.axhline(-band, color=GREY, lw=1.0, ls="--", alpha=0.8)
    ax.text(MAX_LAG + 0.6, band, f"+1.96/sqrt(n) = +{band:.2f}", fontsize=8,
            color=MUTED, ha="right", va="bottom")
    ax.text(MAX_LAG + 0.6, -band, f"-1.96/sqrt(n) = -{band:.2f}", fontsize=8,
            color=MUTED, ha="right", va="top")
    bbox = dict(facecolor=BG, alpha=0.9, edgecolor="none", pad=1.5)
    ax.text(0, r0 + (0.012 if r0 >= 0 else -0.012),
            f"lag 0: r = {r0:+.2f}", fontsize=9, color=TERRA, ha="center",
            va="bottom" if r0 >= 0 else "top", bbox=bbox)
    ax.text(max_lag, max_r + (0.012 if max_r >= 0 else -0.012),
            f"max |r| = {max_r:+.2f} at lag {max_lag:+d}", fontsize=9,
            color=TERRA, ha="center",
            va="bottom" if max_r >= 0 else "top", bbox=bbox)
    ax.set_xlim(-MAX_LAG - 1, MAX_LAG + 1)
    ax.set_xticks(range(-MAX_LAG, MAX_LAG + 1, 2))
    ax.set_xlabel("Lag (days; positive lag = volume leads price)", fontsize=11)
    ax.set_ylabel("Cross-correlation r", fontsize=11)
    ax.set_title("Cross-correlation of daily NEAR price returns versus "
                 "Intents volume growth", fontsize=12, color=TEXT, pad=10)
    style_ax(ax)
    source_line(fig, f"Sources: Binance NEARUSDT daily closes; DefiLlama "
                     f"near-intents daily volume. Window {start}..{end} "
                     f"({len(window)} days). Retrieved {FETCHED}")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(OUT / "fig9_lead_lag.png")
    plt.close(fig)
    print(f"fig9: r(lag 0) = {r0:+.3f}, max |r| = {max_r:+.3f} at lag {max_lag:+d}, "
          f"noise band +/-{band:.3f}")
    CAPTIONS["fig9"] = (
        "Figure 9: Cross-correlation of daily NEAR price returns versus Intents "
        "volume growth, lags -14 to +14 days (positive lag = volume leads). "
        f"r = {r0:.2f} at lag 0; max |r| = {abs(max_r):.2f} at lag {max_lag:+d}. "
        "No exploitable timing relationship. Sources: Binance data-api, "
        f"DefiLlama; retrieved {FETCHED}."
    )


def main():
    jobs = [("fig8_fee_multiples.png", fig8),
            ("fig9_lead_lag.png", fig9)]
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
    print("Both Chapter 5 figures written to", OUT)


if __name__ == "__main__":
    main()
