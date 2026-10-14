# Employee Service

The Employee Service owns employee profiles, active access status, and application
roles. Its internal HTTP contract is reachable only on the Compose network and
requires the shared internal-service credential. The GraphQL gateway supplies the
already validated Keycloak subject; browser-provided identity headers are never
accepted directly.

The service owns its PostgreSQL database and Alembic migrations. Phase 2 exposes
only subject-based profile resolution. Employee administration belongs to Phase 3.

For local bootstrap, use `scripts/bootstrap-development.ps1` after the stack is
healthy. It creates the configured Keycloak development user and invokes the
service's internal provisioning command inside its container.
