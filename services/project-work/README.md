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
