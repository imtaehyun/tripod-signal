# 0004 — Two strategies in one dashboard

**Status:** accepted · 2026-09-16

## Context

This repository existed to answer one question for one rule: *does Tripod want a
trade today?* A second rule now needs the same treatment — a volatility-targeted
version of the trend signal Mallik (@RealTQQQTrader) published, with the sizing
added by me. See the vault notes `볼래틸리티-타게팅` and `mallik-tqqq-trend`.

The two rules answer the identical question (how much Nasdaq leverage should I
carry today?) from the identical input (NDX closes), and they disagree often.
Running them in separate repositories would mean two data pipelines fetching the
same CSV, two cron schedules, two Pages sites, and no way to see the
disagreement — which is the most interesting thing about having both.

## Decision

One repository, one pipeline, one page with **tab navigation**; each strategy
gets its own section of `signal.json` under `strategies.<key>`, and the tab key
doubles as the URL hash so `#voltarget` is linkable.

Consequences accepted:

1. **The repo is no longer "the Tripod project".** The page title is now
   *나스닥 레버리지 시그널* and `CONTEXT.md` carries a glossary per strategy.
   Tripod keeps the first tab and its own vocabulary; nothing about its rule,
   its parameters, or its validation table changed.
2. **Each strategy alerts independently.** Two labels — `strategy:tripod` and
   `strategy:voltarget` — so superseding one never closes the other's
   outstanding alert. A quiet day for one is frequently the day the other moves.
   The nav tab carries a dot when its strategy wants a trade, so switching tabs
   is never how you find out.
3. **They do not share a history window.** Tripod stops at the last settled VIX
   close and starts in 1991 because CBOE's file begins 1990-01-02. Vol Target
   reads no VIX, so it runs from 1986. Truncating it to Tripod's window would
   discard four years for no reason. Both windows are labelled on the page.
4. **`signal.json`'s shape changed.** Top-level `latest`/`stats`/`events`/
   `series`/`params`/`gears` moved under `strategies.tripod`. There are no
   external consumers; the workflow was updated in the same commit.

## Still not computing returns

ADR 0001's reasoning is unchanged and now applies twice. Neither tab shows CAGR,
max drawdown, or any performance figure, because both would need a synthetic
leveraged ETF and that needs financing-cost assumptions. Getting them wrong
produces flattering, false numbers.

That work happens in a separate lab (`~/project-private/tqqq-trend-lab`) which
does model financing — calibrated against real TQQQ to 326.2x vs the actual
326.7x over 2010–2026 — and it is where every performance claim in the vault
notes comes from. It is deliberately not this repository: this one has to keep
working unattended for years, and a returns model is a thing that rots.

The one number this decision did lean on: **latching the four MA legs costs
~0.7pp of CAGR and slightly improves max drawdown.** That was measured in the
lab before shipping, because without it the rule is unrunnable — see below.

## Why the MA legs latch

Four legs and a target-vol/(3·rvol) multiplier near 1.0 mean a single MA
crossing moves the target roughly 25pp, which walks straight through the 10pp
deadband. In testing, a price oscillating around the 50-day MA produced 45pp
round trips on **consecutive days** — 0.90 → 0.50 → 0.95 → 0.50.

So each MA became a latched leg with a ±1% band, exactly the hysteresis device
Tripod already uses on its single MA, for exactly the same reason. Measured
1985–2026: same-week reversals 95 → 9, trades 35.5/yr → 21.9/yr, max drawdown
−51.9% → −49.5%. This is not a performance tweak; it buys operability, and the
returns it costs are the price of that.

## Consequence worth stating plainly

Tripod's headline virtue — *you do not need to look at this every day* — does
**not** transfer. Vol Target moves ~22 times a year against Tripod's ~8, and its
longest untouched stretch is 387 days against Tripod's 1,001. The Vol Target tab
says so on the page, next to the tax consequence of that turnover. Anyone
choosing between the two tabs should be choosing on that, not on a return
number this repository declines to show them.
