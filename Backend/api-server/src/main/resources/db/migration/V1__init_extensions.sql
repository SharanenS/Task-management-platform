-- V1: Baseline database setup.
--
-- Enables pgcrypto so future migrations can default UUID primary keys with
-- gen_random_uuid() (Phase 2+ introduces the users/projects/tasks/jobs
-- tables). No application tables are created in Phase 1 — this migration
-- exists purely to prove Flyway is wired correctly end to end.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
