# Tripod Signal

A daily dashboard for one specific, fully-disclosed Nasdaq trend-following rule.
It answers exactly one question — **"do I need to trade today?"** — and on most
days the answer is no.

> **Not investment advice.** This is a personal record-keeping and automation
> tool. The rule is not mine: it was published in full by the Korean YouTube
> channel **송팀장** on 2026-09-01 ([video](https://www.youtube.com/watch?v=lLdRKcBSKDM)).
> This repository is an independent reimplementation from public market data and
> has no affiliation with, or endorsement from, the original author.
> Past performance does not guarantee future results.

## The rule

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

## Does the implementation actually match the source?

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

## What this deliberately does not do

- **No return figures.** Computing them requires a synthetic TQQQ/QLD series,
  which requires financing-cost and expense-ratio assumptions the source never
  disclosed. Guessing them produces flattering, false numbers, so the page shows
  regime and gear over time and nothing else. Your brokerage knows your returns.
- **No position tracking.** The rebalance issue serves that purpose: an open
  issue is a trade you have not placed yet.
- **No backtest engine.** The full raw history is committed, so one can be
  written later without re-fetching anything.

## Layout

```
index.html              single-file dashboard, no build step
scripts/params.py       every threshold the rule depends on
scripts/fetch.py        NDX + VIX closes -> data/*.csv (append-only)
scripts/signal.py       full replay -> data/signal.json (regenerated wholesale)
data/ndx.csv            Nasdaq-100 closes, 1985-10-01 ->   (Yahoo Finance)
data/vix.csv            VIX closes, 1990-01-02 ->          (CBOE, official)
data/signal.json        canonical derived output
data/signal.js          same payload as a <script> assignment, for file://
CONTEXT.md              glossary — regime vs gear, dd52 vs MDD, etc.
docs/adr/               why the three non-obvious decisions were made
```

Usable history starts 1991 — VIX begins in 1990 and the 250-day MA needs a year
of warm-up.

## Running it

No dependencies. Python 3.9+.

```sh
python scripts/fetch.py --full     # first time: download all history
python scripts/fetch.py            # thereafter: incremental
python scripts/signal.py --stats   # rebuild data/signal.json, print validation
python -m http.server 8000         # then open http://localhost:8000
```

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
only if the data changed, deploys Pages, and **on a gear change opens an issue
labelled `rebalance`**, closing any older one.

Since the rule fires roughly eight times a year and has gone as long as 1,001
days untouched, the issue notification is the real interface. The page is where
you go to check *why*.

## License

MIT for the code. The strategy is not mine and is not licensed here.
