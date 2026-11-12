#!/usr/bin/env python3
"""Scenario model + deflationary-threshold recomputation + hypothesis tests.

Stdlib only — Level 2 (model-only rebuild) needs nothing but Python 3.10+.

Reads:
  - model/config.yaml (ALL assumptions in one file)
  - data/*.csv and data/*.json if present (fetched by scripts/fetch.py)

Writes:
  - data/model_outputs.json (consumed by scripts/build_dashboard.py)

What it computes, from primary data only:
  1. Hero stats (4): cumulative Intents volume, annualised fees (30d
     run-rate), market cap, inflation rate — each with source + as-of date.
  2. Deflationary threshold: daily Intents volume at which buybacks offset
     new issuance, recomputed from current fee rate, issuance and price.
     Price-dependent: the higher the NEAR price, the further the threshold.
  3. Scenario table (bear/base/bull): implied annual settlement volume +
     implied annual fee revenue at year N, fee take rate as an open
     parameter (sensitivity 5/10/20 bps).
  4. Sensitivity table: fee take rate x growth rate -> annual fee revenue.
  5. P/F (market cap / annualised fees) when both inputs exist.
  6. Hypothesis tests: A (sticky — needs swapper data), B (additive —
     correlation volume vs on-chain activity), lead/lag (does volume lead
     price?).

The model does NOT output a NEAR price target (see THESIS.md §6).
"""

import csv
import json
import math
import statistics
import sys
from datetime import date as _date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CONFIG = ROOT / "model" / "config.yaml"
OUT = DATA / "model_outputs.json"


# ------------------------------------------------------------ YAML ---

def _scalar(text: str):
    text = text.strip()
    if text in ("null", "~", ""):
        return None
    if text in ("true", "True"):
        return True
    if text in ("false", "False"):
        return False
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return [_scalar(p) for p in inner.split(",")] if inner else []
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def _strip_comment(line: str) -> str:
    in_s = in_d = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def _parse_yaml_minimal(text: str):
    """Minimal YAML subset: nested mappings by indentation, inline lists,
    block lists, scalars. Only for the known shape of config.yaml."""
    root = {}
    stack = [(-1, root)]  # (indent, container)
    pending_key = None  # (indent, parent_dict, key) awaiting a block value
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        if "\t" in line[: len(line) - len(line.lstrip())]:
            raise ValueError("tabs are not allowed in config.yaml")
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if stripped.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"list item without a list parent: {line!r}")
            parent.append(_scalar(stripped[2:]))
            continue
        if ":" not in stripped:
            raise ValueError(f"cannot parse line in config.yaml: {line!r}")
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if isinstance(parent, list):
            raise ValueError(f"mapping key inside a list: {line!r}")
        if value == "":
            # Block value follows: dict or list — decide on next line.
            parent[key] = {}
            pending_key = (indent, parent, key)
        else:
            parent[key] = _scalar(value)
            pending_key = None
        if pending_key is not None and indent == pending_key[0]:
            # The next deeper line will resolve the pending container.
            pass
        # Resolve a pending key when the next line is deeper.
        if pending_key is not None and indent > pending_key[0]:
            p_indent, p_parent, p_key = pending_key
            if stripped.startswith("- "):
                p_parent[p_key] = []
            stack.append((p_indent, p_parent[p_key]))
            pending_key = None
        if value == "":
            stack.append((indent, parent[key]))
    return root


def load_config() -> dict:
    text = CONFIG.read_text()
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return _parse_yaml_minimal(text)


# ------------------------------------------------------------ data ---

def read_series(path: Path, value_col: str):
    """Read a date,value CSV -> sorted [(date, value)] or None if missing."""
    if not path.exists():
        return None
    # One value per date. If a date appears twice (e.g. CoinGecko appends a
    # live "now" point after the last daily point), the LAST row in the file
    # wins. Sorting (date, value) tuples instead would pick by value, not by
    # recency.
    by_date = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                by_date[row["date"]] = float(row[value_col])
            except (KeyError, TypeError, ValueError):
                continue
    return sorted(by_date.items()) or None


