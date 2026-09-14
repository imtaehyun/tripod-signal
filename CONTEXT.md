# Glossary

Canonical vocabulary for this project. Every term here maps to an identifier in
`scripts/params.py`, `data/signal.json`, or the UI. Implementation details do
not belong in this file — this is a glossary and nothing else.

---

## Tripod / 트라이팟

The strategy as a whole: **three independent readings** taken after each close,
each answering a different question. Named for a camera tripod — remove one leg
and it falls over. Never call the strategy "the model" or "the algorithm"; those
imply a fitted thing, and the whole point is that it was not fitted.

The three legs, and the *only* correct names for them:

| Leg | Term | Question it answers |
|---|---|---|
| 1 | **Trend** / 방향 | Is the trend alive? (index vs its 250-day MA) |
| 2 | **Fear** / 공포 | How frightened is the market? (VIX 10-day average) |
| 3 | **Fatigue** / 피로도 | How far from the recent peak? (52-week drawdown) |

## Regime / 레짐

The market state derived from **leg 1 only**: `up`, `down`, or carried forward.
A regime is *not* a position — it selects which half of the Gear table applies.

Distinct from **Gear**. If you find yourself writing "the regime is 3x", you
mean Gear.

## Neutral band / 중립 구간

The zone between the up line (MA +1%) and the down line (MA −5%) where **no new
regime is declared and the previous one is carried forward**. This is
hysteresis, and it is the reason Regime cannot be computed from a single day's
data — the history has to be replayed. Do not describe it as a "third regime";
there are two regimes and a carry rule.

The band is deliberately asymmetric: *exit carefully, enter quickly.*

## Gear / 기어

The target portfolio. Exactly four exist, and they are always referred to by
their stable keys, never by their leverage alone (two gears share 1.5x):

| Key | Target | Leverage | Regime |
|---|---|---|---|
| `G3` | TQQQ 100% | 3.0x | up |
| `G15_UP` | QQQ 50% + QLD 50% | 1.5x | up |
| `G15_DOWN` | QQQ 50% + QLD 50% | 1.5x | down |
| `CASH` | 100% cash | 0x | down |

**Downshift** / 감속 = moving to lower leverage. **Upshift** / 증속 = higher.
A `G15_UP → G15_DOWN` move is **lateral**, not a downshift: same leverage,
different regime — and critically, **zero orders**, because both hold an
identical QQQ 50 / QLD 50 book. `orders_for()` is the single source of truth for
this; never infer "a trade happened" from the gear key alone.

## Gear change vs trade vs order

Three different counts, and conflating any two of them produces a wrong number
or a wrong instruction:

- **Gear change** — the gear key differs from yesterday's. 288 in 35 years.
- **Trade** (`trade: true`) — the target *book* differs, so orders exist. 283.
  The 5-event gap is the lateral `G15_UP ↔ G15_DOWN` case.
- **Order** — one buy or sell ticket. 809; a trade needs one to three.

`action_required` is **trade-based**, never gear-change-based. A regime-only
change must not raise a rebalance alert, or it sends someone hunting for an
order that does not exist.

## Judgement date vs execution date / 판정일 vs 체결일

The rule reads the **close** of day D (the *judgement date*) and trades on day
D+1 (the *execution date*). Never collapse these. Assuming same-close execution
inflated the source author's own backtest from 24.7% to 44.3% CAGR.

## Insurance premium / 보험료

The source author's term for a downshift that, in hindsight, cost money because
the market recovered immediately. These are the *expected majority* of
downshifts, not errors. Any wording that treats a losing downshift as a bug
misstates the design.

## Leg values

- **`dist_pct`** — index close relative to its 250-day MA, in percent.
- **`vix10`** — 10-day simple average of the VIX close. Never the daily VIX.
- **`dd52`** — close divided by the highest *close* of the trailing 252
  sessions, minus one. Always negative or zero. This is a **52-week drawdown**,
  *not* max drawdown; do not label it MDD even though the source video does.

## MDD

Reserved for **maximum drawdown over a full backtest** — a performance metric.
This project does not compute it (no synthetic ETF returns are modelled). If you
see MDD in this codebase, it is a mistake; you probably mean `dd52`.

## Synthetic ETF / 합성 ETF

A simulated QLD/TQQQ price series derived from the index, used by the source
author to backtest before those funds existed. **This project deliberately does
not build one**, because the financing cost and expense ratio assumptions are
unknown and getting them wrong produces flattering, false returns.

## Session / 거래일

One NDX trading day. NDX defines the calendar because NDX is what is traded; a
missing VIX print is forward-filled rather than dropping the session, which
would silently shift every moving average.
