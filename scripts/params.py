"""Rule parameters for every strategy on the dashboard.

Every number any rule depends on lives here. Nothing else in the codebase
hardcodes a threshold. See docs/adr/0002-unspecified-parameters.md for why the
values marked INFERRED were chosen — the source video did not specify them, and
docs/adr/0004-second-strategy.md for why a second strategy lives here at all.
"""

PARAMS = {
    # --- Leg 1: trend (direction) ---
    "ma_length": 250,           # INFERRED: transcript mixes "250일선" and "251"
    "ma_kind": "sma",           # INFERRED: source unspecified; SMA is the paper's basic form
    "up_band": 0.01,            # close > ma * (1 + up_band)  => uptrend
    "down_band": 0.05,          # close < ma * (1 - down_band) => downtrend
    # between the two bands: carry the previous regime forward (hysteresis)

    # --- Leg 2: fear (VIX) ---
    "vix_ma_length": 10,        # 10-day average, NOT the daily value
    "vix_hot": 28.0,            # uptrend: >= this de-gears 3x -> 1.5x
    "vix_panic": 18.0,          # downtrend: >= this goes to 100% cash
    # NOTE: the author states 28 is NOT an optimum. It is his chosen risk size.

    # --- Leg 3: fatigue (52-week drawdown) ---
    "dd_lookback": 252,         # trading days ~= 52 weeks
    "dd_basis": "close",        # INFERRED: close-basis high, not intraday high
    "dd_trigger": -0.09,        # drawdown deeper than -9% de-gears 3x -> 1.5x

    # --- Execution ---
    "execution": "next_open",   # judge after the close, trade the NEXT session
}

# Gear definitions. Keys are stable identifiers used in signal.json and in the UI.
GEARS = {
    "G3": {
        "label": "TQQQ 100%",
        "leverage": 3.0,
        "regime": "up",
        "weights": {"TQQQ": 1.0},
        "color": "#dc2626",
        "ko": "상승 · 3배",
    },
    "G15_UP": {
        "label": "QQQ 50% + QLD 50%",
        "leverage": 1.5,
        "regime": "up",
        "weights": {"QQQ": 0.5, "QLD": 0.5},
        "color": "#f59e0b",
        "ko": "상승 · 1.5배 (감속)",
    },
    "G15_DOWN": {
        "label": "QQQ 50% + QLD 50%",
        "leverage": 1.5,
        "regime": "down",
        "weights": {"QQQ": 0.5, "QLD": 0.5},
        "color": "#0ea5e9",
        "ko": "하락 · 1.5배",
    },
    "CASH": {
        "label": "100% CASH",
        "leverage": 0.0,
        "regime": "down",
        "weights": {},
        "color": "#64748b",
        "ko": "하락 · 전량 현금",
    },
}

SERIES_TRADING_DAYS = 756  # ~3 years rendered on the page