def log_returns(series):
    """{date: ln(value_t / value_{t-1 day})}, consecutive calendar days with
    positive values only. Correlating CHANGES instead of LEVELS avoids the
    spurious correlation two trending series show."""
    m = dict(series)
    out = {}
    for d, v in series:
        prev = (_date.fromisoformat(d) - timedelta(days=1)).isoformat()
        if prev in m and v > 0 and m[prev] > 0:
            out[d] = math.log(v / m[prev])
    return out


def read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def latest(series):
    return series[-1][1] if series else None


def pearson(xs, ys):
    """Pearson r or None (too few points / constant input)."""
    if len(xs) < 30 or len(xs) != len(ys):
        return None
    try:
        return statistics.correlation(xs, ys)
    except statistics.StatisticsError:
        return None


# ------------------------------------------------------------ model ---

def main() -> int:
    cfg = load_config()
    manifest = read_json(DATA / "manifest.json") or {}

    placeholder_inputs = []

    # --- Inputs: prefer fetched data, fall back to config placeholders. ---
    vol_api = read_series(DATA / "intents_volume_api_daily.csv", "volume_usd")
    vol_dl = read_series(DATA / "intents_volume_daily.csv", "volume_usd")
    vol_series = vol_api or vol_dl
    if vol_series is not None:
        # Starting daily volume = average of the last N days of the series
        # (window from config, default 30), NOT the last single day: a
        # single day is volatile and swings the scenarios ~2x between runs.
        window = int(cfg.get("volume_window_days") or 30)
        window_rows = vol_series[-window:] if len(vol_series) >= window else vol_series
        daily_volume = sum(v for _, v in window_rows) / len(window_rows)
        volume_source = (("Intents Explorer API" if vol_api is not None
                          else "DefiLlama /summary/dexs")
                         + f" ({len(window_rows)}-day average, "
                         + f"{window_rows[0][0]} to {window_rows[-1][0]})")
    elif cfg.get("current_daily_intents_volume_usd") is not None:
        daily_volume = float(cfg["current_daily_intents_volume_usd"])
        volume_source = "model/config.yaml"
    else:
        daily_volume = float(cfg["placeholder_daily_volume_usd"])
        volume_source = "model/config.yaml (PLACEHOLDER)"
        placeholder_inputs.append("daily Intents volume")

    price_series = read_series(DATA / "near_price_daily.csv", "price_usd")
    if price_series is not None:
        near_price = latest(price_series)
        price_source = "CoinGecko market_chart"
    elif cfg.get("near_price_usd") is not None:
        near_price = float(cfg["near_price_usd"])
        price_source = "model/config.yaml"
    else:
        near_price = float(cfg["placeholder_near_price_usd"])
        price_source = "model/config.yaml (PLACEHOLDER)"
        placeholder_inputs.append("NEAR price")

    if cfg.get("total_supply_near") is not None:
        supply = float(cfg["total_supply_near"])
        supply_source = "model/config.yaml"
    else:
        supply = float(cfg["placeholder_total_supply_near"])
        supply_source = "model/config.yaml (PLACEHOLDER)"
        placeholder_inputs.append("total NEAR supply")

    issuance_rate = float(cfg["issuance"]["annual_rate"])
    net_issuance_2027e = float(cfg["issuance"]["net_issuance_2027e"])
    take_rates_bps = [int(b) for b in cfg["fee"]["take_rates_bps"]]
    base_bps = int(cfg["fee"]["base_take_rate_bps"])
    capture_rate = float(cfg["fee"]["capture_rate"])
    if base_bps not in take_rates_bps:
        # Fail fast: the summary print at the end indexes the fee table by
        # base_bps, so a base outside the grid would crash AFTER the outputs
        # are written — a confusing late failure for a config typo.
        print(f"model: ERROR - base_take_rate_bps ({base_bps}) is not in "
              f"take_rates_bps ({take_rates_bps}); add it to the grid in "
              f"model/config.yaml.", file=sys.stderr)
        return 1
    if cfg["fee"].get("capture_rate_is_placeholder", False):
        # Explicit flag in model/config.yaml (not a magic number): set it
        # to true whenever capture_rate is an unmeasured assumption.
        placeholder_inputs.append("fee capture rate")
    years = int(cfg["projection_years"])

    # --- Hero stats (4). ---
    dexs = read_json(DATA / "defillama_intents_dexs.json") or {}
    fees_json = read_json(DATA / "defillama_intents_fees.json") or {}
    market = read_json(DATA / "near_market.json") or {}

    # DefiLlama /summary/dexs names the field totalAllTime (not totalVolume).
    # Fallback: sum of the daily chart — verified to equal totalAllTime.
    cumulative_volume = dexs.get("totalAllTime") or dexs.get("totalVolume")
    cumulative_volume_source = "DefiLlama /summary/dexs (totalAllTime)"
    if cumulative_volume is not None:
        cumulative_volume = float(cumulative_volume)
    elif vol_series is not None:
        cumulative_volume = sum(v for _, v in vol_series)
        cumulative_volume_source = "DefiLlama daily volume chart (summed)"

    fees_series = read_series(DATA / "intents_fees_daily.csv", "fees_usd")
    if fees_json.get("total30d") is not None:
        annualised_fees = float(fees_json["total30d"]) * 12
        fees_source = "DefiLlama /summary/fees (total30d x 12)"
    elif fees_series is not None:
        last_30 = [v for _, v in fees_series[-30:]]
        annualised_fees = sum(last_30) * 12 if len(last_30) >= 30 else None
        fees_source = "DefiLlama daily fees (last 30d x 12)"
    else:
        annualised_fees = None
        fees_source = None

    market_cap = market.get("market_cap_usd")
    if market_cap is not None:
        market_cap = float(market_cap)

    def as_of(filename):
        entry = manifest.get(filename, {})
        return entry.get("pulled_at_utc")

    hero_stats = {
        "cumulative_intents_volume_usd": cumulative_volume,
        "cumulative_intents_volume_source": cumulative_volume_source,
        "cumulative_intents_volume_as_of": as_of("defillama_intents_dexs.json"),
        "annualised_fees_usd": annualised_fees,
        "annualised_fees_definition": "Gross Intents fees, 30-day run-rate (total30d x 12)",
        "annualised_fees_source": fees_source,
        "annualised_fees_as_of": as_of("defillama_intents_fees.json"),
        "market_cap_usd": market_cap,
        "market_cap_source": "CoinGecko /coins/near",
        "market_cap_as_of": as_of("near_market.json"),
        "inflation_rate": issuance_rate,
        "inflation_source": "Protocol parameter (5% -> 2.5% on 30 Oct 2025)",
    }

    # --- Deflationary threshold. ---
    # Annual issuance value = supply * issuance_rate * price.
    # Annual buyback at daily volume V = V * 365 * take_rate * capture_rate.
    # Threshold V = issuance value / (365 * take_rate * capture_rate).
    annual_issuance_value = supply * issuance_rate * near_price
    threshold = {}
    for bps in take_rates_bps:
        take_rate = bps / 10000.0
        denom = 365 * take_rate * capture_rate
        threshold[str(bps)] = annual_issuance_value / denom if denom else None

    # --- Scenario table + sensitivity. ---
    scenarios = []
    for name in ("bear", "base", "bull"):
        sc = cfg["scenarios"][name]
        g = float(sc["annual_growth"])
        annual_volume_y = daily_volume * 365 * (1 + g) ** years
        scenarios.append({
            "name": name,
            "annual_growth": g,
            "annual_settlement_volume_usd": annual_volume_y,
            "annual_fee_revenue_usd_by_bps": {
                str(bps): annual_volume_y * bps / 10000.0 for bps in take_rates_bps
            },
            "fee_revenue_basis": "gross protocol fees (volume x take rate), before capture_rate",
            "what_must_be_true": sc["what_must_be_true"],
        })

    growth_grid = sorted({float(cfg["scenarios"][s]["annual_growth"])
                          for s in ("bear", "base", "bull")})
    sensitivity = {
        "growth_rates": growth_grid,
        "take_rates_bps": take_rates_bps,
        # rows: growth rate -> {bps: year-N annual fee revenue}
        "annual_fee_revenue_usd": {
            str(g): {
                str(bps): daily_volume * 365 * (1 + g) ** years * bps / 10000.0
                for bps in take_rates_bps
            }
            for g in growth_grid
        },
    }

    # --- P/F (market cap / annualised fees), when both inputs exist. ---
    p_to_fees = None
    if market_cap is not None and annualised_fees:
        p_to_fees = market_cap / annualised_fees

    # --- Hypothesis tests. ---
    # A: needs swapper-level data (Intents Explorer API) — not in any CSV.
    test_a = {
        "status": "cannot_compute",
        "reason": ("Swapper-level data not available: the Intents Explorer API "
                   "needs a JWT (see THESIS.md §8). If the API has no swapper "
                   "field, this stays uncomputed."),
    }

    # B: correlation of daily Intents volume vs on-chain activity.
    # PRIMARY = Pearson r on daily log changes (volume growth vs activity
    # growth). Levels of two trending series correlate (or anti-correlate)
    # mostly because of their trends, so level correlations are reported
    # separately as descriptive only.
    g1 = read_series(DATA / "bq_g1_daily_active_accounts.csv", "daily_active_signers")
    g2 = read_series(DATA / "bq_g2_tx_counts.csv", "tx_count")
    test_b = {"status": "cannot_compute", "reason": None}
    if vol_series is not None and (g1 is not None or g2 is not None):
        vol_map = dict(vol_series)
        vol_ret = log_returns(vol_series)
        details, levels = {}, {}
        for label, series in (("active_accounts", g1), ("tx_count", g2)):
            if series is None:
                continue
            s_map = dict(series)
            common_l = sorted(set(vol_map) & set(s_map))
            levels[label] = {
                "n_days": len(common_l),
                "pearson_r": pearson([vol_map[d] for d in common_l],
                                     [s_map[d] for d in common_l]),
            }
            s_ret = log_returns(series)
            common = sorted(set(vol_ret) & set(s_ret))
            details[label] = {
                "n_days": len(common),
                "pearson_r": pearson([vol_ret[d] for d in common],
                                     [s_ret[d] for d in common]),
            }
        if any(d.get("pearson_r") is not None for d in details.values()):
            test_b = {
                "status": "computed",
                "reason": None,
                "method": "Pearson r on daily log changes (primary); levels below are descriptive only",
                "correlations": details,
                "correlations_levels": levels,
            }
        else:
            test_b["reason"] = "Not enough overlapping days (<30) to compute a correlation."
    else:
        missing = []
        if vol_series is None:
            missing.append("Intents volume series")
        if g1 is None and g2 is None:
            missing.append("BigQuery G1/G2 series")
        test_b["reason"] = "Missing data: " + ", ".join(missing) + "."

    # Lead/lag: does Intents volume lead NEAR price?
    # PRIMARY = correlation of daily log changes (same method as fig9).
    lead_lag = {"status": "cannot_compute", "reason": None,
                "method": ("Pearson r of daily log changes: volume growth[t-k] vs price "
                           "return[t]; k>0 means volume leads. Best lag chosen by |r|. "
                           "Levels are in lags_levels (descriptive only)."),
                "lags": {}, "lags_levels": {}, "best_lag_days": None}
    if vol_series is not None and price_series is not None:
        vol_map = dict(vol_series)
        price_map = dict(price_series)
        vol_ret = log_returns(vol_series)
        px_ret = log_returns(price_series)

        def shift(dstr, days):
            return (_date.fromisoformat(dstr) + timedelta(days=days)).isoformat()

        for lag in range(-7, 8):
            # lag k > 0: volume on day (t - k) vs price on day t  =>  volume leads by k days.
            pairs = [(vol_ret[shift(d, -lag)], r) for d, r in px_ret.items()
                     if shift(d, -lag) in vol_ret]
            if len(pairs) >= 30:
                lead_lag["lags"][str(lag)] = {
                    "n_days": len(pairs),
                    "pearson_r": pearson([p[0] for p in pairs], [p[1] for p in pairs]),
                }
            pairs_l = [(vol_map[shift(d, -lag)], price_map[d])
                       for d in sorted(price_map) if shift(d, -lag) in vol_map]
            if len(pairs_l) >= 30:
                lead_lag["lags_levels"][str(lag)] = {
                    "n_days": len(pairs_l),
                    "pearson_r": pearson([p[0] for p in pairs_l], [p[1] for p in pairs_l]),
                }
        valid = {int(k): v["pearson_r"] for k, v in lead_lag["lags"].items()
                 if v["pearson_r"] is not None}
        if valid:
            best = max(valid, key=lambda k: abs(valid[k]))
            n_best = lead_lag["lags"][str(best)]["n_days"]
            band = 1.96 / math.sqrt(n_best)
            lead_lag.update({
                "status": "computed", "best_lag_days": best,
                "best_pearson_r": valid[best],
                "noise_band_95": band,
                "best_is_significant": abs(valid[best]) > band,
            })
        else:
            lead_lag["reason"] = "Not enough overlapping days (<30) at any lag."
    else:
        missing = []
        if vol_series is None:
            missing.append("Intents volume series")
        if price_series is None:
            missing.append("NEAR price series")
        lead_lag["reason"] = "Missing data: " + ", ".join(missing) + "."

    outputs = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "placeholder": bool(placeholder_inputs),
        "placeholder_inputs": sorted(set(placeholder_inputs)),
        "inputs": {
            "daily_intents_volume_usd": daily_volume,
            "daily_intents_volume_source": volume_source,
            "near_price_usd": near_price,
            "near_price_source": price_source,
            "total_supply_near": supply,
            "total_supply_source": supply_source,
            "issuance_annual_rate": issuance_rate,
            "net_issuance_2027e": net_issuance_2027e,
            "net_issuance_2027e_note": ("Nino's estimate (9 Nov 2026), 2027E — "
                                        "verify from on-chain burn data before citing."),
            "fee_take_rates_bps": take_rates_bps,
            "base_take_rate_bps": base_bps,
            "fee_capture_rate": capture_rate,
            "projection_years": years,
        },
        "hero_stats": hero_stats,
        "deflationary_threshold": {
            "daily_volume_usd_by_take_rate_bps": threshold,
            "annual_issuance_value_usd": annual_issuance_value,
            "note": ("Daily Intents volume at which buybacks offset new issuance. "
                     "Price-dependent: the higher the NEAR price, the further the threshold. "
                     "Recomputed from primary data — never copied from any published figure."),
        },
        "scenarios": scenarios,
        "sensitivity": sensitivity,
        "p_to_fees": p_to_fees,
        "p_to_fees_note": ("Market cap / annualised gross fees (30d x 12). Nino's 9 Nov "
                           "2026 dossier input (P/F 58.8x) was computed at that earlier "
                           "date; compare only at the same date."),
        "hypothesis_tests": {
            "A_sticky": test_a,
            "B_additive": test_b,
            "lead_lag_volume_vs_price": lead_lag,
        },
    }

    DATA.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(outputs, indent=2))
    print(f"model: wrote {OUT}")
    print(f"model: placeholder={outputs['placeholder']}"
          + (f" ({', '.join(outputs['placeholder_inputs'])})" if outputs["placeholder"] else ""))
    print(f"model: daily volume ${daily_volume:,.0f} ({volume_source}); "
          f"NEAR ${near_price} ({price_source})")
    print("model: deflationary threshold (daily volume, USD): " +
          ", ".join(f"{bps}bps=${v:,.0f}" for bps, v in threshold.items()))
    for sc in scenarios:
        print(f"model: {sc['name']} g={sc['annual_growth']:.0%} -> "
              f"year-{years} volume ${sc['annual_settlement_volume_usd']:,.0f}, "
              f"fee @{base_bps}bps ${sc['annual_fee_revenue_usd_by_bps'][str(base_bps)]:,.0f}")
    print(f"model: P/F = {p_to_fees:.1f}x" if p_to_fees is not None else "model: P/F = — (inputs missing)")
    print(f"model: tests A={test_a['status']}, B={test_b['status']}, "
          f"lead/lag={lead_lag['status']}"
          + (f" (best lag {lead_lag['best_lag_days']}d)" if lead_lag.get("best_lag_days") is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
