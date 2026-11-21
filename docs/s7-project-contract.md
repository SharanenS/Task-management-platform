# S7 project ownership and initial deadline contract

This supplements the immutable product plan. S7 introduces the manager shell,
project creation, authorized listing/details, objectives and the initial approved
deadline. Membership, leader appointments and owner-transfer commands remain S8
or later work. No task planning, forecast or delivery-progress data is fabricated.

ADMIN and MANAGER can create projects. The creator becomes the initial owner,
including an administrator creating a project. Creator and current owner are
separate stored references; historical creation does not grant permanent access
after ownership changes. ADMIN can oversee same-company projects. MANAGER sees
only currently owned projects until explicit membership is introduced. EMPLOYEE
and HR gain no project authority from their company role.

Names and objectives are plain text. A project requires a published company
calendar. The chosen deadline must itself be a working date: preview resolves its
closing time in the configured timezone; it never silently shifts the commitment.
The owner confirms the initial agreed deadline. This is not a separate admin
approval workflow. A past deadline is shown as a warning rather than silently
changed. The preview expires and is bound to its issuer/actor/current calendar.
Calendar publication and project commitment share the company transaction lock.
If the calendar changes, the creator must review a fresh preview.

Initial deadline date, UTC/local boundary, timezone/rule version and calendar
reference are retained. Later revisions or forecasts must not overwrite them.
Names recorded with actor references are audit/assignment snapshots, not copied
account records. People remains the authority for current account/role status.
