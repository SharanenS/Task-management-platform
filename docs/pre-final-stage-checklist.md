# Email delivery readiness (before S22)

Updated: 17 November 2026. This supplements the immutable product plan.

The owner has superseded the earlier deferral and requested Gmail connection during
S4. Sender account: dailygotasks@gmail.com. The address is known; Gmail authentication and realm
configuration are verified; real inbox delivery remains pending. The original plan is unchanged.

- [x] Owner created the dedicated Dailygo Gmail mailbox and provided its address.
- [x] Prepare the exact Gmail sender configuration and hidden-entry setup command.
- [x] Block automated email acceptance unless the live realm uses local capture.
- [x] Owner completed private Google app-password setup; SMTP authentication passed.
- [x] Owner entered the app password locally with `python scripts/configure-email.py gmail`.
      No password or app password belongs in chat, command arguments or committed files.
- [x] Confirmed delivery mode gmail with `python scripts/configure-email.py status`.
- [ ] Confirm the initial administrator's real recipient email before changing its
      preserved bootstrap marker; do not assume it equals the sender address.
- [x] Owner reported real setup-email receipt, activation, password setup and first login.
- [ ] Verify real Gmail reset, including old-password rejection and expired/used-link behavior.
- [ ] Confirm return origins, sanitized diagnostics, service health and scoped cleanup.
- [ ] Record real email evidence before S21 acceptance is closed or S22 begins.

Gmail delivery is now configured. The local capture inbox remains available at
http://127.0.0.1:8025 but is not the active outbound destination. Normal startup preserves an already configured
approved Gmail sender and stored password. Automated email tests fail closed before
creating fixtures when the realm uses Gmail; they do not switch delivery modes.
