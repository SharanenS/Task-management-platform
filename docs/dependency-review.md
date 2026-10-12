# Dependency review — 2026-10-08

The initial npm audit reported 12 high-severity development dependency entries
stemming from one advisory: [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
`braces <=3.0.3` can exhaust the stack when parsing deeply nested patterns. The
dependency paths are GraphQL Code Generator and Next.js ESLint tooling, which
consume repository-controlled patterns in this project. They do not accept
public request input here.

The audit's suggested automatic fixes downgrade GraphQL Code Generator to 3.2.0
and the Next.js lint configuration to 14.2.35. Those are not compatible upgrades
for this foundation. No forced downgrade or unsupported override was applied.
Recheck upstream patches before production release. Do not describe the full
dependency tree as vulnerability-free.

`npm audit --omit=dev` reported zero vulnerabilities for the production frontend
dependency set on this date.

Node 24 LTS is required by the resolved current toolchain. `.nvmrc`, the npm engine
constraint, and Docker images agree on that major version. All direct npm versions
and transitive lockfile resolutions are pinned. Python dependencies are pinned in
`gateway/requirements.lock`; that development lock includes test tooling and is
also used by the local verification container. Production image slimming and
separate production dependency locks are deferred to deployment work.
