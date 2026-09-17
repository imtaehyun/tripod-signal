#!/usr/bin/env python3
"""Live intraday quote, for deciding at 15:45 ET instead of after the close.

Why this exists
---------------
Judging on the settled close and filling the next session costs this strategy
roughly 8pp of max drawdown per unit of average leverage, and ~0.13 of MAR --
an order of magnitude more than any signal refinement measured in the backtest
lab. Deciding at 15:45 ET and sending the order into the same close recovers it.

The obvious worry is that a 15:45 price is not the close, so the signal is
computed on the wrong number. That was measured (tqqq-trend-lab/intraday_proxy.py)
and it costs nothing: over 20 trials of injecting the residual 15:45->16:00 move
(estimated sigma 0.44%) into the signal while settling P&L on the real closes,
CAGR went 16.68% -> 16.57% [16.01, 17.19] -- the baseline sits inside the spread.
The reason is the +-1% latch band on each moving average: it absorbs a 0.44%
price wobble by design. The device added to stop whipsaw pays for itself twice.

ADR 0005 covers the whole change.

Contract with the rest of the codebase
-------------------------------------
A provisional bar NEVER enters data/*.csv. `fetch.py` stays append-only over
settled closes; this module returns a value that lives only in the current run's
signal.json, tagged `provisional: true`. That keeps ADR 0001 (regenerate derived
data, never trust a provider's revision of history) intact.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import urllib.parse
from zoneinfo import ZoneInfo

from fetch import _get

ET = ZoneInfo("America/New_York")

# The intended decision moment. The exchange MOC cutoff is 15:50 ET and the
# order has to be in before it, so the quote is taken at 15:45 and the
# notification has ~5 minutes to land.
DECIDE_AT = dt.time(15, 45)
# Past this, the session is effectively over: the quote returned is the close or
# near enough, and the order cannot make the auction. Still emit a signal, but
# flag it so the message says "next session" rather than "place now".
TOO_LATE = dt.time(15, 58)


def now_et() -> dt.datetime:
    return dt.datetime.now(ET)


def session_state(at: dt.datetime | None = None) -> str:
    """`early` | `window` | `late` | `closed` — where we are relative to 15:45 ET."""
    at = at or now_et()
    if at.weekday() >= 5:
        return "closed"
    t = at.time()
    if t < DECIDE_AT:
        return "early"
    if t < TOO_LATE:
        return "window"
    if t < dt.time(16, 30):
        return "late"
    return "closed"


def live(symbol: str) -> dict:
    """Last regular-session price for `symbol`.

    Uses the chart endpoint's `meta` block rather than parsing 1-minute bars:
    `regularMarketPrice` is the same number the exchange is printing, and it does
    not depend on the last minute bar having been flushed yet.
    """
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?interval=1m&range=1d&includePrePost=false"
    )
    meta = json.loads(_get(url))["chart"]["result"][0]["meta"]
    price = meta.get("regularMarketPrice")
    stamp = meta.get("regularMarketTime")
    if price is None or stamp is None:
        raise RuntimeError(f"{symbol}: no regularMarketPrice in Yahoo meta")
    when = dt.datetime.fromtimestamp(int(stamp), dt.timezone.utc).astimezone(ET)
    state = str(meta.get("marketState", "")).upper()
    return {
        "symbol": symbol,
        "price": round(float(price), 6),
        "as_of_et": when.isoformat(timespec="seconds"),
        "session": when.date().isoformat(),
        "market_state": state,
    }


def wait_for_window(margin_seconds: int = 0) -> str:
    """Sleep until 15:45 ET if the job started early, then report the state.

    GitHub Actions cron fires late under load -- routinely by several minutes,
    occasionally by much more. So the workflow schedules the job EARLY and this
    function absorbs the jitter, instead of the schedule trying to hit a
    5-minute window it does not control. Blocking is free on a public repo.
    """
    import time

    state = session_state()
    if state != "early":
        return state
    target = now_et().replace(hour=DECIDE_AT.hour, minute=DECIDE_AT.minute,
                             second=margin_seconds, microsecond=0)
    delay = (target - now_et()).total_seconds()
    if delay > 0:
        print(f"quote: sleeping {delay:.0f}s until {target.time()} ET")
        time.sleep(delay)
    return session_state()


def provisional(symbols: tuple[str, ...] = ("^NDX", "^VIX")) -> dict:
    """Quote every symbol and describe when it was taken."""
    state = session_state()
    quotes = {}
    errors = {}
    for sym in symbols:
        try:
            quotes[sym] = live(sym)
        except Exception as exc:  # noqa: BLE001 - a missing quote must not kill the run
            errors[sym] = str(exc)
    # A market holiday looks exactly like a normal weekday to the clock: the
    # state is "window", the fetch succeeds, and the price returned is LAST
    # session's close. Acting on it would silently re-decide yesterday and could
    # fire a duplicate order. So the quote is only usable if the exchange stamped
    # it TODAY.
    today = now_et().date().isoformat()
    ndx = quotes.get("^NDX")
    fresh = bool(ndx) and ndx["session"] == today
    if ndx and not fresh:
        errors["^NDX"] = (f"stale quote: stamped {ndx['session']}, today is {today}"
                          " (market holiday?)")
    return {
        "state": state,
        "taken_at_et": now_et().isoformat(timespec="seconds"),
        "decide_at_et": DECIDE_AT.isoformat(),
        "fresh": fresh,
        "usable": state in ("window", "late") and fresh,
        "same_session_fill": state == "window" and fresh,
        "quotes": quotes,
        "errors": errors,
    }


if __name__ == "__main__":
    if "--wait" in sys.argv:
        print(f"state after wait: {wait_for_window()}")
    print(json.dumps(provisional(), indent=2, ensure_ascii=False))
