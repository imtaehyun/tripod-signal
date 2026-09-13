# 3. Run the daily job at a fixed 23:00 UTC and accept the DST drift

Date: 2026-09-12

## Status

Accepted

## Context

The rule reads the close and trades the next session, so the signal needs to be
published some time after the US close on the same day, for a reader in US
Eastern time.

Relevant clock facts:

- NDX closes 16:00 ET; VIX settles ~16:15 ET; providers stabilise well after.
- GitHub Actions cron is **UTC only and has no DST awareness**. A schedule
  written for EST silently runs an hour off for eight months of the year.
- Scheduled runs on GitHub are also best-effort and can be delayed under load.

Options were: two crons with a guard that no-ops in the wrong season; a single
UTC hour valid year-round; or hourly polling with an "already done today" check.

## Decision

A single `cron: "0 23 * * 1-5"`.

23:00 UTC is 18:00 EST and 19:00 EDT — comfortably after the close in both
halves of the year, and still the same calendar evening for the reader. `1-5`
in UTC maps to the same US weekdays at this hour, so no weekend runs.

`workflow_dispatch` is also wired up for manual runs.

## Consequences

- The publish time drifts by one hour across the year. This is invisible in
  practice: the job runs 2-3 hours after the close either way, and the reader
  acts the next morning.
- No seasonal guard logic, no duplicate schedule entries, nothing to forget to
  update — the failure mode of a DST-aware setup is silent wrongness, and the
  failure mode of this one is a one-hour shift.
- Nothing breaks if a run is delayed or skipped: `fetch.py` always pulls full
  history and merges by date, and `signal.py` recomputes from scratch, so the
  next successful run is fully self-healing. A missed day costs nothing.
- The commit step skips when data is unchanged, so US market holidays produce no
  empty commits despite the cron firing.
