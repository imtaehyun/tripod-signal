# 2. Pin the four parameters the source never specified

Date: 2026-09-12

## Status

Accepted

## Context

The source video discloses the rule in full, including threshold values, but
four choices needed to actually compute it are never stated. Each changes how
often the rule fires:

1. **52-week high basis** — closing high or intraday high? An intraday basis
   registers deeper drawdowns and so crosses the −9% trigger more often,
   downshifting more frequently and paying more insurance premium.
2. **MA length** — the auto-generated transcript contains both "250일선" and a
   garbled "251".
3. **MA kind** — SMA or EMA, never said.
4. **Reference index** — "나스닥 지수" is ambiguous between the Nasdaq
   Composite (^IXIC) and the Nasdaq-100 (^NDX).

Waiting for the author to clarify was an option, as was computing every variant
and displaying them side by side.

## Decision

Pin one value each, in `scripts/params.py`, with reasoning:

| Parameter | Value | Why |
|---|---|---|
| 52-week high basis | **closing high** | The rule is stated as "judge after the close". An intraday high is not observable at the moment of judgement, so a close basis is the only internally consistent reading. |
| MA length | **250** | Stated in prose; "251" appears once and only inside a garbled clause. |
| MA kind | **SMA** | The basic form in the *Leverage for the Long Run* lineage the author cites. |
| Reference index | **^NDX** | QQQ/QLD/TQQQ all track the Nasdaq-100. Judging on one index while trading instruments tracking another has no coherent justification. |

Every inferred value is marked `INFERRED` in `params.py` and carries a dagger
footnote on the page, so a reader never mistakes our inference for the source's
statement.

## Consequences

- The reproduction check validates the choice far more strongly than expected.
  With these values the implementation independently reproduces five of the
  source's six published statistics: 35 years span, 8.07 vs 8.1 gear changes per
  year, 6-day median gap, 5 zero-trade years, and a 1,001-day longest quiet
  stretch against the stated "2 years 7 months".
- One statistic does **not** reproduce: the source's "55 downshifts" against our
  142. Total gear changes match, so the discrepancy is a counting convention,
  not a parameter error. Of the 127 contiguous episodes spent outside 3x, about
  55 last four or more days, which suggests the source merges brief round trips
  without saying so. Left unresolved and documented on the page rather than
  reverse-engineered into a matching filter, which would be fitting our code to
  a number instead of to a rule.
- Because all four live in one dict, revisiting any of them is a one-line change
  plus a rerun, and ADR 0001 guarantees the whole history reflows.
