# Required Features

This document defines the remaining features that must be implemented for HSLab CTF
Classroom. Anything not listed in this document is outside the required scope.

## 1. Root Me Challenge Search by Name

### Current limitation

Creating a challenge requires the Lab Leader to know its numeric Root Me challenge
ID. In normal use, the Lab Leader usually knows only the challenge name.

### Required functionality

- Add a Root Me challenge search field to the Challenge form.
- Search Root Me using a challenge title instead of requiring an ID first.
- Display all matching results so the Lab Leader can choose the correct challenge.
- Show enough information to distinguish similar results, including the title,
  language, category, and Root Me challenge ID when available.
- After selection, automatically populate:
  - Root Me challenge ID.
  - Challenge title.
  - Category.
  - Points.
  - Root Me challenge URL when it is available from the API.
- Keep the selected Root Me challenge ID as the value used by automatic progress
  synchronization.
- Perform Root Me API calls through the backend so the API key is never exposed to
  the browser.

### Root Me challenge URL and direct access

- Add a dedicated URL field to the Challenge data model, API schemas, create form,
  and edit form.
- Store the canonical Root Me webpage URL for the selected challenge, not the Root Me
  API endpoint.
- Automatically populate the URL when Root Me search results provide one.
- Allow the Lab Leader to enter or correct the URL manually when the API does not
  provide it.
- Validate that the value is a valid `https` URL before saving it.
- Prefer official `root-me.org` challenge URLs and clearly warn before accepting an
  external domain.
- Display an Open in Root Me action in the Challenge list and relevant Challenge
  detail views.
- Open the challenge in a new browser tab so the Classroom page and its current state
  remain available.
- Use safe external-link behavior such as `rel="noopener noreferrer"`.
- Hide or disable the action when a Challenge has no URL.
- Do not construct the webpage URL from the numeric challenge ID unless Root Me
  officially supports that URL format; store the real canonical URL instead.

## 2. Password Change and Recovery

### Current limitation

Members receive temporary passwords but cannot change them. The application has no
forgot-password, password-recovery, or administrator-assisted reset workflow.

### Required functionality

- Allow an authenticated Member to change their own password, regardless of role —
  Lab Leader and Presenter accounts are self-service here too, not only the "member"
  role.
- Require the current password before accepting a normal password change.
- Allow a Lab Leader to reset the password of a Member in the same Lab.
- Add a forgot-password workflow for users who cannot sign in.
- Use expiring, single-use reset tokens.
- Never store or log plaintext passwords or reset tokens.
- Invalidate or safely handle existing sessions after a password reset.
- Apply a consistent password-strength policy to account creation, password changes,
  and password resets.

## 3. Complete Member Editing

### Current limitation

The Members interface currently supports creation, activation, deactivation, and
deletion, but does not provide a complete editing workflow.

### Required functionality

- Add an Edit action and form to the Members interface.
- Allow a Lab Leader to edit:
  - Full name.
  - Email address.
  - Role.
  - Active status.
  - Linked Root Me username and user ID.
  - Password through a dedicated reset action.
- Support adding, updating, and removing linked platform accounts.
- Validate that every selected platform belongs to the same Lab.
- Handle duplicate email addresses with a clear conflict response.
- Prevent Member editing from violating the final-Lab-Leader protection described in
  this document.

## 4. Challenge Editing

### Current limitation

The backend has a Challenge update endpoint, but the frontend only supports creating
and deleting challenges.

### Required functionality

- Add an Edit action to each challenge in the Challenges interface.
- Reuse the Challenge form for both creation and editing where practical.
- Allow a Lab Leader to edit:
  - Semester.
  - Platform.
  - Week number.
  - Root Me challenge association.
  - Root Me challenge URL.
  - Title.
  - Category.
  - Difficulty.
  - Points.
  - Presenter.
  - Deadline.
- Validate that the selected Semester, Platform, and Presenter belong to the same
  Lab.
- Clearly warn the user when changing a Root Me association could affect future
  synchronization.
- Preserve existing Progress records unless the product explicitly requires a
  deliberate migration or reset.

## 5. Self-Service Account Management (all roles)

### Current limitation

No authenticated account — Lab Leader, Presenter, or Member role alike — has a
Profile page or any way to manage their own account information.

### Required functionality

- Add a Profile page for every authenticated account, regardless of role. A Lab
  Leader manages their own account through this same page, not through the Members
  admin interface — that interface remains for managing *other* accounts in the Lab.
- Allow the account holder to view their own account information.
- Allow the account holder to change their own password (see §2).
- Allow the account holder to update their own Root Me username and Root Me user ID.
- Validate a Root Me identity before saving it when the platform supports validation.
- Do not allow the account holder to change their own role, Lab, or active status
  through this page — including a Lab Leader changing their own role or active
  status (that stays subject to the final-Lab-Leader protection in §14 and, where
  applicable, the ownership-transfer workflow in §15).
