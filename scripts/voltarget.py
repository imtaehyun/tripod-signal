#!/usr/bin/env python3
"""Replay the full history for the Vol Target strategy.

Like the Tripod side, this regenerates everything on every run and never
appends — the deadband makes the weight path-dependent, so a single day's data
is not enough to know today's target. See ADR 0001.

Unlike Tripod this needs NDX only, no VIX, so its usable history starts ~250
sessions after the NDX series does (1986) rather than being bounded by CBOE's
1990 VIX file.

The rule, in full:

    leg_n  = latched: on above SMA_n*1.01, off below SMA_n*0.99, else carried
    vote   = share of the {50,100,200,250}-day legs that are on   (0 .. 1)
    rvol   = mean of the 20d and 60d annualised stdev of daily returns
    raw    = vote * target_vol / (3 * rvol),  clamped to [0, max_weight]
    target = raw snapped to a 5pp grid
    weight = target, but only if it has drifted >= 10pp from what is held

`weight` is the fraction of the account in TQQQ. The remainder is held in
SGOV rather than as uninvested cash -- worth 1.99pp of CAGR, see params.py.

Two of these steps are path-dependent — the latched legs and the deadband — so
today's weight is not a function of today's prices alone. That is why this
replays from the beginning rather than appending.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from params import CASH_TICKER, SERIES_TRADING_DAYS, VOLTARGET as VT, band_for

ANNUALISATION = 252


def _prefix_sums(values: list[float]) -> list[float]:
    out = [0.0] * (len(values) + 1)
    for i, v in enumerate(values):
        out[i + 1] = out[i] + v
    return out


def _stdev(values: list[float], mean: float) -> float:
    """Sample standard deviation (ddof=1), matching pandas' default."""
    n = len(values)
    if n < 2:
        return 0.0
    return (sum((v - mean) ** 2 for v in values) / (n - 1)) ** 0.5


def build(dates: list[str], closes: list[float]) -> dict:
    n = len(closes)
    lengths = list(VT["ma_lengths"])
    windows = list(VT["vol_windows"])
    step, band = VT["weight_step"], VT["rebalance_band"]

    csum = _prefix_sums(closes)
    # Simple (not log) daily returns, to match how the backtest lab measures vol.
    rets = [0.0] + [closes[i] / closes[i - 1] - 1.0 for i in range(1, n)]
    rsum = _prefix_sums(rets)

    # First session where every SMA and every vol window is fully populated.
    first = max(max(lengths) - 1, max(windows))

    rows: list[dict] = []
    events: list[dict] = []
    held: float | None = None
    # One latched on/off state per MA length. Seeded on the first live session
    # from a plain comparison, then it only moves when a band is breached.
    legs: dict[int, bool] = {}
    band_pct = VT["ma_band"]

    for i in range(n):
        if i < first:
            rows.append({"d": dates[i], "c": round(closes[i], 2), "w": None,
                         "vote": None, "rv": None, "raw": None})
            continue

        mas = {L: (csum[i + 1] - csum[i + 1 - L]) / L for L in lengths}
        for L in lengths:
            if L not in legs:
                legs[L] = closes[i] > mas[L]
            elif closes[i] > mas[L] * (1 + band_pct):
                legs[L] = True
            elif closes[i] < mas[L] * (1 - band_pct):
                legs[L] = False
            # inside the band: carry the previous state forward
        above = sum(1 for L in lengths if legs[L])
        vote = above / len(lengths)

        vols = []
        for w in windows:
            seg = rets[i + 1 - w:i + 1]
            mean = (rsum[i + 1] - rsum[i + 1 - w]) / w
            vols.append(_stdev(seg, mean) * (ANNUALISATION ** 0.5))
        rvol = sum(vols) / len(vols)

        denom = max(rvol, VT["vol_floor"]) * VT["etf_leverage"]
        raw = min(VT["max_weight"], max(0.0, vote * VT["target_vol"] / denom))
        target = round(raw / step) * step

        if held is None or abs(target - held) >= band - 1e-12:
            new = target
        else:
            new = held

        if held is not None and abs(new - held) > 1e-12:
            events.append({
                "date": dates[i],                                 # judged on this close
                "exec_date": dates[i + 1] if i + 1 < n else None,  # traded next session
                "from": round(held, 4),
                "to": round(new, 4),
                "delta": round(new - held, 4),
                "trade": True,
            })
        elif held is None:
            events.append({
                "date": dates[i], "exec_date": dates[i + 1] if i + 1 < n else None,
                "from": None, "to": round(new, 4), "delta": round(new, 4), "trade": True,
            })

        held = new
        rows.append({
            "d": dates[i], "c": round(closes[i], 2), "w": round(held, 4),
            "vote": round(vote, 3), "rv": round(rvol, 4), "raw": round(raw, 4),
            "ma": {str(L): round(mas[L], 2) for L in lengths},
            "legs": {str(L): bool(legs[L]) for L in lengths},
        })

    return {"rows": rows, "events": events, "dates": dates}


