#!/usr/bin/env python3
"""Replay the full history and derive data/signal.json for every strategy.

This regenerates the ENTIRE derived history on every run — it never appends.
Change a threshold in params.py and the whole timeline reflows under the new
logic, so the chart can never show a past painted by a rule we no longer use.
See docs/adr/0001-regenerate-derived-data.md.

Two strategies are emitted side by side under `strategies` (ADR 0004). They
answer the same question and deliberately do not share a window: Tripod needs
VIX and so starts in 1990, Vol Target needs only NDX and starts in 1986.

Usage:
    python scripts/signal.py           # write data/signal.json
    python scripts/signal.py --stats   # also print validation stats to stdout
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
from collections import Counter

import voltarget
from params import GEARS, PARAMS, SERIES_TRADING_DAYS, STRATEGIES, orders_for

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")


def read_csv(name: str) -> dict[str, float]:
    path = os.path.join(DATA, f"{name}.csv")
    out: dict[str, float] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                out[row["date"]] = float(row["close"])
            except (TypeError, ValueError):
                continue
    return out


def align() -> tuple[list[str], list[float], list[float], int]:
    """Align VIX onto the NDX trading calendar.

    NDX defines the sessions because NDX is what we actually trade. A missing
    VIX print is forward-filled rather than dropped: dropping the session would
    silently shift every moving average by one day.
    """
    ndx = read_csv("ndx")
    vix = read_csv("vix")
    start = max(min(ndx), min(vix))
    # Never judge past the last settled VIX close. fetch.py already truncates,
    # but a stale checkout or a hand-edited CSV must not be able to produce a
    # signal from a forward-filled VIX on the most recent session — that is
    # exactly the reading someone would act on.
    end = min(max(ndx), max(vix))
    dates = sorted(d for d in ndx if start <= d <= end)

    closes: list[float] = []
    vixes: list[float] = []
    filled = 0
    last_vix: float | None = None
    for day in dates:
        if day in vix:
            last_vix = vix[day]
        elif last_vix is not None:
            filled += 1
        if last_vix is None:
            continue
        closes.append(ndx[day])
        vixes.append(last_vix)

    dates = dates[len(dates) - len(closes):]
    return dates, closes, vixes, filled


def sma(values: list[float], n: int, i: int) -> float | None:
    if i + 1 < n:
        return None
    return sum(values[i + 1 - n:i + 1]) / n


def classify_regime(close: float, ma: float, previous: str | None) -> str | None:
    if close > ma * (1 + PARAMS["up_band"]):
        return "up"
    if close < ma * (1 - PARAMS["down_band"]):
        return "down"
    return previous  # neutral band: carry the previous regime forward


def pick_gear(regime: str, vix10: float, dd: float) -> str:
    if regime == "up":
        if vix10 < PARAMS["vix_hot"] and dd >= PARAMS["dd_trigger"]:
            return "G3"
        return "G15_UP"
    return "G15_DOWN" if vix10 < PARAMS["vix_panic"] else "CASH"


def build() -> dict:
    dates, closes, vixes, filled = align()
    n = len(dates)
    ma_n, vix_n, dd_n = PARAMS["ma_length"], PARAMS["vix_ma_length"], PARAMS["dd_lookback"]

    rows = []
    regime: str | None = None
    gear: str | None = None
    events: list[dict] = []

    for i in range(n):
        ma = sma(closes, ma_n, i)
        v10 = sma(vixes, vix_n, i)
        if i + 1 < dd_n:
            dd = None
        else:
            peak = max(closes[i + 1 - dd_n:i + 1])
            dd = closes[i] / peak - 1.0

        regime = classify_regime(closes[i], ma, regime) if ma is not None else None

        new_gear = gear
        if regime is not None and v10 is not None and dd is not None:
            new_gear = pick_gear(regime, v10, dd)
            if new_gear != gear:
                events.append({
                    "date": dates[i],                                  # judged on this close
                    "exec_date": dates[i + 1] if i + 1 < n else None,   # traded on the next session
                    "from": gear,
                    "to": new_gear,
                    **orders_for(gear, new_gear),
                })
            gear = new_gear

        rows.append({
            "d": dates[i],
            "c": round(closes[i], 2),
            "ma": round(ma, 2) if ma is not None else None,
            "v": round(v10, 2) if v10 is not None else None,
            "dd": round(dd, 5) if dd is not None else None,
            "r": regime,
            "g": gear,
        })

    return {
        "rows": rows,
        "events": events,
        "vix_filled_sessions": filled,
        "dates": dates,
    }


def summarize(built: dict) -> dict:
    rows, events = built["rows"], built["events"]
    live = [r for r in rows if r["g"] is not None]
    if not live:
        raise SystemExit("FATAL: not enough history to produce a single signal")

    first, last = live[0], live[-1]
    span_years = (dt.date.fromisoformat(last["d"]) - dt.date.fromisoformat(first["d"])).days / 365.25

    real = [e for e in events if e["from"] is not None]
    trades = [e for e in real if e["trade"]]
    regime_only = [e for e in real if not e["trade"]]
    downshifts = [e for e in real
                  if GEARS[e["to"]]["leverage"] < GEARS[e["from"]]["leverage"]]

    # A gear change is not one order. Going TQQQ 100% -> QQQ 50%/QLD 50% is a
    # sell plus two buys. Counting orders is what makes our number comparable
    # to the source video's "8.1 trades per year".
    orders = sum(len(e["sell"]) + len(e["buy"]) for e in real)

    by_year: Counter[str] = Counter(e["date"][:4] for e in trades)
    years = {r["d"][:4] for r in live}
    zero_trade_years = sorted(y for y in years if by_year[y] == 0)

    gaps = []
    marks = [first["d"]] + [e["date"] for e in trades]
    for a, b in zip(marks, marks[1:]):
        gaps.append((dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days)
    gaps.append((dt.date.fromisoformat(last["d"]) - dt.date.fromisoformat(marks[-1])).days)

    # Time spent in each gear, as a share of live sessions.
    occupancy = Counter(r["g"] for r in live)

    return {
        "span_start": first["d"],
        "span_end": last["d"],
        "span_years": round(span_years, 1),
        "sessions": len(live),
        "gear_changes": len(real),
        "trade_events": len(trades),
        "regime_only_changes": len(regime_only),
        "downshifts": len(downshifts),
        "orders_total": orders,
        "orders_per_year": round(orders / span_years, 1),
        "changes_per_year": round(len(trades) / span_years, 2),
        "zero_trade_years": zero_trade_years,
        "longest_no_change_days": max(gaps),
        "median_gap_days": sorted(gaps)[len(gaps) // 2],
        "occupancy_pct": {k: round(100 * v / len(live), 1) for k, v in occupancy.items()},
        "vix_filled_sessions": built["vix_filled_sessions"],
    }


def latest_block(built: dict) -> dict:
    rows = built["rows"]
    live = [r for r in rows if r["g"] is not None]
    cur, prev = live[-1], live[-2]
    real = [e for e in built["events"] if e["from"] is not None]
    trades = [e for e in real if e["trade"]]
    last_change = trades[-1] if trades else None

    today = dt.date.fromisoformat(cur["d"])
    since_days = None
    sessions_since = None
    if last_change:
        since_days = (today - dt.date.fromisoformat(last_change["date"])).days
        idx = next(i for i, r in enumerate(live) if r["d"] == last_change["date"])
        sessions_since = len(live) - 1 - idx

    ma, close, v10, dd = cur["ma"], cur["c"], cur["v"], cur["dd"]
    up_line = ma * (1 + PARAMS["up_band"])
    down_line = ma * (1 - PARAMS["down_band"])
    gear = GEARS[cur["g"]]

    return {
        "date": cur["d"],
        "close": close,
        "regime": cur["r"],
        "gear": cur["g"],
        "gear_ko": gear["ko"],
        "label": gear["label"],
        "weights": gear["weights"],
        "leverage": gear["leverage"],
        "color": gear["color"],
        "changed": cur["g"] != prev["g"],
        "prev_gear": prev["g"],
        # True only when the target book actually differs. A G15_UP <-> G15_DOWN
        # move changes the gear key but holds the same QQQ/QLD book, so there is
        # nothing to place.
        "action_required": orders_for(prev["g"], cur["g"])["trade"],
        "regime_only_change": cur["g"] != prev["g"] and not orders_for(prev["g"], cur["g"])["trade"],
        "orders": orders_for(prev["g"], cur["g"]),
        "last_change": last_change,
        "days_since_change": since_days,
        "sessions_since_change": sessions_since,
        "legs": {
            "ma": {
                "value": ma,
                "up_line": round(up_line, 2),
                "down_line": round(down_line, 2),
                "dist_pct": round(100 * (close / ma - 1), 2),
                # Percent move in the index required to flip the regime.
                "to_up_pct": round(100 * (up_line / close - 1), 2),
                "to_down_pct": round(100 * (down_line / close - 1), 2),
            },
            "vix": {
                "value": v10,
                "hot": PARAMS["vix_hot"],
                "panic": PARAMS["vix_panic"],
                "to_hot": round(PARAMS["vix_hot"] - v10, 2),
                "to_panic": round(PARAMS["vix_panic"] - v10, 2),
            },
            "dd": {
                "value": round(100 * dd, 2),
                "trigger": round(100 * PARAMS["dd_trigger"], 2),
                "to_trigger_pp": round(100 * (dd - PARAMS["dd_trigger"]), 2),
                "peak": round(close / (1 + dd), 2),
            },
        },
    }


def ndx_series() -> tuple[list[str], list[float]]:
    """The full NDX calendar, unbounded by VIX.

    Tripod has to stop at the last settled VIX close; Vol Target does not read
    VIX at all, so truncating it to the VIX window would throw away four years
    of history for no reason.
    """
    ndx = read_csv("ndx")
    dates = sorted(ndx)
    return dates, [ndx[d] for d in dates]


def main() -> None:
    built = build()
    stats = summarize(built)
    latest = latest_block(built)

    series = [r for r in built["rows"] if r["g"] is not None][-SERIES_TRADING_DAYS:]
    tripod = {
        "params": PARAMS,
        "gears": GEARS,
        "latest": latest,
        "stats": stats,
        "events": built["events"],
        "series": series,
    }

    vt_dates, vt_closes = ndx_series()
    vt = voltarget.payload(vt_dates, vt_closes)

    out = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "nav": STRATEGIES,
        "data_range": {
            "ndx_first": vt_dates[0],
            "last_session": vt_dates[-1],
            "tripod_last_session": built["dates"][-1],
        },
        "strategies": {"tripod": tripod, "voltarget": vt},
    }

    path = os.path.join(DATA, "signal.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"signal.json written: {os.path.getsize(path) / 1024:.0f} KB")

    # Same payload wrapped as a script assignment. A <script src> is not subject
    # to CORS, so this is what makes index.html work when it is opened by
    # double-clicking the file (file:// origin), where fetch() is blocked.
    # signal.json stays the canonical artifact for any other consumer.
    js_path = os.path.join(DATA, "signal.js")
    with open(js_path, "w", encoding="utf-8") as fh:
        fh.write("window.__SIGNAL__=")
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write(";\n")
    print(f"signal.js  written: {os.path.getsize(js_path) / 1024:.0f} KB")
    print(f"  tripod    {latest['date']}  ->  {latest['gear']} ({latest['label']})"
          f"  action_required={latest['action_required']}")
    vl = vt["latest"]
    print(f"  voltarget {vl['date']}  ->  TQQQ {vl['weight_pct']}% / cash {vl['cash_pct']}%"
          f"  action_required={vl['action_required']}")

    if "--stats" in sys.argv:
        print("\n--- tripod: validation stats (compare against the source video) ---")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        print("\n--- voltarget: operating stats (no performance figures by design) ---")
        for key, value in vt["stats"].items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
