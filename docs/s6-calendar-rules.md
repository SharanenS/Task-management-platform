# S6 approved company calendar rules

Approved by the owner on 17 November 2026. This supplements the immutable product
plan; it does not edit or replace that document.

- Durations are positive whole working days, not hourly effort estimates.
- A working planned start counts as day one. A non-working start rolls forward,
  with the requested and effective starts and adjustment exposed.
- The deadline is the final working day's configured closing time in the company's
  explicitly selected IANA timezone. No locale, hours, workweek or holidays are seeded.
- A dependent task's earliest handoff is the next working day's opening after the
  prerequisite's scheduled finish. Same-day handoff is not included initially.
- A date exception overrides a holiday, and a holiday overrides the weekly pattern.
  Reopening a holiday requires an explicit working exception and its own hours.
- Overnight shifts and fractional days are not supported initially. Ambiguous or
  nonexistent local opening/closing times are rejected rather than guessed.
- Each published calendar version is immutable. Server-issued, actor-bound previews,
  confirmation and current-version checks precede publication. Publication never
  rewrites earlier versions or commitments. Existing-project schedule revision is
  a future work-domain operation and must itself preview impact and preserve history.
- Clicking Start, late starts and incomplete work never silently move commitments.
  Forecasts, original dates, revisions and actual outcomes remain separate concepts.
- Calculations explicitly identify their version and include counted dates, local
  and UTC boundaries. Unsupported/unresolvable windows return an error, not a date.

Example fixture only: Monday–Friday 09:00–17:00, no holidays, three working days
starting Friday finishes Tuesday. These values are never installed as company data.

The existing architecture assigns the calendar to services/project-work and its own
private database. People remains the authoritative account/role service. Calendar
operations independently verify identity and current administrator authority; no
account or employee records are copied into the work database. Later project stages
reuse the same versioned calculation functions.


Timezone reproducibility: each preview and publication records the pinned tzdata
release and calculation uses that packaged data, not the host's timezone database.
A missing historical release produces an explicit unsupported-version error;
it must never silently recalculate an older version using newer rules. Later
committed schedules must retain their calculated boundaries as well as version IDs.
