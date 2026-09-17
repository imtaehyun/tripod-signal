# Glossary

Canonical vocabulary for this project. Every term here maps to an identifier in
`scripts/params.py`, `data/signal.json`, or the UI. Implementation details do
not belong in this file — this is a glossary and nothing else.

The dashboard carries **two strategies** (ADR 0004). Terms below are grouped by
which one owns them; the shared section applies to both. A term owned by one
strategy must not be used to describe the other — saying "the gear" about Vol
Target or "the weight" about Tripod is always a mistake.

---

# Shared

## Strategy / 전략

One complete rule that turns NDX closes into a target portfolio. Exactly two
exist, keyed `tripod` and `voltarget`. The key is also the URL hash and the
`strategy:<key>` issue label, so it is a public interface — renaming one breaks
bookmarks and orphans open alerts.

## Judgement date vs execution date / 판정일 vs 체결일

Both strategies read the **close** of day D (the *judgement date*) and trade on
day D+1 (the *execution date*). Never collapse these. Assuming same-close
execution inflated Tripod's source author's own backtest from 24.7% to 44.3%
CAGR.

The newest judgement has no settled execution date yet. The UI renders that as
"다음 거래일", never as "—", which reads as *never*.

## Session / 거래일

One NDX trading day. NDX defines the calendar because NDX is what we actually
trade. For Tripod a missing VIX print is forward-filled rather than dropping the
session, which would silently shift every moving average.

## Hysteresis / 히스테리시스

A band around a threshold inside which **the previous state is carried forward**
instead of a new one being declared. Both strategies use it, and in both cases it
is what makes the rule runnable rather than what makes it profitable. Never
describe a carry band as a "third state" — there are two states and a carry rule.

## action_required

Whether *this* strategy wants an order placed on the next session. Always
order-based, never state-based: a change of internal state that leaves the target
book identical must not raise an alert, or it sends someone hunting for a trade
that does not exist. Each strategy computes its own; they are frequently
different, and the nav tab carries a dot for whichever is true.

## MDD

Reserved for **maximum drawdown over a full backtest** — a performance metric.
This project does not compute it for either strategy (no synthetic ETF returns
are modelled, ADR 0001 and 0004). If you see MDD in this codebase it is a
mistake; for Tripod you probably mean `dd52`.

## Synthetic ETF / 합성 ETF

A simulated QLD/TQQQ price series derived from the index. **This project
deliberately does not build one**, because the financing cost and expense ratio
assumptions are unknown here and getting them wrong produces flattering, false
returns. That modelling lives in a separate lab; see ADR 0004.

---

# Tripod / 트라이팟

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

---

# Vol Target / 변동성 타겟

The second strategy, keyed `voltarget`. Reads the trend as a **proportion** and
divides by how violently the index is currently moving, producing a continuous
weight rather than one of four discrete states. Never call it "the model" or
"Mallik's strategy" — only its trend signal is his; the sizing is not, and his
own rule has no sizing at all.

It holds exactly two things: **TQQQ and cash.** No QQQ, no QLD, no SQQQ.

## Leg / 다리

One of the four moving averages (50, 100, 200, 250-day SMA), each carrying a
**latched on/off state**. A leg turns on above `MA × 1.01`, off below
`MA × 0.99`, and inside that band keeps whatever it already was.

Distinct from Tripod's legs, which are three *different kinds* of reading. These
four are the same reading at four lengths. The word is shared; the meaning is not.

Do not describe a leg as "above its MA" — a latched leg can read on while price
sits just below its average, and that is the normal case near a crossing, not a
bug. `legs` in `signal.json` is the latched state that drives the vote;
`ma_above` is the raw comparison, kept only so the UI can mark the difference.

## Vote / 추세 투표

The share of legs that are on, so one of `0, 0.25, 0.5, 0.75, 1.0`. This is the
whole of the direction reading — there is no regime and no carry above it,
because the carry already happened inside each leg.

## rvol / 실현변동성

The mean of the 20-day and 60-day annualised standard deviation of daily NDX
returns. Simple returns, not log. Annualised by √252. Never call this VIX: VIX is
the market's *expectation*, rvol is what already happened, and Vol Target reads
no VIX at all.

## Raw target vs snapped target vs weight

Three numbers, and conflating any two of them misreports why a trade fired:

- **raw** — `vote × target_vol / (3 × rvol)`, clamped to `[0, 1]`. Continuous.
- **snapped** — raw rounded to the 5pp grid. **This is what the deadband tests.**
- **weight** — the snapped target, but only adopted once it sits ≥ 10pp from what
  is currently held. Otherwise the held weight carries.

`weight` is the fraction of the account in TQQQ; the remainder is cash. It is the
only one of the three that is an instruction.

Reporting the *raw*-to-held gap as the reason for a trade is wrong and will look
like the rule fired below its own threshold: raw 98.3% snaps to 100%, which is
10pp from a held 90% and therefore releases, while the raw gap is only 8pp.

## Deadband / 데드밴드

The 10pp of drift the snapped target must accumulate before it is adopted. This
is the second path-dependent step after the latched legs, and together they are
why today's weight is **not** a function of today's prices alone — the history has
to be replayed (ADR 0001).

## Target vol / 목표 변동성

The annualised volatility the levered book aims at, currently 50%. A **risk
budget, not an optimum** — the same character of value as Tripod's VIX 28, and
the only knob here meant to be turned. Raising it raises return and drawdown
together. Nothing else in `VOLTARGET` should be tuned to improve a backtest
number.

## Weight band / 비중 구간

A colour bucket for the weight (`현금 / 소액 / 중간 / 적극`), used by the chart
and the today card. Purely presentational — no rule reads it. Do not confuse it
with Tripod's Gear, which *is* the rule's output.
