# 1. Regenerate derived data in full; never append to it

Date: 2026-09-12

## Status

Accepted

## Context

Two kinds of data live in this repo:

- **Raw**: `data/ndx.csv`, `data/vix.csv` — daily closes from Yahoo and CBOE.
- **Derived**: `data/signal.json` — regime, gear, events, and per-leg readings,
  all computed from the raw closes plus the thresholds in `scripts/params.py`.

The obvious cheap design is to append one row of derived output per day, since
each day only adds one session. The daily job would stay O(1).

But the thresholds are not fixed. The source author states outright that VIX 28
"is not an optimum, it is the risk size I chose", and three further parameters
(52-week high basis, MA length, MA kind) are our own inferences because the
source never specified them. Changing any of them is a *likely* event, not a
hypothetical one.

If derived history were appended, changing a threshold would leave every past
row computed under the old rule while new rows used the new one. The timeline
chart would render a past that the current rule never would have produced, and
the reproduction check against the source video's statistics would silently
compare against a mixture of rules.

## Decision

`scripts/signal.py` **recomputes the entire derived history on every run** and
overwrites `data/signal.json`. It never reads its own previous output.

Raw CSVs remain append-only in spirit: an existing date keeps its stored value
unless `fetch.py --full` is passed, so a provider quietly revising last week's
close cannot rewrite history we already traded on.

## Consequences

- Changing a threshold reflows 35 years of timeline immediately and correctly.
- The full replay is also what makes the neutral-band carry rule computable at
  all: today's regime depends on the previous regime, recursively back to the
  first decisive signal. There is no stored state to drift out of sync.
- Cost is negligible — ~9,000 sessions, well under a second — so the O(1)
  argument was never worth its correctness risk.
- `signal.json` is rewritten wholesale each run, so its git diff is not
  human-readable. The raw CSVs, which are append-only, serve that purpose.
