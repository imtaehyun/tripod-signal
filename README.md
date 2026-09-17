# Nasdaq Leverage Signal

A daily dashboard for **two** fully-disclosed rules that answer the same
question — *how much Nasdaq leverage should I carry today?* — in two different
ways. Each tab answers exactly one thing: **"do I need to trade today?"**

| Tab | Rule | Holds | Moves |
|---|---|---|---|
| **트라이팟** (`#tripod`) | 250-day MA regime + VIX(10d) + 52-week drawdown → one of four gears | TQQQ / QQQ+QLD / cash | ~8×/yr |
| **변동성 타겟** (`#voltarget`) | four latched MAs voted, then divided by realised volatility | TQQQ / cash | ~22×/yr |

They disagree often, which is the most useful thing about running both. Each
alerts independently and the nav tab carries a dot when its strategy wants a
trade.

> **Not investment advice.** This is a personal record-keeping and automation
> tool, and neither rule is mine. Tripod was published in full by the Korean
> YouTube channel **송팀장** on 2026-09-01
> ([video](https://www.youtube.com/watch?v=lLdRKcBSKDM)). Vol Target's trend
> signal comes from **Mallik (@RealTQQQTrader)**, who published it on
> [B The Trader](https://www.youtube.com/watch?v=xoerEBGf5ZA) — the volatility
> sizing on top of it is mine, and his own rule has none.
> This repository is an independent reimplementation from public market data with
> no affiliation with, or endorsement from, either author.
> Past performance does not guarantee future results.

---

## Rule 1 — Tripod

Read three numbers after each US close. Trade the **next** session.

**Leg 1 — trend.** Nasdaq-100 close vs its 250-day simple moving average:

| Regime | Condition |
|---|---|
| up | close > MA × 1.01 |
| down | close < MA × 0.95 |
| — | in between: **carry the previous regime forward** |

**Legs 2 and 3 — fear and fatigue.** The 10-day average of VIX, and the
drawdown from the highest close of the trailing 252 sessions.

| Gear | Condition | Target | Leverage |
|---|---|---|---|
| `G3` | up **and** VIX10 < 28 **and** DD ≥ −9% | TQQQ 100% | 3.0x |
| `G15_UP` | up **and** (VIX10 ≥ 28 **or** DD < −9%) | QQQ 50% + QLD 50% | 1.5x |
| `G15_DOWN` | down **and** VIX10 < 18 | QQQ 50% + QLD 50% | 1.5x |
| `CASH` | down **and** VIX10 ≥ 18 | 100% cash | 0x |

If today's gear equals yesterday's, do nothing. That is the whole rule.

Note that `G15_UP` and `G15_DOWN` hold the **same book** and differ only in the
regime that produced them, so moving between them requires **no orders at all**
(5 occurrences in 35 years). The dashboard reports that as "상태만 변경" rather
than a rebalance, and no issue is opened.

The asymmetric band (+1% / −5%) is hysteresis: *exit carefully, enter quickly.*
It also means the regime **cannot be computed from a single day** — the history
has to be replayed, which is what `scripts/signal.py` does.

### Does the Tripod implementation actually match its source?

The source video publishes six statistics about its own 35-year backtest. With
the parameters in `scripts/params.py`, this implementation reproduces five of
them without any fitting:

| Statistic | Source | This repo |
|---|---|---|
| Backtest span | 35 years | 35.7 years |
| Trades per year | 8.1 | **7.93** (8.07 counting gear keys) |
| Median gap between changes | 6 days | **6 days** |
| Years with zero changes | 5 | **5** (2001, 2002, 2013, 2014, 2017) |
| Longest quiet stretch | 2 years 7 months | **1,001 days** |
| Downshifts | 55 | 142 ✗ |

The last row does not reconcile. Total gear changes match, so it is a counting
convention rather than a parameter error — of the 127 contiguous episodes spent
outside 3x, roughly 55 last four days or more, suggesting the source merges brief
round trips without saying so. Left documented rather than reverse-engineered
into a matching filter. See [ADR 0002](docs/adr/0002-unspecified-parameters.md).

**Four parameters are our inference, not the source's statement** — the 52-week
high basis, MA length, MA kind, and which Nasdaq index. They are marked
`INFERRED` in `params.py` and daggered on the page. ADR 0002 has the reasoning.

---

## Rule 2 — Vol Target

Mallik's published trend rule is a single line: `NDX close > SMA(250)` → 100%
TQQQ, else cash. It works, and it takes an **87% drawdown** doing it, because it
reads direction and never reads size. This tab keeps his signal and adds the
missing half.

Read after each close, trade the **next** session. Holds TQQQ and cash, nothing
else.

1. **Vote.** Each of the 50/100/200/250-day SMAs is a *latched leg*: on above
   `MA × 1.01`, off below `MA × 0.99`, carrying its state in between. The vote is
   the share that are on — `0, 0.25, 0.5, 0.75, 1.0`.
2. **Measure speed.** `rvol` = mean of the 20-day and 60-day annualised stdev of
   daily returns.
3. **Size it.**

   ```
   raw    = vote × target_vol / (3 × rvol),  clamped to [0, 1]
   target = raw snapped to a 5pp grid
   weight = target, adopted only once it sits ≥ 10pp from what is held
   ```

`weight` is the fraction of the account in TQQQ. The rest is cash — and earns
interest, which matters more than people expect.

**Why divide by volatility.** A 3x ETF's rebalancing decay is
`-(L²-L)/2 × σ²`, which at L=3 is `-3σ²`. Measured on NDX since 1985, the top
volatility quintile decays **16.7× faster** than the bottom. Holding a constant
3x through that is the largest avoidable cost in a leveraged trend rule, and
sizing inversely to σ pins the term to a constant. It also drops average leverage
from 2.3x to 1.9x, so the borrowing cost falls too.

**`target_vol` is a risk budget, not an optimum** — the same character of value as
Tripod's VIX 28, and the only knob here meant to be turned.

**Why the legs latch.** Without it the rule is unrunnable: four legs and a
multiplier near 1.0 mean one MA crossing moves the target ~25pp, straight through
the 10pp deadband, so a price oscillating around the 50-day MA produces 45pp
round trips on consecutive days. Latching cut same-week reversals from 95 to 9
and trades from 35.5/yr to 21.9/yr, cost ~0.7pp of CAGR, and slightly *improved*
max drawdown. It buys operability, not performance. [ADR 0004](docs/adr/0004-second-strategy.md).

**What you give up versus Tripod.** Tripod's headline virtue — you do not need to
look at this every day — does not transfer. ~22 moves a year against ~8, longest
quiet stretch 387 days against 1,001, and roughly 5× the turnover, which in a
taxable account eats a large part of the edge. The tab says all of this on the
page, next to the signal.

Vol Target reads no VIX, so its history starts in **1986** rather than 1991.

---

## What this deliberately does not do

- **No return figures, for either strategy.** Computing them requires a synthetic
  TQQQ/QLD series, which requires financing-cost and expense-ratio assumptions.
  Guessing them produces flattering, false numbers, so the page shows state over
  time and nothing else. Your brokerage knows your returns.
  That modelling happens in a separate lab that does charge for financing —
  calibrated against real TQQQ to 326.2x vs the actual 326.7x over 2010–2026 —
  and every performance claim about these rules comes from there, not from here.
  Kept out on purpose: this repo has to run unattended for years, and a returns
  model is a thing that rots.
- **No position tracking.** The rebalance issue serves that purpose: an open
  issue is a trade you have not placed yet.
- **No backtest engine.** The full raw history is committed, so one can be
  written later without re-fetching anything.

## Layout

```
index.html              single-file dashboard, no build step
scripts/params.py       every threshold BOTH rules depend on
scripts/fetch.py        NDX + VIX closes -> data/*.csv (append-only)
scripts/signal.py       orchestrates both replays -> data/signal.json
scripts/voltarget.py    the Vol Target replay (latched legs + deadband)
data/ndx.csv            Nasdaq-100 closes, 1985-10-01 ->   (Yahoo Finance)  [committed]
data/vix.csv            VIX closes, 1990-01-02 ->          (CBOE, official) [committed]
data/signal.json        derived output                                       [gitignored]
data/signal.js          same payload as a <script> assignment, for file://   [gitignored]
CONTEXT.md              glossary — per strategy; regime vs gear, raw vs weight
docs/adr/               why the four non-obvious decisions were made
```

`signal.json` is keyed `strategies.tripod` and `strategies.voltarget`.

Tripod's usable history starts **1991** — VIX begins in 1990 and the 250-day MA
needs a year of warm-up. Vol Target needs no VIX so it starts **1986**. The two
windows are deliberately not aligned; truncating Vol Target would discard four
years for nothing.

## Running it

No dependencies. Python 3.9+.

```sh
python scripts/fetch.py --full     # first time: download all history
python scripts/fetch.py            # thereafter: incremental
python scripts/signal.py --stats   # rebuild data/signal.json, print validation
python -m http.server 8000         # then open http://localhost:8000
```

**A fresh clone has no `data/signal.json`** — the derived payload is gitignored
and generated in CI right before deploy (ADR 0001). Run `scripts/signal.py`
once and the page works; until then it tells you so.

`index.html` also works by double-clicking it. A `file://` page cannot `fetch`,
so it reads `data/signal.js` — which is why `signal.py` writes the payload twice.

`certifi` is optional but helps if your local Python has an empty CA store.

> `fetch.py` sends a deliberately minimal `User-Agent`. Yahoo fingerprints
> requests and returns a blanket 429 to a full Chrome UA string that is not
> backed by a real Chrome TLS fingerprint. Do not "improve" it.

## Automation

[`.github/workflows/daily.yml`](.github/workflows/daily.yml) runs at 23:00 UTC
Mon–Fri (18:00 EST / 19:00 EDT — after the close, same evening, DST-proof; see
[ADR 0003](docs/adr/0003-fixed-utc-cron.md)). It fetches, recomputes, commits
only the raw CSVs if new sessions arrived, deploys Pages, and **when a trade is
required opens an issue labelled `rebalance` plus `strategy:<key>`** with the
concrete orders in it, closing any older one *for that strategy only*. The two
strategies alert independently; a regime-only Tripod change opens nothing.

It is a single job on purpose: the derived signal is never committed, so a
separate deploy job would check out a tree without it.

For Tripod, which fires roughly eight times a year and has gone 1,001 days
untouched, the issue notification is the real interface and the page is where you
go to check *why*. For Vol Target, at ~22 moves a year, you will hear from it
often enough that the page is worth actually reading.

## License

MIT for the code. Tripod's rule and Vol Target's trend signal are not mine and
are not licensed here.
