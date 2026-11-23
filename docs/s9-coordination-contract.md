# S9 manager coordination contract

The project-work service owns coordination records in its existing database.
The people service remains authoritative for active accounts, employee profiles
and the single company role. The shared GraphQL gateway exposes typed operations;
private project-work endpoints independently verify the service credential,
bearer identity and current people authority.

## Scope and access

Only the current project owner with MANAGER authority, or ADMIN, may create/read
coordination and append follow-ups. An unrelated manager, historical creator,
team leader, employee or HR role does not obtain coordination management access.
Each recipient must have an active explicit appointment in the same project and
an active EMPLOYEE account/profile according to a fresh people lookup. Project
leadership does not change the company role. Incoming account identifiers are
never treated as authority.

Recipient names and account references are retained as historical snapshots.
Revoking an appointment does not delete past records. It prevents selection for
new requests. Following up on an existing record does not restore recipient
access or modify project appointments. Employee response access is not exposed
by S9; S17 must independently check current actor and recipient authority.

## Records and times

UPDATE requires a topic, request details, required response time, recipients and
an explicit acknowledgement preference. MEETING and CHECK_IN additionally require
an internal location/cabin and use the scheduled time. All writes require explicit
confirmation. A new scheduled/response time and next follow-up must be future
instants with an explicit UTC offset. Browser forms convert device-local input to
UTC and saved records show UTC; no company-calendar change is made.

Requests are immutable. Follow-ups append the actor, note, next follow-up instant
and recorded time, and increment the record version. The original required time
and original project deadline remain intact. Past required times are shown as
outstanding, not silently extended. Unique request identifiers and payload hashes
make exact retries idempotent; a changed payload conflicts. Follow-ups require
the expected record version. PostgreSQL company transaction locks serialize
competing mutations with membership changes. Migration downgrade refuses to
discard retained coordination history.

Initial supported bounds: 25 recipients per request, 25 records per page, 50
follow-ups per request; topics 150 characters, details/notes 2,000, locations 300.
The UI and API expose pagination for retained request history. A follow-up beyond
the supported bound is rejected, never silently dropped.

## Response contract and deliberate stage boundary

No response-writing endpoint or employee response form exists in S9. Pending
response and acknowledgement states mean no response has been recorded; they
are not simulated acceptance evidence. When acknowledgement is not requested,
its state is NOT_REQUIRED. Future structured UPDATE responses contain progress,
blockers and next_steps. Meeting/check-in responses contain ACCEPT, or an
ALTERNATIVE decision with an offset-bearing alternative_time and reason.
Unknown fields, including supplied account identity, are rejected by the tested
contract. Authenticated response persistence, acknowledgement transitions,
employee UI and notifications belong to S17 and require further authorization
tests; the payload validator alone does not implement those workflows.

Follow-ups are manual tracking records. No automatic reminder intervals or
escalation thresholds have been approved. S9 sends no email and does not add
calling, video conferencing, external calendar synchronization, a queue or a new
service. Existing Gmail configuration remains separate and untouched.
