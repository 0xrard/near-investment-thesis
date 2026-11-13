#!/usr/bin/env python3
"""Build dashboard/index-generated.html (the Live Check page).

The live build is the Live Check page: when opened, the browser fetches
current Intents volume, fees and NEAR price from DefiLlama's public API and
re-tests falsifier F1 (and recomputes V*) live. Falsifiers that cannot be
re-tested from a browser (F2, F3, F4, F5, F6) keep their snapshot status,
read from data/model_outputs.json and data/falsifiers.json at load.

This script writes the page from scripts/live_check_template.html, injecting
the current snapshot constants (the SNAP line) from the two JSON files so the
embedded fallback is always as fresh as the last rebuild. It never restores
the old generated dashboard: that layout was retired on 2026-11-13 because it
duplicated the thesis with different numbers.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TEMPLATE = Path(__file__).resolve().parent / "live_check_template.html"
OUT = ROOT / "dashboard" / "index-generated.html"

SNAP_RE = re.compile(r"var SNAP = \{[^}]*\};")
# Thesis-measured 60-day gross take (bps). A model input, not a live reading:
# the checker measures the *net* take for F2; the gross take is only shown
# here as context on the Live Check page.
TAKE_GROSS_60_BPS = 16.4


def read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def snap_line(model: dict | None, falsifiers: dict | None) -> str:
    """Build the SNAP fallback line from the current JSON files."""
    f1_reading = 125805115
    f1_win = "2026-10-14..2026-11-12"
    f2_snap = "net take 5.24 bps, capture 32.2%, 60 days 2026-09-14..2026-11-12"
    check_date = "13 Nov 2026"
    price = 3.5118584696509734
    capture_txt = "32.6%"
    triggered = 0

    if model:
        inp = model.get("inputs") or {}
        if isinstance(inp.get("near_price_usd"), (int, float)):
            price = inp["near_price_usd"]
        if isinstance(inp.get("fee_capture_rate"), (int, float)):
            capture_txt = f"{inp['fee_capture_rate'] * 100:.1f}%"

    if falsifiers:
        by_id = {f.get("id"): f for f in falsifiers.get("falsifiers") or []}
        f1 = by_id.get("F1") or {}
        if isinstance(f1.get("reading"), (int, float)):
            f1_reading = int(f1["reading"])
        rt = f1.get("reading_text") or ""
        if " over " in rt:
            f1_win = rt.split(" over ", 1)[1]
        f2 = by_id.get("F2") or {}
        r2 = f2.get("reading") or {}
        if isinstance(r2.get("take_bps"), (int, float)) and isinstance(
            r2.get("capture_pct"), (int, float)
        ):
            win2 = ""
            rt2 = f2.get("reading_text") or ""
            if " over " in rt2:
                win2 = " " + rt2.split(" over ", 1)[1]
            f2_snap = (
                f"net take {r2['take_bps']:.2f} bps, "
                f"capture {r2['capture_pct']:.1f}%, 60 days{win2}"
            )
        triggered = sum(
            1 for f in falsifiers.get("falsifiers") or [] if f.get("status") == "triggered"
        )
        gen = falsifiers.get("generated_at_utc") or ""
        try:
            dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
            check_date = dt.strftime("%d %b %Y")
        except ValueError:
            pass

    return (
        f'var SNAP = {{ f1: {f1_reading}, price: {price!r}, '
        f"takeGross60: {TAKE_GROSS_60_BPS}, f1win: {f1_win!r}, "
        f"captureTxt: {capture_txt!r}, f2snap: {f2_snap!r}, "
        f'summary: "{triggered} of 6 triggered", checkDate: {check_date!r} }};'
    )


def build() -> None:
    model = read_json(DATA / "model_outputs.json")
    falsifiers = read_json(DATA / "falsifiers.json")
    html = TEMPLATE.read_text()
    new_snap, n = SNAP_RE.subn(snap_line(model, falsifiers), html, count=1)
    if n != 1:
        raise SystemExit("live_check_template.html: SNAP line not found")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(new_snap)
    print(f"dashboard: wrote {OUT} ({len(new_snap):,} bytes)")


if __name__ == "__main__":
    build()
