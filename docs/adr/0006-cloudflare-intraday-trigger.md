# 0006 — Start the intraday run from a Cloudflare cron, not GitHub's

Status: accepted · 2026-10-01

## Context

ADR 0005 scheduled the intraday run on GitHub Actions cron ~20 minutes before
15:45 ET and let `quote.wait_for_window()` absorb the jitter. In practice the
jitter was hours, not minutes. Every run from 2026-09-28 to 2026-10-01:

| schedule (UTC) | intended | actually started (UTC) | late by |
|---|---|---|---|
| `25 19 * * 1-5` | 15:25 EDT | 23:00 – 23:50 | 3.6 – 4.4 h |
| `0 23 * * 1-5` | after close | 01:00 – 02:22 next day | 2.0 – 3.4 h |

`github.event.schedule` on each run named the right cron, so the schedule was
correct and GitHub simply started it late, which its documentation permits. Every
intraday run therefore started after the close, read `closed`, and skipped.
`origin/main` holds no `intraday call` commit at all: the same-close fill that
ADR 0005 exists for never happened once.

The settled run is unaffected in substance. It only has to land before the next
day's 15:45 ET, and it does.

## Decision

A Cron-only Cloudflare Worker (`scheduler/`) calls the `workflow_dispatch` API
with `mode=intraday` at 15:30 ET. The two intraday crons are removed from
`daily.yml`. The settled run stays on GitHub cron.

- **15:30 ET.** Dispatch-to-first-step takes well under a minute, and the
  remaining wait to 15:45 is the same sleep ADR 0005 already relies on.
- **DST.** Cloudflare cron is also UTC-only, so the pair remains (`30 19` and
  `30 20`), but the Worker checks the hour in `America/New_York` and drops the
  wrong one instead of dispatching it. One intraday run per day in Actions.
- **Retries.** Three attempts, 15 s apart. A failed dispatch means the workflow,
  and so its own failure message, never starts, so the Worker sends the Telegram
  alert itself when those secrets are set.
- **Free plan.** 2 of the 5 cron triggers, one subrequest and ~1 ms of CPU per
  run.

## Consequences

- The Worker needs a fine-grained PAT scoped to this repository with
  `Actions: read and write` and nothing else. It expires and must be rotated; an
  expired token fails loudly through the alert above.
- Holiday handling is unchanged: the Worker dispatches on holidays and
  `quote.provisional()` rejects the stale stamp.
- A manual `workflow_dispatch` with `mode=intraday` still works the same way.

## Rejected

**Keep GitHub cron and schedule earlier.** A 4-hour lead would mean starting at
11:25 ET and blocking a runner for four hours on days GitHub happens to be on
time, with no bound on the days it is later still.

**Poll from GitHub cron every few minutes.** Each poll is subject to the same
delay; it raises the odds without fixing the cause.
