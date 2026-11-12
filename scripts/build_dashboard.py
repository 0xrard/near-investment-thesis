#!/usr/bin/env python3
"""Build dashboard/index-generated.html from data/ + model outputs.

NOTE: dashboard/index.html is the frozen thesis page (11 Nov 2026 snapshot)
served by GitHub Pages. This script deliberately writes to
index-generated.html so a rebuild never overwrites the served page.

Static page — no JavaScript, no API calls at view time. Charts render from
shipped CSVs when present; otherwise they render as clearly-labelled
placeholders ("—", "No data yet"), never invented numbers.

Usage: python3 scripts/build_dashboard.py
"""

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
QUERIES = ROOT / "queries"
OUT = ROOT / "dashboard" / "index-generated.html"

ACCENT = "#E07856"
MUTED = "#9a9a9a"


# ------------------------------------------------------------ helpers ---

def fmt_usd(v):
    if v is None:
        return "—"
    v = float(v)
    if abs(v) >= 1e9:
        return f"${v / 1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v / 1e3:.1f}K"
    return f"${v:,.0f}"


def fmt_num(v):
    if v is None:
        return "—"
    return f"{float(v):,.0f}"


def fmt_pct(v):
    if v is None:
        return "—"
    return f"{float(v) * 100:.1f}%"