- Ensure all updates remain scoped to the authenticated account and its Tenant.

## 6. Role-Aware Navigation

### Current limitation

The sidebar and command palette show pages that some roles cannot use, including
Reports and Settings.

### Required functionality

- Define the allowed roles for every navigation item.
- Filter the sidebar based on the authenticated Member's role.
- Apply the same filtering to the command palette.
- Do not show Lab Leader-only Settings to Presenters or Members.
- Show Reports only to roles that are allowed by the final report-access policy.
- Keep backend authorization checks in place even when a page is hidden from the UI.
- Handle direct navigation to an unauthorized page with a clear access-denied state
  or redirect.

## 7. Persisted Platform Connection Verification

### Current limitation

The Test Connection action verifies credentials temporarily, but the successful
result is not stored. A platform can become the focus based only on having a nonempty
credential object.

### Required functionality

- Store when platform credentials were last verified successfully.
- Record sufficient verification state without storing additional plaintext secrets.
- Require a successful verification before a platform can become the focus.
- Prevent inactive platforms from becoming the focus.
- Invalidate the verification state when any of the following changes:
  - API credentials.
  - Base URL.
  - Adapter type or other connection-critical configuration.
- Display the verification status and last successful verification time in the
  Platforms interface.
- Provide clear states for unconfigured, unverified, verified, and verification
  failed.

## 8. Synchronization and Automation History

### Current limitation

The backend stores some synchronization and job information, but the UI exposes only
the latest synchronization state and does not provide an operational history.

### Required functionality

- Add an Automation or Job History interface.
- Display synchronization runs with:
  - Start or run time.
  - Platform.
  - Overall status.
  - Number of Members checked.
  - Updated Progress count.
  - Manual-override conflicts.
  - Per-Member errors when available.
- Display reminder, weekly-report, and backup job history.
- Clearly distinguish successful, partial, failed, skipped, and still-running jobs.
- Allow authorized users to inspect error details.
- Add a safe retry action for retryable jobs.
- Prevent retry actions from bypassing rate limits or creating duplicate work.
- Scope Lab automation history to its own Tenant.
- Keep system-wide operational visibility restricted to Super Admins.

## 9. Weekly Report Idempotency

### Current limitation

The same weekly period can produce multiple report drafts through scheduled delivery,
manual generation, retries, or scheduler restarts.

### Required functionality

- Prevent duplicate weekly reports for the same Tenant, Semester, report type, and
  reporting period.
- Enforce the uniqueness rule at the database level.
- Return or update the existing draft when generation is repeated.
- Never silently overwrite a report that has already been sent.
- Make scheduled and manual generation follow the same idempotency rules.

## 10. Report Recipient Audit Information

### Current limitation

The application records when a report was sent and who approved it, but it does not
store the recipient address used for delivery.

### Required functionality

- Store the final recipient email address on the Report record.
- Preserve the exact recipient used for each sent report.
- Display the recipient in the report detail and history views.
- Do not change historical recipient information when the Lab's professor email
  setting changes later.
- Include the recipient in relevant audit records.

## 11. Report Retry and Resend Workflow

### Current limitation

There is no explicit workflow for retrying a failed report delivery or deliberately
resending a previously sent report.

### Required functionality

- Distinguish a failed send attempt from a successfully sent report.
- Record send attempts, timestamps, recipient, and failure details.
- Allow a Lab Leader to retry a failed delivery.
- Require explicit confirmation before resending a successfully sent report.
- Prevent accidental duplicate sends caused by repeated requests or worker retries.
- Preserve the original report content and audit history.
- Clearly label original delivery, retry, and deliberate resend operations.

## 12. Persistent Notifications

### Current limitation

The notification bell derives temporary items from the dashboard response. It does
not store notifications or track user interaction.

### Required functionality

- Add persistent notifications with created time and notification type.
- Track read and unread state per recipient.
- Allow users to mark one notification or all notifications as read.
- Allow appropriate notifications to be dismissed.
- Keep a notification history instead of losing items when the dashboard condition
  changes.
- Link actionable notifications to the relevant Report, Semester, Platform, or job
  history entry.
- Scope notifications to the correct Tenant and recipient role.

## 13. Historical Reports Must Include Inactive Members

### Current limitation

Semester reports use the Member's current active status. A Member who participated in
a Semester but was deactivated later can disappear from a report generated for that
Semester.

### Required functionality

- Preserve which Members participated in each Semester.
- Generate semester reports from historical Semester participation rather than the
  Member's current active status.
