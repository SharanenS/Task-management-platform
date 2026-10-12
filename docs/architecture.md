# Architecture decisions — Phase 1

## Fixed boundaries

Single enterprise per deployment. No tenants, public registration, or public REST
business endpoints. The four future domain services are Employee, Work Management,
Workflow, and Job Execution. Each owns a separate PostgreSQL database, migrations,
authorization, and durable publication. The gateway owns neither domain rules nor
a business database. Domain services will not be publicly exposed.

## Foundation decisions

- Monorepo: `frontend/`, `gateway/`, `services/`, and `docs/`.
- npm with a committed lockfile; Python 3.13 virtual environment with pinned requirements.
- Same-origin browser requests to `/graphql`; a Next.js rewrite forwards them to
  the gateway. No CORS wildcard or alternative REST business interface.
- Rewrite destination is a trusted server-side build setting, never user input.
  Rebuild production frontend images if the destination changes.
- Strawberry is the source of the schema. Export SDL with `gateway/export_schema.py`;
  GraphQL Code Generator emits typed documents from SDL and checked-in operations.
- TanStack Query owns server state. The status query refreshes every 15 seconds
  in active pages, times out after 8 seconds, and supports explicit retry.
- A failed refresh hides previously successful status data. The status describes
  gateway reachability only, not aggregate platform readiness.
- The only Phase 1 operation is `SystemInfo`; fields are name, version, environment,
  and status. There are no mutations or persisted business entities.
- Two container services only. No empty database, broker, Redis, or identity server.
- Compose project name is `enterprise-task-platform-phase1`; host ports default
  to 3010 and 8010 to coexist with the owner's older project on 3000/8000.
- Local Compose ports bind to loopback. Both application containers use non-root users.

## Interface conventions

Taskspace is the interface label for Enterprise Task Platform. A neutral canvas,
forest green accent, system fonts (no remote font dependency), restrained borders,
and an 8px spacing rhythm establish the visual foundation. Local shadcn/ui-style
source components use Tailwind 4, class-variance-authority, and Radix primitives.
`components.json` enables subsequent shadcn component additions. Interactive
navigation includes focus management and a modal mobile drawer.

Dashboard business content is explicitly illustrative. Planned feature controls
are disabled. `/system` contains real data; `/design-system` contains explicit
interactive previews. No forms are needed yet; React Hook Form and Zod will be
introduced when the first actual business form needs them.

## Incremental security

Public metadata contains no hostnames, tokens, credentials, or infrastructure
inventory. GraphQL errors are sanitized. Initial depth and alias caps limit this
small schema; GET queries are disabled. Request IDs are server-generated, and
structured request logs exclude query text, headers, and payloads. GraphiQL is
development-only. Introspection is not an authorization mechanism.

This is a local foundation, not a production security release. OIDC with PKCE,
secure sessions, JWT validation, service authentication, and authorization belong
to their functional slices; broader complexity/rate controls and telemetry grow
with the schema. An exact session/token forwarding contract must be recorded in
Phase 2 before introducing authenticated data.

## Dependency references

Versions were resolved from the npm/Python package indexes during implementation.
Compatibility references: [Next.js installation](https://nextjs.org/docs/app/getting-started/installation),
[shadcn Tailwind 4](https://ui.shadcn.com/docs/tailwind-v4), and
[Strawberry FastAPI integration](https://strawberry.rocks/docs/integrations/fastapi).
