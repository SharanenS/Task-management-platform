# Phase 1 acceptance

## User journey

Open the dashboard, distinguish demo business content from the real gateway
indicator, inspect `/system`, and verify loading, outage, retry, and recovery.
Navigate at desktop/mobile widths and explore reusable states at `/design-system`.

## Automated checks

Run the commands in the root README. Gateway tests cover the real GraphQL contract,
health endpoints, invalid requests, alias limits, GET restrictions, and schema
export consistency. Frontend tests cover loading, successful data, GraphQL failures,
stale-status rejection, and retry. Playwright exercises desktop/mobile integration,
navigation, no page overflow, network failure/recovery, and component previews.

## Manual browser checklist

- [ ] Start the stack and open http://localhost:3010.
- [ ] Dashboard clearly labels sample content; planned feature controls are disabled.
- [ ] Gateway indicator becomes connected from an actual POST to `/graphql`.
- [ ] System status shows the gateway version and environment.
- [ ] Stop the gateway (`docker compose stop gateway`), then click Refresh status.
- [ ] Unavailable state replaces successful data, with a retry action.
- [ ] Start the gateway (`docker compose start gateway`), then retry; it recovers.
- [ ] At 390px width, open/close navigation; select a page; no page-level overflow.
- [ ] Tab through controls; focus is visible; Escape closes the mobile drawer.
- [ ] Design system empty/loading/error/success previews work, including retry.
- [ ] Reload a nested route and visit an unknown route.
- [ ] Review the design and behavior with the project owner.

## Acceptance gate

Do not mark accepted until actual checks pass and the owner has reviewed the
browser experience. Do not commit/push before acceptance. No repository remote is
configured by this implementation. Suggested eventual commit:
`feat: establish Phase 1 application shell and GraphQL foundation`.