# ─────────────────────────────────────────────────────────────────────────────
# Vol Target / 변동성 타겟
#
# A different answer to the same question Tripod answers. Tripod decides the
# leverage by reading three thresholds and picking one of four discrete gears.
# This one reads the trend as a *proportion* and then divides by how violently
# the index is currently moving, producing a continuous weight.
#
# The reason to divide by volatility: a 3x ETF's rebalancing decay is
# -(L^2-L)/2 * sigma^2, which for L=3 is -3*sigma^2. Measured on NDX since 1985,
# the top volatility quintile decays 16.7x faster than the bottom one. Holding a
# constant 3x through that is the single largest avoidable cost in a leveraged
# trend rule. Sizing inversely to volatility pins that term to a constant.
#
# `target_vol` is a RISK BUDGET, not an optimum — exactly like Tripod's VIX 28.
# It is the one knob here that is meant to be turned, and turning it moves
# drawdown roughly in proportion. Nothing else in this block should be tuned to
# improve a backtest number; see docs/adr/0004-second-strategy.md.
# ─────────────────────────────────────────────────────────────────────────────
VOLTARGET = {
    # --- trend, read as a proportion rather than a switch ---
    "ma_lengths": [50, 100, 200, 250],
    "ma_kind": "sma",

    # Each MA is a leg that latches on above MA*(1+band) and off below
    # MA*(1-band), carrying its state in between — the same hysteresis device
    # Tripod uses on its single MA, for the same reason.
    #
    # Without this the rule is unrunnable. Four legs and a ~1:1 vote-to-weight
    # multiplier mean one MA crossing moves the target ~25pp, which walks
    # straight through the 10pp deadband, so a price oscillating around the
    # 50-day MA produces 45pp round trips on consecutive days. Measured over
    # 1985-2026, latching cuts same-week reversals from 95 to 9 and trades from
    # 35.5/yr to 21.9/yr. It costs ~0.7pp of CAGR and slightly IMPROVES max
    # drawdown, so it is not a performance tweak — it buys operability.
    "ma_band": 0.01,

    # --- how violently the index is moving right now ---
    "vol_windows": [20, 60],    # annualised stdev of each, then averaged
    "vol_floor": 0.05,          # guard against divide-by-tiny; never binds in practice

    # --- the risk budget ---
    "target_vol": 0.50,         # annualised volatility the levered book aims at
    "etf_leverage": 3.0,        # TQQQ
    "max_weight": 1.0,          # never more than 100% of the account in TQQQ

    # --- turning a continuous number into something you can actually place ---
    "weight_step": 0.05,        # target is snapped to 5pp
    "rebalance_band": 0.10,     # ...and only acted on once it drifts 10pp away

    # --- execution ---
    "execution": "next_open",   # judge after the close, trade the NEXT session
}

# Colour ramp for the weight, used by the chart and the today card. Keys are the
# lower bound of each bucket in percent. Deliberately the same hues Tripod uses
# for comparable leverage so the two tabs read consistently: red = heaviest.
WEIGHT_BANDS = [
    {"from": 0,  "color": "#64748b", "ko": "현금"},
    {"from": 5,  "color": "#0ea5e9", "ko": "소액"},
    {"from": 25, "color": "#f59e0b", "ko": "중간"},
    {"from": 50, "color": "#dc2626", "ko": "적극"},
]


def band_for(weight: float) -> dict:
    """Which colour band a weight falls in. `weight` is a fraction, not percent."""
    pct = weight * 100
    chosen = WEIGHT_BANDS[0]
    for band in WEIGHT_BANDS:
        if pct >= band["from"]:
            chosen = band
    return chosen


# Tab order on the page. The key is also the URL hash, so these strings are a
# public interface — renaming one breaks any bookmark to that tab.
STRATEGIES = [
    {"key": "tripod",    "ko": "트라이팟",     "en": "Tripod"},
    {"key": "voltarget", "ko": "변동성 타겟",  "en": "Vol Target"},
]


def orders_for(from_gear: str | None, to_gear: str) -> dict:
    """Concrete orders to move between two gears.

    A gear change is not the same thing as a trade. G15_UP and G15_DOWN hold an
    identical QQQ 50 / QLD 50 book and differ only in which regime produced
    them, so moving between them requires ZERO orders. Telling someone to
    rebalance in that case sends them looking for a trade that does not exist.

    Returns sell/buy ticker lists and a `trade` flag that is False exactly when
    the target book is unchanged.
    """
    before = GEARS[from_gear]["weights"] if from_gear else {}
    after = GEARS[to_gear]["weights"]

    # Preserve each gear's declared ticker order rather than sorting, so the
    # rendered orders read in the same order as the gear label ("QQQ 50% + QLD
    # 50%") instead of alphabetically ("QLD ... QQQ ...").
    sell = [t for t in before if t not in after]
    buy = [t for t in after if t not in before]
    keep = [t for t in after if t in before]

    # Every gear holds its tickers at a fixed weight, so a ticker present in
    # both books never needs resizing. If that ever stops being true this
    # assertion fires rather than silently under-reporting a partial trim.
    for ticker in keep:
        assert before[ticker] == after[ticker], f"{ticker} needs resizing, not handled"

    return {
        "sell": sell,
        "buy": buy,
        "keep": keep,
        "trade": bool(sell or buy),
    }
