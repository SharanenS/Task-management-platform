# Identity / Employee Service (future phase)

Owns employee profiles, application roles, status, Keycloak subject linkage,
administrator provisioning, reconciliation, and security audit records.
Keycloak owns credentials. No public signup.

Foundation integration begins in Phase 2; administration and database migrations
arrive in Phase 3. This directory contains no running service in Phase 1.
The service will own its PostgreSQL database and enforce its own authorization.