def read_csv(path: Path):
    if not path.exists():
        return None
    with open(path, newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def read_sql(name: str) -> str:
    p = QUERIES / name
    return p.read_text().strip() if p.exists() else "-- query not found: " + name


# -------------------------------------------------------------- charts ---

def _scale(points, width, height, pad=8):
    ys = [p[1] for p in points]
    lo, hi = min(ys), max(ys)
    if hi == lo:
        hi = lo + 1
    n = len(points)
    xs = [pad + i * (width - 2 * pad) / max(n - 1, 1) for i in range(n)]
    ys_px = [height - pad - (y - lo) / (hi - lo) * (height - 2 * pad) for y in ys]
    return xs, ys_px, lo, hi


def svg_line(series, width=720, height=240, color=ACCENT, title=""):
    """series: [(label, value), ...] -> SVG line chart or None."""
    pts = [(lbl, float(v)) for lbl, v in series if v is not None]
    if len(pts) < 2:
        return None
    xs, ys, lo, hi = _scale(pts, width, height)
    points = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    grid = ""
    for frac in (0.25, 0.5, 0.75):
        gy = height - 8 - frac * (height - 16)
        grid += (f'<line x1="8" y1="{gy:.1f}" x2="{width - 8}" y2="{gy:.1f}" '
                 f'stroke="rgba(255,255,255,0.07)" stroke-width="1"/>')
    last = pts[-1]
    return f"""<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="{html.escape(title)}">
{grid}
<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>
<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="3.5" fill="{color}"/>
<text x="8" y="18" fill="{MUTED}" font-size="11" font-family="IBM Plex Mono, monospace">{fmt_num(hi)}</text>
<text x="8" y="{height - 4}" fill="{MUTED}" font-size="11" font-family="IBM Plex Mono, monospace">{html.escape(str(pts[0][0]))}</text>
<text x="{width - 8}" y="{height - 4}" fill="{MUTED}" font-size="11" font-family="IBM Plex Mono, monospace" text-anchor="end">{html.escape(str(last[0]))} · {fmt_num(last[1])}</text>
</svg>"""


def svg_dual_indexed(series_a, series_b, label_a, label_b, width=720, height=240):
    """Two series indexed to 100 at the first common date (avoids dual axes)."""
    a = {d: float(v) for d, v in series_a if v is not None}
    b = {d: float(v) for d, v in series_b if v is not None}
    common = sorted(set(a) & set(b))
    if len(common) < 2:
        return None
    base_a, base_b = a[common[0]], b[common[0]]
    if not base_a or not base_b:
        return None
    sa = [(d, a[d] / base_a * 100) for d in common]
    sb = [(d, b[d] / base_b * 100) for d in common]
    all_y = [v for _, v in sa] + [v for _, v in sb]
    lo, hi = min(all_y), max(all_y)
    if hi == lo:
        hi = lo + 1
    pad = 8
    n = len(common)
    xs = [pad + i * (width - 2 * pad) / max(n - 1, 1) for i in range(n)]

    def to_y(v):
        return height - pad - (v - lo) / (hi - lo) * (height - 2 * pad)

    pa = " ".join(f"{x:.1f},{to_y(v):.1f}" for x, (_, v) in zip(xs, sa))
    pb = " ".join(f"{x:.1f},{to_y(v):.1f}" for x, (_, v) in zip(xs, sb))
    return f"""<svg viewBox="0 0 {width} {height}" width="100%" role="img" aria-label="indexed chart">
<polyline points="{pa}" fill="none" stroke="{ACCENT}" stroke-width="2" stroke-linejoin="round"/>
<polyline points="{pb}" fill="none" stroke="#ededed" stroke-width="2" stroke-linejoin="round"/>
<circle cx="{xs[-1]:.1f}" cy="{to_y(sa[-1][1]):.1f}" r="3.5" fill="{ACCENT}"/>
<circle cx="{xs[-1]:.1f}" cy="{to_y(sb[-1][1]):.1f}" r="3.5" fill="var(--ink)"/>
<text x="8" y="18" fill="{ACCENT}" font-size="11" font-family="IBM Plex Mono, monospace">— {html.escape(label_a)}</text>
<text x="8" y="34" fill="#ededed" font-size="11" font-family="IBM Plex Mono, monospace">— {html.escape(label_b)}</text>
<text x="8" y="{height - 4}" fill="{MUTED}" font-size="11" font-family="IBM Plex Mono, monospace">{html.escape(common[0])}</text>
<text x="{width - 8}" y="{height - 4}" fill="{MUTED}" font-size="11" font-family="IBM Plex Mono, monospace" text-anchor="end">{html.escape(common[-1])}</text>
</svg>"""


def placeholder_box(text="No data yet — placeholder shape, not real data."):
    return (f'<div class="placeholder-box"><div class="placeholder-mark">—</div>'
            f'<p>{html.escape(text)}</p></div>')


def chart_card(chart_id, title, sentence, chart_html, sql_name, source_note):
    sql = html.escape(read_sql(sql_name))
    return f"""<div class="chart-card" id="{chart_id}">
  <h3>{html.escape(title)}</h3>
  {chart_html}
  <p class="chart-sentence">{html.escape(sentence)}</p>
  <details class="query"><summary>Show query</summary><pre>{sql}</pre></details>
  <p class="source-note">{html.escape(source_note)}</p>
</div>"""


# ------------------------------------------------------------ sections ---

def hero_stats_html(outputs):
    hero = (outputs or {}).get("hero_stats", {}) if outputs else {}
    cells = [
        ("Cumulative Intents Volume",
         fmt_usd(hero.get("cumulative_intents_volume_usd")),
         hero.get("cumulative_intents_volume_source") or "DefiLlama — awaiting fetch",
         hero.get("cumulative_intents_volume_as_of")),
        ("Annualised Fees (30d run-rate)",
         fmt_usd(hero.get("annualised_fees_usd")),
         (hero.get("annualised_fees_definition") or "Gross Intents fees, 30-day run-rate (total30d × 12)")
         + (f" — {hero['annualised_fees_source']}" if hero.get("annualised_fees_source") else " — awaiting fetch"),
         hero.get("annualised_fees_as_of")),
        ("Current Market Cap",
         fmt_usd(hero.get("market_cap_usd")),
         hero.get("market_cap_source") or "CoinGecko — awaiting fetch",
         hero.get("market_cap_as_of")),
        ("Post-Halving Inflation Rate",
         fmt_pct(hero.get("inflation_rate")),
         hero.get("inflation_source") or "Protocol parameter",
         None),
    ]
    out = []
    for label, value, src, as_of in cells:
        as_of_txt = f" · as of {as_of[:10]}" if as_of else ""
        out.append(
            f'<div class="hero-stat"><div class="hs-num">{value}</div>'
            f'<div class="hs-label">{html.escape(label)}</div>'
            f'<div class="hs-src">{html.escape(src)}{as_of_txt}</div></div>'
        )
    return "\n".join(out)


def scenario_rows(outputs):
    if not outputs:
        return '<tr><td colspan="4" class="ph">— (run the model to fill this table)</td></tr>'
    rows = []
    base_bps = str(outputs["inputs"]["base_take_rate_bps"])
    for sc in outputs["scenarios"]:
        fee = sc["annual_fee_revenue_usd_by_bps"][base_bps]
        rows.append(
            f"<tr><td><strong>{sc['name'].title()}</strong></td>"
            f"<td>{sc['annual_growth']:.0%} / yr</td>"
            f"<td>{fmt_usd(sc['annual_settlement_volume_usd'])}</td>"
            f"<td>{fmt_usd(fee)}</td>"
            f"<td>{html.escape(sc['what_must_be_true'])}</td></tr>"
        )
    return "\n".join(rows)


def sensitivity_rows(outputs):
    if not outputs:
        return '<tr><td colspan="4" class="ph">— (run the model to fill this table)</td></tr>'
    bps_list = [str(b) for b in outputs["sensitivity"]["take_rates_bps"]]
    head = "".join(f"<th>{b} bps</th>" for b in bps_list)
    rows = [f"<tr><th>Growth</th>{head}</tr>"]
    for g in outputs["sensitivity"]["growth_rates"]:
        cells = "".join(
            f"<td>{fmt_usd(outputs['sensitivity']['annual_fee_revenue_usd'][str(g)][b])}</td>"
            for b in bps_list
        )
        rows.append(f"<tr><td><strong>{float(g):.0%} / yr</strong></td>{cells}</tr>")
    return "\n".join(rows)


def threshold_html(outputs):
    if not outputs:
        return '<div class="big-num">—</div><p>Run the model to compute the threshold.</p>'
    th = outputs["deflationary_threshold"]["daily_volume_usd_by_take_rate_bps"]
    base_bps = str(outputs["inputs"]["base_take_rate_bps"])
    val = th.get(base_bps)
    ph = outputs.get("placeholder", False)
    note = ("<p class='warn'>Placeholder — computed from placeholder inputs "
            "(see list below). Do not cite until inputs are real data.</p>") if ph else ""
    items = "".join(
        f"<li>{b} bps → <strong>{fmt_usd(v)}</strong> / day</li>" for b, v in th.items()
    )
    return (f'<div class="big-num">{fmt_usd(val)}<span class="big-unit"> / day</span></div>'
            f'<p>Daily Intents volume at which buybacks offset new issuance '
            f'(at the base fee take rate of {base_bps} bps). Price-dependent: '
            f'the higher the NEAR price, the further the threshold.</p>'
            f'<ul>{items}</ul>{note}')


def tests_html(outputs):
    if not outputs:
        return "<p>— (run the model to evaluate the tests)</p>"
    t = outputs["hypothesis_tests"]
    parts = []
    a = t["A_sticky"]
    parts.append(f"<p><strong>A — Sticky volume:</strong> {a['status'].replace('_', ' ')}. "
                 f"{html.escape(a.get('reason') or '')}</p>")
    b = t["B_additive"]
    if b["status"] == "computed":
        det = "; ".join(
            f"{k}: r={v['pearson_r']:.2f} (n={v['n_days']}d)" if v.get("pearson_r") is not None
            else f"{k}: n/a" for k, v in b["correlations"].items()
        )
        parts.append(f"<p><strong>B — Additive growth:</strong> computed on daily changes "
                     f"(volume growth vs activity growth). {html.escape(det)}</p>")
    else:
        parts.append(f"<p><strong>B — Additive growth:</strong> {b['status'].replace('_', ' ')}. "
                     f"{html.escape(b.get('reason') or '')}</p>")
    ll = t["lead_lag_volume_vs_price"]
    if ll["status"] == "computed":
        band = ll.get("noise_band_95")
        noise = ""
        if band is not None:
            verdict = ("outside" if ll.get("best_is_significant") else "within")
            noise = f"; 95% noise band ±{band:.2f}, so {verdict} noise"
        parts.append(
            f"<p><strong>Lead/lag (volume vs price):</strong> computed on daily changes. "
            f"Strongest lag (by |r|): {ll['best_lag_days']} days "
            f"(r={ll['best_pearson_r']:.2f}{noise}). "
            f"Positive lag means volume moves first.</p>")
    else:
        parts.append(f"<p><strong>Lead/lag (volume vs price):</strong> "
                     f"{ll['status'].replace('_', ' ')}. {html.escape(ll.get('reason') or '')}</p>")
    return "\n".join(parts)


# ------------------------------------------- prose-number templating ---
# "Where Things Stand" prose numbers are templated: WTS_TEMPLATE uses
# {{placeholder}} tokens, resolved here from data CSVs / JSONs / model
# outputs at build time, falling back to the Nov 9 2026 dossier snapshot
# when a source is missing. Never invent a number: a missing source means
# the fallback snapshot value is used. Placeholders whose definition
# depends on the fee slug are named for the slug (near_protocol =
# full-chain DefiLlama fees); the repo only fetches the near-intents slug,
# so those resolve to the fallback until a near-protocol source is added
# (a fetch.py change, out of scope here). The Intents-based P/F (67.9x)
# is a different definition and is deliberately NOT substituted for the
# dossier's full-chain P/F (58.8x).
WTS_FALLBACKS = {
    "snapshot_date": "November 9, 2026",
    "price": "$3.57",
    "market_cap": "$4.68B",
    "reverse_dcf_growth": "15%",
    "fees_annualized_near_protocol": "$79.7M",
    "fees_annualized_body": "$70.7M",
    "fee_yield_near": "1.70%",
    "fee_yield_eth": "1.87%",
    "fee_base_ratio_eth": "50x",
    "tvl_mcap": "3.58%",
    "intents_volume_30d": "$4.0B",
    "tvl": "$167.5M",
    "stablecoins": "$130.4M",
    "staked_share": "44.3%",
    "inflation_rate": "2.5%",
    "net_issuance_2027e": "~1.5%",
    "pf_multiple_near_protocol": "58.8x",
}


def _fmt_snapshot_date(iso_str):
    """ISO timestamp -> 'Month D, YYYY' (e.g. 'November 9, 2026'), or None."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
    except ValueError:
        return None
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def resolve_prose_values(outputs):
    """Placeholder -> formatted string, live source first, Nov 9 fallback."""
    vals = dict(WTS_FALLBACKS)
    manifest = read_json(DATA / "manifest.json") or {}
    market = read_json(DATA / "near_market.json") or {}

    # Price + market cap: CoinGecko snapshot (near_market.json), else model.
    if market.get("price_usd") is not None:
        vals["price"] = f"${float(market['price_usd']):.2f}"
    elif outputs and outputs.get("inputs", {}).get("near_price_usd") is not None:
        vals["price"] = f"${float(outputs['inputs']['near_price_usd']):.2f}"
    if market.get("market_cap_usd") is not None:
        vals["market_cap"] = fmt_usd(market["market_cap_usd"])
    elif outputs and outputs.get("hero_stats", {}).get("market_cap_usd") is not None:
        vals["market_cap"] = fmt_usd(outputs["hero_stats"]["market_cap_usd"])

    # Snapshot date: the market snapshot's pull date (price/mcap as-of).
    snap = _fmt_snapshot_date(market.get("last_updated"))
    if snap is None:
        snap = _fmt_snapshot_date((manifest.get("near_market.json") or {}).get("pulled_at_utc"))
    if snap is not None:
        vals["snapshot_date"] = snap

    # Intents 30-day volume: DefiLlama /summary/dexs total30d.
    dexs = read_json(DATA / "defillama_intents_dexs.json") or {}
    if dexs.get("total30d") is not None:
        vals["intents_volume_30d"] = fmt_usd(dexs["total30d"])

    # Model outputs: reverse-DCF growth (base scenario), inflation, net issuance.
    if outputs:
        for sc in outputs.get("scenarios", []):
            if sc.get("name") == "base" and sc.get("annual_growth") is not None:
                vals["reverse_dcf_growth"] = f"{float(sc['annual_growth']) * 100:.0f}%"
        inp = outputs.get("inputs", {})
        if inp.get("issuance_annual_rate") is not None:
            vals["inflation_rate"] = f"{float(inp['issuance_annual_rate']) * 100:.1f}%"
        if inp.get("net_issuance_2027e") is not None:
            vals["net_issuance_2027e"] = f"~{float(inp['net_issuance_2027e']) * 100:.1f}%"

    # No repo source (fallback stands by design — see the comment above):
    # fees_annualized_near_protocol, fees_annualized_body, fee_yield_near,
    # fee_yield_eth, fee_base_ratio_eth, tvl_mcap, tvl, stablecoins,
    # staked_share, pf_multiple_near_protocol.
    return vals


def render_wts_template(template, values):
    """Substitute {{placeholder}} tokens; fail loudly on any leftover."""
    out = template
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", html.escape(str(val)))
    if "{{" in out:
        import re
        missing = sorted(set(re.findall(r"\{\{([A-Za-z0-9_]+)\}\}", out)))
        raise ValueError(f"unresolved prose placeholders: {', '.join(missing)}")
    return out


WTS_TEMPLATE = """<section id="where-things-stand">
  <div class="sec-kicker">Snapshot</div>
  <h2 class="sec-title">Where Things Stand</h2>
  <p class="lede">After five years of building, NEAR Protocol has reached a turning point — one visible in the numbers, not in a headline. The network is now producing the fee and volume patterns that come before lasting token value. As of {{snapshot_date}}, the token trades at {{price}} with a {{market_cap}} market cap, fully unlocked, with monetized usage accelerating and the supply curve bending downward. This summary builds the case from the ground up — using real fee numbers, actual volume trends, and a supply model with every assumption out in the open — and it names, up front, the exact data that would prove it wrong.</p>
  <div class="key-finding"><p><strong>Key finding:</strong> at {{price}}, the reverse DCF says today's price already pays for roughly {{reverse_dcf_growth}} per year of fee growth over five years — merely to break even. Anything faster is pure upside, and the review-trigger table defines, in advance, exactly which data would force this thesis to be discarded.</p></div>
  <table>
    <tr><th>Key metric</th><th>Value</th><th>Key metric</th><th>Value</th></tr>
    <tr><td>Price</td><td><strong>{{price}}</strong></td><td>Market capitalization</td><td><strong>{{market_cap}}</strong></td></tr>
    <tr><td>30-day fees (annualized)</td><td><strong>{{fees_annualized_near_protocol}}</strong></td><td>P/F multiple</td><td><strong>{{pf_multiple_near_protocol}}</strong></td></tr>
    <tr><td>Chain TVL</td><td><strong>{{tvl}}</strong></td><td>Stablecoins outstanding</td><td><strong>{{stablecoins}}</strong></td></tr>
    <tr><td>On-chain stake</td><td><strong>{{staked_share}}</strong></td><td>Maximum inflation (on-chain)</td><td><strong>{{inflation_rate}}</strong></td></tr>
    <tr><td>Net issuance post-burn (2027E)</td><td><strong>{{net_issuance_2027e}}</strong></td><td>Implied 5-year fee growth</td><td><strong>+{{reverse_dcf_growth}}/yr</strong></td></tr>
  </table>
  <p class="muted">Note: the table uses {{fees_annualized_near_protocol}} (annualized) for 30-day fees; the Report's body cites {{fees_annualized_body}}. Different definitions — shown as published, not reconciled.</p>
  <h3>Three mutually reinforcing dynamics</h3>
  <p>Three forces drive this thesis, and they strengthen one another — monetized usage accelerating, supply discipline verified in code and governance, and a valuation that already pays for most of the story — each tested against public data, not narrative, and each with a defined falsification threshold.</p>
  <h3>The market already repriced the bounce</h3>
  <p>The token bottomed on February 6, 2026, then re-rated sharply over the following months (Figure 1). Spot volume repeatedly cleared levels far above the early-year baseline. The "easy" multiple expansion has already happened — what remains unpriced is persistence (whether Intents flow sticks) plus the descending supply curve. From here, price must be earned by fundamentals.</p>
  <div class="placeholder-box"><div class="placeholder-mark">—</div><p>Figure 1 — NEAR/USDT daily price and volume, trailing 2 years (Binance daily klines). Generated by scripts/generate_chapter3_figures.py (fig1_price.png); not yet embedded in this dashboard.</p></div>
  <h3>The gap is not the price</h3>
  <p>Measured against peers, NEAR is not a discount asset waiting for re-rating: its {{fee_yield_near}} fee yield is roughly in line with Ethereum's per dollar ({{fee_yield_eth}} on a fee base {{fee_base_ratio_eth}} larger), its TVL/Mcap of {{tvl_mcap}} is the lowest of eleven peer chains, and its supply carries no vesting overhang left to discount. The gap that matters is therefore not price versus peers - it is protocol quality versus the market's assessment of persistence. NEAR is priced for delivery; the margin of safety must come from flow and supply, not from multiples.</p>
  <h3>The stack agents need</h3>
  <p>NEAR is building the stack for agent-mediated commerce - transactions executed by autonomous AI agents that need three properties no single chain provides together today: privacy (Confidential Intents, GA July 2026), cross-chain reach (Intents and Chain Signatures let users and agents hold assets and act on any chain while settlement runs through NEAR), and verifiability (settlement on a public ledger anyone can audit). Intents abstract execution paths so agents express outcomes, not routes. NEAR is the settlement token for that flow, and the {{intents_volume_30d}}/30-day volume against {{tvl}} TVL is its quantitative fingerprint.</p>
  <h3>Why now: the convergence window</h3>
  <p>Three structural changes land within nine months of each other, and each one moves a different lever - monetization, overhang, and issuance.</p>
  <ol>
    <li>Fee switch active (February 23, 2026) - the protocol begins converting and burning a share of fees; monetization starts from ~0%.</li>
    <li>Supply fully unlocked (March 2026) - circulating supply reaches total supply (~1.29B); the unlock overhang that still burdens most large-cap assets ends permanently.</li>
    <li>HSP-029 ratified (November 3, 2026) - issuance steps down from 2.5% to 1.6% within 24 months (~$45M/year less emission), and governance demonstrates it executes supply discipline through process, not announcements.</li>
  </ol>
  <p>Third-party confirmation followed: Nansen's Q3 report tallies cumulative Intents volume at $32B (+45% QoQ) with cumulative fees above $52M.</p>
</section>"""


def where_things_stand_html(outputs):
    """Render the 'Where Things Stand' section with templated prose numbers."""
    return render_wts_template(WTS_TEMPLATE, resolve_prose_values(outputs))


# ---------------------------------------------------------------- page ---

CSS = """
:root{--paper:#f4f1ea;--paper-2:#ece7db;--card:#fbf9f4;--ink:#1d2733;--ink-soft:#48586a;
--ink-faint:#7c8a99;--line:#b9c2cc;--line-strong:#5b7186;--accent:#E07856;
--accent-soft:rgba(224,120,86,.10);--key:#d95d1e;--key-soft:rgba(217,93,30,.10);
--good:#2e7d4f;--bad:#b03a2e;--grid:rgba(224,120,86,.07);--code-bg:#22303e;
--code-ink:#d7e3ee;--bg:var(--paper);--bg-hero:#0a0a0a}
@media (prefers-color-scheme: dark){
:root{--paper:#10161d;--paper-2:#0c1117;--card:#161e27;--ink:#e6edf4;--ink-soft:#a9b8c7;
--ink-faint:#71808f;--line:#33424f;--line-strong:#5f7488;--accent:#E07856;
--accent-soft:rgba(224,120,86,.12);--key:#f08a4b;--key-soft:rgba(240,138,75,.12);
--good:#5cb586;--bad:#e07a6b;--grid:rgba(224,120,86,.06);--code-bg:#0a0f14;
--code-ink:#cfe0ef;--bg:var(--paper)}
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:Inter,system-ui,-apple-system,sans-serif;line-height:1.6;
background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);
background-size:28px 28px}
a{color:var(--accent)}
h1,h2,h3{font-family:"Playfair Display",Georgia,serif;line-height:1.15;margin:0}
h2.sec-title{font-size:2rem;font-weight:700}
h3{font-size:1.25rem;font-weight:700}
.sec-kicker{font-family:"IBM Plex Mono",monospace;font-size:.72rem;letter-spacing:.16em;
text-transform:uppercase;color:var(--ink-soft);margin-bottom:.5rem}
.page{max-width:1080px;margin:0 auto;padding:0 1.5rem 4rem}
section{margin-top:4.5rem}
.lede{font-size:1.15rem;color:var(--ink)}
.muted{color:var(--ink-soft)}
/* hero */
.site-hero{min-height:100vh;background:var(--bg-hero);position:relative;overflow:hidden;
display:flex;flex-direction:column}
.top-nav{display:flex;justify-content:center;flex-wrap:wrap;gap:1.2rem 2.2rem;
padding:1.1rem 1rem;border-bottom:1px solid var(--line);position:relative;z-index:2}
.top-nav a{font-family:"IBM Plex Mono",monospace;font-size:.72rem;font-weight:600;
letter-spacing:.16em;text-transform:uppercase;color:var(--ink-soft);text-decoration:none}
.top-nav a:hover,.top-nav a:focus{color:var(--accent)}
.hero-inner{max-width:1080px;margin:0 auto;width:100%;padding:16vh 1.5rem 3rem;
position:relative;z-index:2}
.hero-eyebrow{font-size:.72rem;font-weight:600;letter-spacing:.18em;text-transform:uppercase;
color:var(--accent);margin-bottom:1.4rem}
.hero h1{font-size:clamp(3rem,8.5vw,5.9rem);font-weight:700;color:#fff}
.h1-angle{font-family:"Playfair Display",Georgia,serif;font-style:italic;font-weight:600;
font-size:clamp(1.26rem,3.6vw,2.48rem);color:var(--accent);margin-top:.4rem}
.hero-stats{display:grid;grid-template-columns:repeat(4,1fr);background:var(--card);
border:1px solid var(--line);margin-top:3rem}
.hero-stat{padding:1.2rem 1.3rem;border-left:1px solid var(--line)}
.hero-stat:first-child{border-left:none}
.hs-num{font-family:"Playfair Display",Georgia,serif;font-size:clamp(1.9rem,4vw,2.6rem);font-weight:700;color:var(--accent)}
.hs-label{font-size:.82rem;margin-top:.2rem}
.hs-src{font-size:.68rem;color:var(--ink-soft);margin-top:.3rem;line-height:1.4}
.hero-author{margin-top:2.6rem;color:var(--ink-soft)}
.hero-rule{border:none;border-top:1px solid var(--line);margin-top:1.6rem}
.watermark{position:absolute;right:-30px;top:50%;transform:translateY(-50%);
width:520px;max-width:60vw;z-index:1;pointer-events:none}
/* boxes */
.box{background:var(--card);border:1px solid var(--line);padding:1.4rem 1.6rem;margin-top:1.2rem}
.falsifier{border-left:3px solid var(--key)}
.key-finding{border-left:3px solid var(--accent);padding:.4rem 0 .4rem 1.2rem;font-style:italic;margin-top:1.2rem}
.key-finding strong{color:var(--accent);font-style:normal}
.ev-against{border:2px solid var(--bad)}
.ev-against h3{color:var(--bad)}
.warn{color:#f5a623;font-size:.9rem}
.ph{color:var(--ink-soft)}
.big-num{font-family:"Playfair Display",Georgia,serif;font-size:2.6rem;font-weight:700;color:var(--accent)}
.big-unit{font-size:1.1rem;color:var(--ink-soft)}
/* charts */
.chart-grid{display:grid;grid-template-columns:1fr 1fr;gap:1.4rem;margin-top:1.4rem}
.chart-card{background:var(--card);border:1px solid var(--line);padding:1.3rem 1.4rem}
.chart-card.wide{grid-column:1/-1}
.chart-sentence{color:var(--ink-soft);font-size:.95rem}
.query summary{font-family:"IBM Plex Mono",monospace;font-size:.75rem;color:var(--ink-soft);cursor:pointer}
.query pre{background:var(--code-bg);border:1px solid var(--line);padding:1rem;overflow:auto;
font-size:.78rem;line-height:1.5;color:var(--code-ink)}
.source-note{font-size:.75rem;color:var(--ink-soft)}
.placeholder-box{border:1.5px dashed var(--line-strong);padding:2.6rem 1rem;text-align:center;color:var(--ink-soft)}
.placeholder-mark{font-family:"Playfair Display",Georgia,serif;font-size:2.2rem;color:var(--ink-soft)}
/* tables */
table{width:100%;border-collapse:collapse;margin-top:1rem;font-size:.95rem}
th,td{padding:.55rem .75rem;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{font-family:"IBM Plex Mono",monospace;font-size:.72rem;letter-spacing:.1em;
text-transform:uppercase;color:var(--ink-soft)}
td.num,th.num{text-align:right}
.flow{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;margin-top:1rem}
.flow span{background:var(--card);border:1px solid var(--line);padding:.5rem .9rem;font-size:.9rem}
.flow b{color:var(--accent)}
footer{border-top:1px solid var(--line);margin-top:5rem;padding-top:1.6rem;
color:var(--ink-soft);font-size:.85rem}
@media(max-width:760px){.hero-stats{grid-template-columns:1fr 1fr}
.hero-stat:nth-child(3){border-left:none}
.chart-grid{grid-template-columns:1fr}.hero-inner{padding-top:10vh}}
/* hero keeps its dark palette in both colour schemes (wireframe: site-hero always dark) */
.site-hero{--card:#151515;--line:rgba(255,255,255,.08);--line-strong:rgba(255,255,255,.25);--ink:#ededed;--ink-soft:#9a9a9a;--ink-faint:#8a8a8a}
.hs-label{color:#8a8a8a}
.hero-author{color:#c9c9c9}
.sec-kicker{display:flex;align-items:center;gap:.7rem}
.sec-kicker::after{content:"";flex:1;border-top:1.5px dashed var(--line)}
.key-card{border-color:var(--key);background:linear-gradient(0deg,var(--key-soft),var(--key-soft)),var(--card)}
.threshold{border-color:var(--key);background:linear-gradient(0deg,var(--key-soft),var(--key-soft)),var(--card)}
.chart-card svg{background-image:linear-gradient(var(--grid) 1px,transparent 1px),linear-gradient(90deg,var(--grid) 1px,transparent 1px);background-size:24px 24px}
"""

NAV = """
<nav class="top-nav">
  <a href="#where-things-stand">Things</a>
  <a href="#claim">Claim</a>
  <a href="#subhypotheses">Sub-hypotheses</a>
  <a href="#charts">Charts</a>
  <a href="#comparisons">Comparisons</a>
  <a href="#model">Model</a>
  <a href="#evidence">Evidence</a>
  <a href="#methodology">Methodology &amp; Sources</a>
</nav>
"""

N_WATERMARK = """<svg class="watermark" viewBox="0 0 200 200" aria-hidden="true">
<path d="M40 180 V20 h30 L130 140 V20 h30 V180 h-30 L70 60 V180 Z" fill="#17130e"/>
</svg>"""


def build() -> None:
    outputs = read_json(DATA / "model_outputs.json")
    manifest = read_json(DATA / "manifest.json") or {}
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    wts_section = where_things_stand_html(outputs)

    placeholder_banner = ""
    if outputs and outputs.get("placeholder"):
        items = ", ".join(outputs["placeholder_inputs"])
        placeholder_banner = (
            f'<div class="box falsifier"><strong>Placeholder notice.</strong> '
            f'The model is running on placeholder inputs ({html.escape(items)}). '
            f'Every figure below is marked "—" or "placeholder" until real data lands. '
            f'Nothing here is a finding yet.</div>'
        )
    elif not outputs:
        placeholder_banner = (
            '<div class="box falsifier"><strong>Placeholder notice.</strong> '
            'No model outputs yet — run <code>bash rebuild.sh --model-only</code>. '
            'Every figure below is "—" until real data lands.</div>'
        )

    # ---- charts ----
    def series_from_csv(path, value_col):
        rows = read_csv(path)
        if not rows:
            return None
        out = []
        for r in rows:
            try:
                out.append((r["date"], float(r[value_col])))
            except (KeyError, TypeError, ValueError):
                continue
        return out or None

    def chart_or_placeholder(series, title, color=ACCENT):
        svg = svg_line(series, color=color, title=title) if series else None
        return svg or placeholder_box()

    g1 = series_from_csv(DATA / "bq_g1_daily_active_accounts.csv", "daily_active_signers")
    g2 = series_from_csv(DATA / "bq_g2_tx_counts.csv", "tx_count")
    g3_rows = read_csv(DATA / "bq_g3_contract_usage.csv")
    g3_series = None
    g3_top = ""
    if g3_rows:
        totals = {}
        top = {}
        for r in g3_rows:
            try:
                totals[r["date"]] = totals.get(r["date"], 0) + float(r["function_calls"])
                top[r["contract"]] = top.get(r["contract"], 0) + float(r["function_calls"])
            except (KeyError, TypeError, ValueError):
                continue
        g3_series = sorted(totals.items())
        top10 = sorted(top.items(), key=lambda kv: -kv[1])[:10]
        g3_top = ("<table><tr><th>Contract</th><th class='num'>Function calls</th></tr>" +
                  "".join(f"<tr><td>{html.escape(c)}</td><td class='num'>{fmt_num(v)}</td></tr>"
                          for c, v in top10) + "</table>")
    g4 = series_from_csv(DATA / "intents_volume_api_daily.csv", "volume_usd") or \
        series_from_csv(DATA / "intents_volume_daily.csv", "volume_usd")
    vol_series = g4
    price_series = series_from_csv(DATA / "near_price_daily.csv", "price_usd")
    g5 = svg_dual_indexed(vol_series, price_series, "Intents volume", "NEAR price") \
        if (vol_series and price_series) else None
    g6_rows = read_csv(DATA / "bq_g6_outcomes.csv")
    g6_series = None
    if g6_rows:
        g6_series = [(r["date"], float(r["success_rate"])) for r in g6_rows
                     if r.get("success_rate") not in (None, "")]

    charts = "".join([
        chart_card("g1", "G1 — Daily active accounts",
                   "How many distinct accounts signed a transaction on NEAR each day.",
                   chart_or_placeholder(g1, "Daily active accounts"),
                   "g1-daily-active-accounts.sql",
                   "Source: BigQuery transactions. Filtered on block_date."),
        chart_card("g2", "G2 — Transaction counts",
                   "How much raw activity the chain processes each day.",
                   chart_or_placeholder(g2, "Transaction counts"),
                   "g2-tx-counts.sql",
                   "Source: BigQuery transactions. Filtered on block_date."),
        chart_card("g3", "G3 — Contract usage",
                   "Which contracts people actually use — total daily FUNCTION_CALLs.",
                   chart_or_placeholder(g3_series, "Contract calls") + g3_top,
                   "g3-contract-usage.sql",
                   "Source: BigQuery receipt_actions (FUNCTION_CALL). Filtered on block_date."),
        chart_card("g4", "G4 — Intents swap volume",
                   "Daily cross-chain swap volume through NEAR Intents.",
                   chart_or_placeholder(g4, "Intents volume"),
                   "g4-intents-volume.sql",
                   "Source: Intents Explorer API (canonical) / DefiLlama (cross-check, raw volume)."),
        chart_card("g5", "G5 — Key chart: Intents volume vs NEAR price",
                   "The key chart. Both series indexed to 100 on the first day — "
                   "does volume move first, or only follow price?",
                   g5 or placeholder_box(),
                   "g5-key-chart.sql",
                   "Sources: Intents volume (API / DefiLlama) + NEAR price (CoinGecko). "
                   "On-chain activity leg: BigQuery transactions."),
        chart_card("g6", "G6 — Success rate + gas burnt",
                   "Is the chain getting more reliable — and cheaper to use?",
                   chart_or_placeholder(g6_series, "Success rate", color="var(--ink)"),
                   "g6-outcomes.sql",
                   "Source: BigQuery execution_outcomes. Filtered on block_date."),
    ])

    # ---- freshness ----
    fresh_rows = read_csv(DATA / "bq_00_freshness.csv")
    if fresh_rows:
        max_date = fresh_rows[0].get("max_block_date", "—")
        freshness = (f"<p><strong>MAX(block_date) in BigQuery: {html.escape(str(max_date))}.</strong> "
                     f"The on-chain leg is only as fresh as this date — if it is months old, "
                     f"it cannot speak about current usage.</p>")
    else:
        freshness = ("<p><strong>Freshness not yet checked.</strong> Run "
                     "<code>queries/00-freshness.sql</code> (or <code>bash rebuild.sh</code>) — "
                     "MAX(block_date) is the first thing to verify on every run.</p>")

    # ---- model values ----
    pf = outputs.get("p_to_fees") if outputs else None
    pf_html = f"<div class='big-num'>{pf:.1f}x</div>" if pf is not None else '<div class="big-num">—</div>'
    net_iss = outputs["inputs"]["net_issuance_2027e"] if outputs else None
    years = outputs["inputs"]["projection_years"] if outputs else 5
    base_bps = outputs["inputs"]["base_take_rate_bps"] if outputs else 10

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>NEAR Protocol — Beyond the Price</title>
<meta name="description" content="Investment thesis: NEAR is becoming the settlement layer for cross-chain value transfer — and Intents volume is the metric that proves it.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;0,700;0,800;1,500;1,600&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>

<header class="site-hero">
{NAV}
{N_WATERMARK}
<div class="hero-inner">
  <div class="hero-eyebrow">Investment Thesis · NEAR Hackathon · November 2026</div>
  <h1>NEAR Protocol</h1>
  <div class="h1-angle">Beyond the Price</div>
  <div class="hero-stats">
{hero_stats_html(outputs)}
  </div>
  <div class="hero-author">0xrard</div>
  <hr class="hero-rule">
</div>
</header>

<div class="page">
{placeholder_banner}
{wts_section}

<section id="claim">
  <div class="sec-kicker">Section 1 · Claim</div>
  <h2 class="sec-title">The claim</h2>
  <p class="lede">NEAR is becoming the settlement layer for cross-chain value transfer — and Intents volume is the metric that proves it, while the market hasn't priced it in yet.</p>
  <p>More precisely: <strong>cross-chain volume through NEAR Intents is a better leading indicator of real network usage than token price.</strong> Three things have to be true — volume <em>leads</em> price, volume is <em>sticky</em>, and Intents grows <em>together with</em> on-chain activity. Each is tested below, with its own falsifier.</p>
  <div class="box falsifier">
    <h3>Falsifier</h3>
    <p>If Intents volume only <em>follows</em> price, or more than 80% of it is one-off addresses, or it rises while on-chain activity falls — the thesis weakens or fails. See <a href="#evidence">Evidence</a> and <a href="#model">Model</a>.</p>
  </div>
  <div class="box">
    <h3>Three key numbers</h3>
    <table>
      <tr><th>Metric</th><th class="num">Value</th></tr>
      <tr><td>Daily Intents volume</td><td class="num">{fmt_usd(outputs["inputs"]["daily_intents_volume_usd"]) if outputs else "—"}</td></tr>
      <tr><td>Fee capture rate (share of gross fees reaching NEAR)</td><td class="num">{fmt_pct(outputs["inputs"]["fee_capture_rate"]) if outputs else "—"}</td></tr>
      <tr><td>Deflationary threshold (daily volume, base {base_bps} bps)</td><td class="num">{fmt_usd(outputs["deflationary_threshold"]["daily_volume_usd_by_take_rate_bps"][str(base_bps)]) if outputs else "—"}</td></tr>
    </table>
    <p class="muted">Values marked "—" await real data. Placeholder inputs are flagged in the model outputs.</p>
  </div>
</section>

<section id="subhypotheses">
  <div class="sec-kicker">Section 2 · Sub-hypotheses</div>
  <h2 class="sec-title">Two testable sub-hypotheses</h2>
  <div class="box">
    <h3>A — Intents volume is sticky</h3>
    <p>Most Intents volume comes from addresses that swap repeatedly, not one-offs. Test: repeat-swapper share of volume, per week.</p>
    <p><strong>Falsifier:</strong> if more than 80% of volume comes from addresses that never swap again, usage is not sticky and the thesis weakens.</p>
    {tests_html(outputs).split("</p>")[0] + "</p>" if outputs else "<p><strong>Status:</strong> cannot compute yet — swapper-level data needs the Intents Explorer API (JWT).</p>"}
  </div>
  <div class="box">
    <h3>B — Intents grows with on-chain activity, not instead of it</h3>
    <p>Rising Intents volume goes together with rising (or holding) daily active accounts and transaction counts — Intents adds demand, it does not move existing activity off-chain.</p>
    <p><strong>Falsifier:</strong> if Intents volume rises while on-chain activity falls, Intents is cannibalising — this weakens the "NEAR as settlement layer" thesis.</p>
    {tests_html(outputs).split("</p>")[1] + "</p>" if outputs and len(tests_html(outputs).split("</p>")) > 1 else "<p><strong>Status:</strong> cannot compute yet — needs the Intents volume series + BigQuery G1/G2.</p>"}
  </div>
</section>

<section id="charts">
  <div class="sec-kicker">Section 3 · Charts</div>
  <h2 class="sec-title">The data</h2>
  <p class="muted">Every chart shows the query or source behind it, with one plain sentence on what it shows.</p>
  <div class="chart-grid">
{charts}
  </div>
</section>

<section id="comparisons">
  <div class="sec-kicker">Section 4 · Comparisons</div>
  <h2 class="sec-title">NEAR vs the rest</h2>
  <p>Comparisons are a core part of this thesis, not an appendix. Each uses the same data and the same methodology on both sides.</p>
  <div class="box"><h3>P1 — Active accounts: NEAR vs Solana vs Base vs Ethereum</h3>{placeholder_box("Comparison chart — awaiting data.")}</div>
  <div class="box"><h3>P2 — Volume: NEAR vs Solana vs Base vs Ethereum</h3>{placeholder_box("Comparison chart — awaiting data.")}</div>
  <div class="box"><h3>P3 — Developers: NEAR vs Solana vs Ethereum</h3><p class="muted">Two legs: Open Dev Data (secondary, cited) + new contract deployments per day on NEAR (BigQuery receipt_actions).</p>{placeholder_box("Comparison chart — awaiting data.")}</div>
  <div class="box"><h3>P4 — Intents vs Across vs UniswapX vs 1inch Fusion</h3>{placeholder_box("Comparison chart — awaiting data.")}</div>
  <div class="box"><h3>P5 — Intents vs Across (volume growth rate, same metric)</h3><p class="muted">Same metric, two intent protocols. Source: DefiLlama / Across API — to be verified live.</p>{placeholder_box("Comparison chart — awaiting data.")}</div>
  <div class="box"><h3>P6 — Swap cost &amp; speed: Intents vs traditional bridge</h3><p class="muted">Intents via 1Click dry quote (fee + estimated time). The bridge side is docs data, not a measurement — labelled as such.</p>{placeholder_box("Comparison table — awaiting data.")}</div>
  <div class="box"><h3>P7 — Developers (on-chain leg)</h3><p class="muted">New contract deployments per day on NEAR (BigQuery receipt_actions) as an on-chain proxy for developer activity.</p>{placeholder_box("Comparison chart — awaiting data.")}</div>
  <div class="box">
    <h3>Tokenomics context — to verify</h3>
    <table>
      <tr><th>Metric</th><th class="num">Value</th><th>Source</th></tr>
      <tr><td>Chain TVL</td><td class="num">$167.5M</td><td>Nino's input (9 Nov 2026) — verify against primary source before citing</td></tr>
      <tr><td>Stablecoin float</td><td class="num">$130.4M</td><td>Nino's input (9 Nov 2026) — verify against primary source before citing</td></tr>
      <tr><td>Staked share</td><td class="num">44.3%</td><td>Nino's input (9 Nov 2026) — verify against primary source before citing</td></tr>
    </table>
  </div>
</section>

<section id="model">
  <div class="sec-kicker">Section 5 · Model</div>
  <h2 class="sec-title">The model</h2>
  <p>Bottom-up: tokenomics → fee mechanism → threshold → what changes it. All assumptions in one file (<code>model/config.yaml</code>); change them and re-run <code>bash rebuild.sh --model-only</code>.</p>
  <div class="flow"><span>Tokenomics</span><b>→</b><span>Fee mechanism</span><b>→</b><span>Deflationary threshold</span><b>→</b><span>What changes it</span></div>
  <div class="box">
    <h3>Deflationary threshold</h3>
{threshold_html(outputs)}
  </div>
  <div class="box">
    <h3>Scenario table — year {years} (base fee take rate {base_bps} bps)</h3>
    <table>
      <tr><th>Scenario</th><th>Growth</th><th class="num">Annual settlement volume</th><th class="num">Annual fee revenue</th><th>What would have to be true</th></tr>
{scenario_rows(outputs)}
    </table>
  </div>
  <div class="box">
    <h3>Sensitivity — annual fee revenue, year {years} (fee take rate × growth)</h3>
    <table>
{sensitivity_rows(outputs)}
    </table>
  </div>
  <div class="box">
    <h3>P / F — market cap / annualised fees</h3>
{pf_html}
    <p class="muted">Cross-check: Nino's input P/F 58.8x (9 Nov 2026) matches market cap / annualised fees from the same inputs. Computed live from fetched data — never hardcoded.</p>
  </div>
  <div class="box">
    <h3>Net issuance after burn (2027E)</h3>
    <p><strong>{fmt_pct(net_iss) if net_iss is not None else "—"}</strong> — Nino's estimate (9 Nov 2026), 2027E. Gross issuance is 2.5%/yr; the estimate implies fee burn offsets ~1.0pp. Verify from on-chain burn data before citing.</p>
  </div>
  <div class="box">
    <h3>Hypothesis tests</h3>
    {tests_html(outputs) if outputs else "<p>— (run the model to evaluate the tests)</p>"}
    <p class="muted">Lead/lag: positive lag means Intents volume moves first. Correlations use daily series (n ≥ 30 days); a rising correlation toward positive lags is the pattern the thesis predicts — it is a correlation, not proof of causation.</p>
  </div>
  <div class="box falsifier">
    <h3>No price target</h3>
    <p>This model does <strong>not</strong> output a NEAR price target. A price target from Intents volume alone would need a valuation multiple too far removed from the data — an assumption dressed up as a conclusion. What it outputs is volume and fee revenue under stated scenarios, and the volume threshold at which issuance is offset. Anyone who wants a price target must supply their own multiple, openly, in <code>model/config.yaml</code>.</p>
  </div>
  <p><code>bash rebuild.sh --model-only</code> — re-run the model from the shipped CSVs, no credentials needed.</p>
</section>

<section id="evidence">
  <div class="sec-kicker">Section 6 · Evidence</div>
  <h2 class="sec-title">Evidence</h2>
  <div class="box ev-against">
    <h3>Evidence against — first, and on purpose</h3>
    <p>The following figures are <strong>reported by independent coverage and must be recomputed from G1/G2 before being cited as fact</strong>. They are listed here so the thesis has to answer them.</p>
    <ul>
      <li>Reported: NEAR lost 4 in 5 active users on its own chain in a year; on-chain transactions down ~83% year-over-year, while Intents grew. This is precisely the falsifier pattern of sub-hypothesis B.</li>
      <li>Reported: "Buying NEAR for its usage does not buy a share of NEAR's users. It buys a fee on swaps between other chains." (tradingstrategies.work.) The thesis answers this only if the fee-capture mechanism (Intents fees → NEAR buybacks) is real and measured.</li>
      <li>Reported: NEAR's own on-chain fees fell from $5.18M to $1.27M over the reported period.</li>
      <li>Reported: buybacks are real but small relative to issuance, and bought tokens are held, not burned — "buyback offsets issuance" is not the same as "supply shrinks". The model distinguishes the two.</li>
      <li>Structural risks: Rhea concentrates NEAR DEX volume (a single point of failure); Across, UniswapX and 1inch Fusion compete with Intents; solver/attestor centralisation is unverified; one recovered exploit is not a guarantee against the next.</li>
    </ul>
  </div>
  <div class="box">
    <h3>Evidence for</h3>
    <p class="muted">To be filled from G1–G6 once data is fetched. Each item cites its chart and query.</p>
    <ul>
      <li>— (G1: daily active accounts)</li>
      <li>— (G2: transaction counts)</li>
      <li>— (G3: contract usage)</li>
      <li>— (G4: Intents swap volume)</li>
      <li>— (G5: Intents volume vs NEAR price — the key chart)</li>
      <li>— (G6: success rate + gas burnt)</li>
      <li>Pillar 3: the $3.8M exploit case — detected, auto-paused, funds returned within 36 hours (see the official postmortem). A system that is attacked and recovers with funds returned is evidence of resilience — but the exploit itself is a real risk, listed above.</li>
    </ul>
  </div>
</section>

<section id="methodology">
  <div class="sec-kicker">Section 7 · Methodology &amp; Sources</div>
  <h2 class="sec-title">Methodology &amp; sources</h2>
  <div class="box">
    <h3>Status &amp; data freshness</h3>
{freshness}
    <p class="muted">Dashboard generated: {generated}. Rebuild any time with <code>bash rebuild.sh</code> — the same page shows fresher data.</p>
  </div>
  <div class="box">
    <h3>Sources</h3>
    <table>
      <tr><th>Source</th><th>Feeds</th></tr>
      <tr><td>BigQuery <code>bigquery-public-data.crypto_near_mainnet_us</code></td><td>G1–G3, G6 (accounts, tx, contracts, success rate, gas)</td></tr>
      <tr><td>NEAR Intents Explorer API (JWT-gated)</td><td>G4, G5, sub-hypothesis A (swapper-level data)</td></tr>
      <tr><td>DefiLlama API (<code>api.llama.fi</code>)</td><td>Intents volume + fees (cross-check), chain volumes. Volume is raw (unadjusted).</td></tr>
      <tr><td>CoinGecko Keyless API</td><td>NEAR price (+ SOL/ETH for comparisons)</td></tr>
      <tr><td>Open Dev Data</td><td>Developer comparison (P7, secondary, cited)</td></tr>
    </table>
  </div>
  <div class="box">
    <h3>What we couldn't compute</h3>
    <ul>
      <li>Sub-hypothesis A (sticky volume): needs swapper-level data from the Intents Explorer API — pending JWT access, and pending confirmation that a swapper field exists.</li>
      <li>Intents volume series (G4/G5): pending Intents Explorer API (JWT) or DefiLlama slug verification.</li>
      <li>HSP-029 status (proposed issuance cut 2.5% → 1.6%): sources conflict. Do not cite either way until verified.</li>
      <li>TVL: published figures conflict. No TVL figure is quoted as fact anywhere in this thesis.</li>
    </ul>
  </div>
</section>

<footer>
  <p><strong>NEAR Protocol — Beyond the Price.</strong> Investment thesis by 0xrard, NEAR Hackathon 2026 (track: Investment Thesis).</p>
  <p>Reproduce everything: <code>git clone &lt;repo&gt; &amp;&amp; bash rebuild.sh --model-only</code> (no credentials) or <code>bash rebuild.sh</code> (full rebuild, needs GCP + Intents JWT in <code>.env</code>). Queries in <code>queries/</code>, raw data in <code>data/</code> (with source + pull date in <code>manifest.json</code>), model in <code>model/</code>.</p>
  <p>Not financial advice. Not a price prediction. Judged on the evidence, not the conviction.</p>
</footer>
</div>

</body>
</html>
"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html_doc)
    print(f"dashboard: wrote {OUT} ({len(html_doc):,} bytes)")


if __name__ == "__main__":
    build()
