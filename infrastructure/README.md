# Operational configuration

The Keycloak import, Prometheus configuration and Grafana provisioning files
in this directory support the preserved legacy runtime. Their bind mount
sources remain at their existing absolute paths during S0.

legacy/compose.yaml and legacy/compose.test.yaml refer to these files using
../infrastructure. The root replacement Compose file does not attach them.

No provider configuration is automatically applied to the replacement.
New identity, database, session and messaging configuration requires the
stage-specific design and explicit runtime authorization.

The separate auth directory belongs only to the replacement S1 environment.
compose.auth.yaml mounts its fresh taskspace-portals realm and login theme.
It contains no users, credentials or references to the legacy realm. The new
identity database volume is scoped to taskspace-portals-development.
