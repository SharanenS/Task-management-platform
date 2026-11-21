# Project-work service

S6 introduces the company working calendar. This service exclusively owns
calendar previews, immutable publications and working-day calculations in the
private project-work database. It owns no account or employee copies.

The public business boundary remains the gateway's typed GraphQL API. The private
service requires its own service credential and independently verifies the provider
JWT. It asks people for current administrator authority on each operation and again
after waiting for the publication lock. Forged actor/role headers confer no access.

The calculation module is reusable by later project/task stages. It consumes an
explicit calendar configuration or published version; it never reads an implicit
machine timezone, holiday jurisdiction, current progress or start-click timestamp.

Migration: 0001_company_calendar. Published history is retained and downgrade
refuses to discard it. Server-issued previews are actor/issuer bound, expire after
ten minutes and are checked against the current publication under a per-issuer
PostgreSQL transaction lock. Repeat publication requests are intent-bound.

Source checks: `python scripts/run-s6-source-checks.py` from the repository root.
After explicit runtime approval, use `python scripts/calendar-development.py up
--apply-migration`, then `python scripts/verify-calendar-postgres.py` and the
email-free acceptance focus `python scripts/run-s1-acceptance.py --project desktop
--calendar-only`. No command reads or modifies the legacy .env.

Production must supply HTTPS service/provider origins and private credentials.
Development service/database endpoints are private Compose addresses; no new
business or database host port is exposed. The normal web origin remains port3020.


## S7 projects

Projects and their initial deadline previews are owned here, alongside the calendar.
Migration 0002_manager_projects adds two tables without changing published calendars.
Both ADMIN and MANAGER may create; the creator becomes initial owner. Administrator
oversight is company-scoped. Manager list/search/detail access uses current owner,
not historical creator. Membership and transfer endpoints are not introduced in S7.

Project previews pin the latest calendar's working-date closing boundary and expire.
Calendar publication and project commitment use the same company transaction lock.
A later calendar publication makes an uncommitted project preview stale, while
already committed deadline snapshots remain unchanged. Creation requests are
idempotent and cannot reuse a preview to create duplicate projects. Current people
account/role authority is independently checked on every operation and after waiting
for the lock; neither a browser role nor an owner identifier establishes authority.

The existing runtime wrapper applies the latest work-domain migration. The PostgreSQL
verification now checks project commitment/calendar races too. Source entrypoint:
`python scripts/run-s7-source-checks.py`. Browser focus:
`python scripts/run-s1-acceptance.py --project desktop --projects-only`.
The project journey creates and removes only marked test resources and sends no mail.
