# 0005 — Decide at 15:45 ET, not after the close

Status: accepted · 2026-09-17

## Context

Every number this dashboard has ever shown assumed the rule is judged on the
settled close and filled the **next** session, because the dashboard could only
run after the close. That is not a free choice. Measured on ^NDX 1985–2026 in
`tqqq-trend-lab/timing.py`, the one-day delay costs:

| target_vol | avg leverage | ΔCAGR | ΔMDD | ΔMDD ÷ leverage |
|---|---|---|---|---|
| 20% | 0.84 | −1.1pp | −5.2pp | −6.2pp |
| 35% | 1.45 | −1.4pp | −11.7pp | **−8.0pp** |
| 50% | 1.84 | −2.4pp | −15.1pp | **−8.2pp** |
| 65% | 2.07 | −2.3pp | −17.0pp | **−8.2pp** |

The last column is roughly **constant**: a one-day-stale target is wrong in
proportion to how much you are holding. ΔMAR is likewise flat at about −0.13.

For scale, sixteen attempts to improve the *signal* — eleven VIX/term-structure/
MA overlays plus five of my own (faster vol estimator, 52-week drawdown leg, a
cost-minimal QQQ+TQQQ ladder, an asymmetric rebalance policy, NDX+SPX blending) —
all failed at matched average leverage. The fill timing is an order of magnitude
larger than anything available in the rule itself.

## Decision

Take a live quote at **15:45 ET** and decide on it, so the order can be sent
into the same closing auction. Keep the after-close run as the record.

### Why a 15:45 price is safe to compute the signal on

It is not the close, so the signal is computed on the wrong number. That was
measured directly (`tqqq-trend-lab/intraday_proxy.py`): inject the residual
15:45→16:00 move (estimated σ = 0.44%, from the daily σ scaled by √(15/390) and
multiplied by 1.4 for closing-auction volume) into the **signal only**, and
settle P&L on the real closes.

| | CAGR | MDD | MAR | avg leverage |
|---|---|---|---|---|
| signal on the close (baseline) | 16.68% | −51.9% | 0.32 | 1.44 |
| signal on a 15:45 proxy, 20 trials | 16.57% [16.01, 17.19] | −49.7% | 0.33 | 1.42 |

**The baseline sits inside the spread — it costs nothing.** The reason is the
±1% latch band on each moving average (ADR 0004): it absorbs a 0.44% wobble by
construction. The device added to stop whipsaw pays for itself a second time.
Positions differed from baseline on 24.8% of days by an average of 2.13pp —
mostly one grid step.

Two error sources have to be kept apart. The execution-price error is **zero-mean
noise** and does not accumulate. The fill delay is a **bias** — you eat a whole
day of adverse movement in a crash. Only the second one is expensive.

### Modelling trap avoided

The first version of that experiment perturbed the *entire* price series. That
inflates measured realised volatility (it is a sum of squares), which lowers
exposure — average leverage fell 1.45 → 1.34 — and the drawdown "improved" for
free. Only **today's** price is uncertain; every earlier close is known exactly.
The same confound is why `matched.py` exists in the lab.

## Consequences

- **`fetch.py` must never run in the intraday job.** It is append-only and an
  existing date keeps its stored value, so writing today's in-progress bar at
  15:45 would freeze a partial price into `ndx.csv` permanently. The intraday run
  reads committed history (settled through yesterday) and gets today from the
  live quote. ADR 0001 is unaffected: the provisional bar exists only in that
  run's `signal.json`, tagged `provisional: true`.
- **Cron is scheduled ~20 minutes early and the script sleeps to 15:45 ET.**
  Actions cron fires late under load; a five-minute window is not something the
  scheduler can be trusted to hit. Blocking is free on a public repo.
- **Two crons for DST.** Actions cron has no timezone, and unlike ADR 0003 there
  is no single UTC hour that is 15:45 ET in both halves of the year. Both fire;
  the one that is wrong lands outside the session and the guard skips it.
- **Holidays need an explicit check.** A market holiday looks identical to a
  normal weekday from the clock: right time, successful fetch, and a price that
  is *last* session's close. `quote.provisional()` therefore requires the
  exchange to have stamped the quote today.
- **Graceful degradation.** If the quote is unusable the run falls back to the
  settled close rather than failing. A late signal beats no signal; a stale
  signal presented as fresh is the only unacceptable outcome.
- The 15:50 MOC cutoff is now a hard operational deadline. Past 15:58 the signal
  is emitted but labelled for next-session execution.

## Rejected

**Next-day open fill.** The intermediate option, and it needs no workflow change
beyond ordering before the bell. Measured on 2005–2026 (Yahoo's `^NDX` opens are
backfilled with the prior close for 89.6% of 1985–94 and 40.5% of 1995–2004, so
earlier data is unusable): it recovers only **12–28%** of the delay penalty, and
the MAR gain of +0.011–0.013 is inside the ±0.07 noise floor. Not worth it.