def summarize(built: dict) -> dict:
    rows = built["rows"]
    live = [r for r in rows if r["w"] is not None]
    if not live:
        raise SystemExit("FATAL: not enough history for a Vol Target signal")

    first, last = live[0], live[-1]
    span_years = (dt.date.fromisoformat(last["d"]) - dt.date.fromisoformat(first["d"])).days / 365.25
    real = [e for e in built["events"] if e["from"] is not None]

    gaps = []
    marks = [first["d"]] + [e["date"] for e in real]
    for a, b in zip(marks, marks[1:]):
        gaps.append((dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days)
    gaps.append((dt.date.fromisoformat(last["d"]) - dt.date.fromisoformat(marks[-1])).days)

    by_year: Counter[str] = Counter(e["date"][:4] for e in real)
    years = {r["d"][:4] for r in live}

    # Time spent in each colour band, so the legend can say how normal today is.
    occupancy: Counter[str] = Counter(band_for(r["w"])["ko"] for r in live)
    fully_out = sum(1 for r in live if r["w"] <= 1e-9)

    return {
        "span_start": first["d"],
        "span_end": last["d"],
        "span_years": round(span_years, 1),
        "sessions": len(live),
        "trade_events": len(real),
        "changes_per_year": round(len(real) / span_years, 2),
        "zero_trade_years": sorted(y for y in years if by_year[y] == 0),
        "longest_no_change_days": max(gaps),
        "median_gap_days": sorted(gaps)[len(gaps) // 2],
        "avg_weight_pct": round(100 * sum(r["w"] for r in live) / len(live), 1),
        "avg_leverage": round(VT["etf_leverage"] * sum(r["w"] for r in live) / len(live), 2),
        "fully_cash_pct": round(100 * fully_out / len(live), 1),
        "occupancy_pct": {k: round(100 * v / len(live), 1) for k, v in occupancy.items()},
    }


def latest_block(built: dict) -> dict:
    rows = built["rows"]
    live = [r for r in rows if r["w"] is not None]
    cur, prev = live[-1], live[-2]
    real = [e for e in built["events"] if e["from"] is not None]
    last_change = real[-1] if real else None

    today = dt.date.fromisoformat(cur["d"])
    since_days = sessions_since = None
    if last_change:
        since_days = (today - dt.date.fromisoformat(last_change["date"])).days
        idx = next(i for i, r in enumerate(live) if r["d"] == last_change["date"])
        sessions_since = len(live) - 1 - idx

    delta = cur["w"] - prev["w"]
    band = band_for(cur["w"])
    lengths = list(VT["ma_lengths"])

    # What the raw target would have to reach for the deadband to release. Shown
    # so a flat day is legibly "nothing to do" rather than "nothing happened".
    step = VT["weight_step"]
    release_up = cur["w"] + VT["rebalance_band"]
    release_down = cur["w"] - VT["rebalance_band"]

    return {
        "date": cur["d"],
        "close": cur["c"],
        "weight": cur["w"],
        "weight_pct": round(100 * cur["w"], 1),
        "cash_pct": round(100 * (1 - cur["w"]), 1),
        "leverage": round(VT["etf_leverage"] * cur["w"], 2),
        "color": band["color"],
        "band_ko": band["ko"],
        "prev_weight": prev["w"],
        "changed": abs(delta) > 1e-12,
        "action_required": abs(delta) > 1e-12,
        "delta": round(delta, 4),
        "delta_pp": round(100 * delta, 1),
        "side": "buy" if delta > 0 else ("sell" if delta < 0 else None),
        "last_change": last_change,
        "days_since_change": since_days,
        "sessions_since_change": sessions_since,
        "inputs": {
            "vote": cur["vote"],
            "above": int(round(cur["vote"] * len(lengths))),
            "of": len(lengths),
            "mas": cur.get("ma", {}),
            # `legs` is the latched state that actually drives the vote;
            # `ma_above` is the raw comparison. They differ inside the band, and
            # showing only the raw one would make the vote look wrong.
            "legs": cur.get("legs", {}),
            "ma_above": {str(L): bool(cur["c"] > cur["ma"][str(L)]) for L in lengths},
            "ma_dist_pct": {str(L): round(100 * (cur["c"] / cur["ma"][str(L)] - 1), 2)
                            for L in lengths},
            "ma_band_pct": round(100 * VT["ma_band"], 1),
            "rvol": cur["rv"],
            "rvol_pct": round(100 * cur["rv"], 1),
            "raw": cur["raw"],
            "raw_pct": round(100 * cur["raw"], 1),
            "target_vol_pct": round(100 * VT["target_vol"], 0),
            "held_pct": round(100 * cur["w"], 1),
            "release_up_pct": round(100 * min(1.0, release_up), 1),
            "release_down_pct": round(100 * max(0.0, release_down), 1),
            "step_pp": round(100 * step, 0),
            "band_pp": round(100 * VT["rebalance_band"], 0),
        },
    }


def payload(dates: list[str], closes: list[float],
            provisional: tuple[str, float] | None = None) -> dict:
    """Full payload. `provisional` appends one unsettled bar for today's decision.

    The appended bar is a live 15:45 ET quote, not a close. It is safe to append
    because `build` is a pure replay of committed history plus this one value --
    nothing here is ever written back to data/*.csv, so ADR 0001 holds. Only the
    LAST row can be affected, and it is tagged so the dashboard and the
    notification can say which price the decision used.

    History stays exact: yesterday and earlier are settled closes. Only today is
    a proxy, which is precisely the situation measured in
    tqqq-trend-lab/intraday_proxy.py, where it cost nothing.
    """
    if provisional is not None:
        day, price = provisional
        dates, closes = list(dates), list(closes)
        if dates and dates[-1] == day:
            closes[-1] = price      # provider already stubbed today; overwrite it
        else:
            dates.append(day)
            closes.append(price)

    built = build(dates, closes)
    live = [r for r in built["rows"] if r["w"] is not None]
    latest = latest_block(built)
    latest["provisional"] = provisional is not None
    if live:
        live[-1] = dict(live[-1], provisional=provisional is not None)
    return {
        "params": VT,
        "cash_ticker": CASH_TICKER,
        "latest": latest,
        "stats": summarize(built),
        "events": built["events"],
        "series": live[-SERIES_TRADING_DAYS:],
    }
