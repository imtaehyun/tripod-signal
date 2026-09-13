"""Rule parameters for the Tripod strategy.

Every number the rule depends on lives here. Nothing else in the codebase
hardcodes a threshold. See docs/adr/0002-unspecified-parameters.md for why the
values marked INFERRED were chosen — the source video did not specify them.
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