- Keep former Members in historical rankings and completion statistics.
- Exclude Members who never participated in the selected Semester.
- Preserve report snapshots so later Member changes do not rewrite previously
  generated reports.

## 14. Final Lab Leader Protection

### Current limitation

A Lab Leader can currently deactivate, delete, or demote the final active Lab Leader,
leaving the Lab without an administrator.

### Required functionality

- Ensure every active Lab always has at least one active Lab Leader.
- Reject deletion, deactivation, or demotion of the final active Lab Leader.
- Prevent unsafe self-deactivation and self-deletion.
- Enforce the rule transactionally so concurrent requests cannot bypass it.
- Return a clear conflict message explaining why the action was rejected.

## 15. Lab Ownership Transfer

### Current limitation

The application has Lab Leaders but no explicit workflow for transferring primary
responsibility for a Lab.

### Required functionality

- Add an explicit ownership-transfer workflow.
- Require selection of another active Member in the same Lab.
- Promote the recipient to Lab Leader when necessary.
- Require confirmation from the current authorized owner or Lab Leader.
- Prevent the transfer from leaving the Lab without an active Leader.
- Record who initiated the transfer, the previous owner, the new owner, and when it
  occurred.
- Super Admin recovery path (decided): when a Lab has no active Lab Leader left, the
  Super Admin directly promotes/adds a Lab Leader for that Lab from the Console — a
  narrowly-scoped Super-Admin-only provisioning action (same category of narrow
  exception as `create_lab`'s existing Member-insert bypass), not general Member
  access to that Lab's data.

## 16. Lab Deletion

### Current limitation

Super Admin can suspend and reactivate a Lab but cannot delete it through the
application.

### Required functionality

- Add a Super Admin-only Lab deletion workflow.
- Require explicit confirmation using the Lab name or another strong confirmation
  mechanism.
- Show the affected data before deletion.
- Prevent accidental deletion through ordinary status controls.
- Deletion is immediate (decided) — not a recoverable/retention-window design — but
  must show an explicit "are you sure you want to delete this Lab?" confirmation
  prompt naming the Lab before executing.
- Record the deletion request and actor in the audit log.
- Ensure all Tenant-owned data is deleted consistently when permanent deletion is
  executed.

## 17. Per-Lab Data Export

### Current limitation

Exporting one Lab currently requires a manual database procedure.

### Required functionality

- Add an authorized export workflow for a single Lab.
- Include Members, platform associations, Semesters, Challenges, Progress, Reports,
  reminder history, and relevant automation history.
- Use a documented, versioned export format.
- Exclude encrypted credentials and secret configuration by default.
- Restrict Lab exports to authorized Lab Leaders and/or Super Admins according to the
  final policy.
- Record who requested and downloaded the export.
- Support large exports as background jobs when necessary.

## 18. Per-Lab Backup and Restore

### Current limitation

The application currently supports backup and restore only for the complete shared
database. It cannot back up or restore one Lab independently.

### Required functionality

- Add a backup workflow for one selected Lab without including another Lab's data.
- Include all data required to reconstruct the Lab and its relationships.
- Define a versioned backup format and record the application/schema version used to
  create it.
- Add a restore workflow that validates the backup before changing application data.
- Define how restore handles existing Tenant IDs, email conflicts, platform IDs, and
  other unique values.
- Support restore into the original Lab and, when explicitly allowed, into a newly
  created Lab.
- Exclude or separately protect API keys, SMTP passwords, and other encrypted
  credentials.
- Restrict backup and restore operations to explicitly authorized roles.
- Run large backup and restore operations as tracked background jobs.
- Require strong confirmation before a restore overwrites existing Lab data.
- Record backup and restore operations in the audit log.
- Preserve the existing full-database backup and disaster-recovery procedure.

## 19. Audit Logging

### Current limitation

The application records some job and report information but does not provide a
general audit trail for sensitive administrative actions.

### Required functionality

- Add an immutable audit-log model.
- Record at least the following actions:
  - Member creation, editing, activation, deactivation, deletion, and role changes.
  - Lab ownership transfer.
  - Challenge creation, editing, and deletion.
  - Semester creation, editing, current-semester changes, and deletion.
  - Platform credential/configuration changes and focus changes.
  - Report editing, approval, sending, retrying, and resending.
  - SMTP and professor-email configuration changes.
  - Lab suspension, reactivation, export, and deletion.
- Store actor, Tenant, action type, target type, target ID, timestamp, and a safe
  summary of changed fields.
- Never store passwords, API keys, SMTP passwords, JWTs, or reset tokens.
- Provide a filtered, paginated audit-log viewer for authorized roles.
- Prevent normal application users from editing or deleting audit records.

## Scope Rule

Only the features listed in this document are required. Features mentioned in other
planning documents but omitted here must not be treated as required work unless this
document is updated explicitly.
