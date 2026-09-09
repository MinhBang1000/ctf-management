# HSLab CTF Classroom: Feature and Remediation Guide

This document complements `README.md`, `OPERATIONS.md`, and `guideline.md`. It
summarizes what the application currently implements, the logic problems found in a
static code review, the features that are incomplete or absent, and a recommended
order for fixing them.

Review date: 2026-08-27

## 1. Product Purpose

HSLab CTF Classroom is a multi-tenant management layer for CTF training programs.
Each Lab has its own members, semesters, challenges, platform credentials, progress,
reminders, and reports. A separate Super Admin manages Labs without entering their
day-to-day workspaces.

The application does not host CTF challenges itself. It tracks and coordinates work
performed on external CTF platforms, with Root Me as the first implemented adapter.

## 2. Architecture

### Frontend

- Next.js 16, React 19, TypeScript, and Tailwind CSS.
- Lab dashboard under `/dashboard`.
- Super Admin console under `/console`.
- Same-origin API calls through Next.js rewrites.
- HTTP-only cookie authentication.
- Responsive sidebar, command palette, theme switching, notifications, and toasts.

### Backend

- FastAPI and Pydantic for HTTP APIs and request validation.
- SQLAlchemy and PostgreSQL for persistence.
- Alembic for schema migrations.
- JWTs stored in an HTTP-only `access_token` cookie.
- Tenant identity comes from the verified JWT, not client-provided tenant IDs.
- PostgreSQL Row-Level Security provides a second tenant-isolation layer.

### Automation

- Celery worker and embedded Celery beat scheduler.
- Redis as the Celery broker/backend and shared Root Me rate limiter.
- Scheduled platform synchronization.
- T-3 and T-1 reminder emails.
- Weekly report draft generation.
- Scheduled full-database backups.
- Repeated scheduled-job failure alerts to Super Admins.

### Deployment

- PM2 manages `hslab-app`, `hslab-celery`, and `hslab-tunnel`.
- Cloudflare Quick Tunnel is the default public entry point.
- A Named Tunnel can be enabled using configuration in `.env`.

## 3. Implemented Feature Inventory

### Authentication and Roles

- Separate Member and Super Admin login endpoints.
- Roles: `lab_leader`, `presenter`, and `member`.
- Active/inactive Member accounts.
- Active/inactive Labs.
- Globally unique Member email addresses at the database level.

### Super Admin

- Create a Lab and its initial Lab Leader.
- Seed a Root Me platform for a new Lab.
- List, suspend, and reactivate Labs.
- View Labs with missing platform configuration or recent sync errors.

### Lab Management

- Member create, read, update, deactivate, and delete APIs.
- Member-to-platform account associations.
- Semester create, update, set-current, report generation, and delete operations.
- Challenge create, update, list, and delete APIs.
- Manual progress entry.
- Platform creation, editing, focus selection, connection testing, user lookup, and
  challenge lookup.

### Synchronization

- Root Me user validation retrieval using `id_auteur`.
- Root Me completion timestamp parsing.
- Early, Done, and Late classification based on the challenge deadline.
- Manual progress entries take precedence over synchronization.
- Per-Lab manual sync cooldown.
- Shared Redis token bucket across all Labs.
- Scheduled fan-out into one Celery task per Member.
- Per-run synchronization logs and repeated-failure alerts.

### Reporting and Email

- T-3 and T-1 Member reminders.
- Weekly report drafts.
- Lab Leader review, editing, approval, and sending.
- Semester ranking and weekly trend reports.
- Platform-switch annotations in semester reports.
- PDF and Excel semester-report exports.
- Lab-specific SMTP with system SMTP fallback.

### Operations

- Daily full PostgreSQL backups with retention.
- Dedicated `BYPASSRLS` backup-role design.
- Operational documentation for restore, onboarding, and alerts.

## 4. Confirmed Logic Problems

The items below are ordered approximately by security and operational impact.

### 4.1 Suspended Labs Retain Existing Access

Current behavior:

- Lab activity is checked during login in `backend/app/api/v1/auth.py`.
- `get_current_member()` in `backend/app/core/deps.py` checks whether the Member is
  active, but it does not check whether the Member's Tenant is still active.
- A user who logged in before suspension can continue using the Lab until the JWT
  expires.

Required fix:

- After loading the Member, load its Tenant and reject the request when
  `Tenant.is_active` is false.
- Add an integration test proving that an existing cookie stops working immediately
  after Super Admin suspends the Lab.

### 4.2 Cross-Lab Duplicate Emails Can Return HTTP 500

Current behavior:

- `create_member()` checks whether an email already exists.
- RLS makes Members in other Labs invisible to that query.
- The database-wide unique constraint still sees the duplicate and rejects the
  commit.
- The resulting `IntegrityError` is not caught and translated into a `409 Conflict`.

Required fix:

- Catch the database uniqueness error, roll back, and return a stable `409` response.
- Alternatively, add a narrowly scoped global email-existence operation similar to
  the login lookup policy, without exposing the matching Member record.
- Normalize email addresses consistently before storage and lookup so differences in
  letter case cannot create confusing login behavior.
- Add tests for duplicates in the same Lab, another Lab, and concurrent requests.

### 4.3 Dashboard Status Counts Do Not Represent the Current Semester

Current behavior:

- The dashboard labels the breakdown as applying to the current semester.
- The backend counts existing Progress rows from every semester in the Lab.
- It does not filter inactive Members.
- A Member/challenge pair without a Progress row is omitted instead of counted as
  Missing or Not Started.
- Weekly and semester reports treat the same absent row as Missing, so screens can
  disagree.

Required fix:

- Build the status population from active Members multiplied by challenges in the
  current semester.
- Join existing Progress rows onto that population.
- Define whether an absent row before its deadline is `not_started` and after its
  deadline is `missing`.
- Use the same status calculation in the dashboard, progress grid, reminders, and
  reports.

### 4.4 Reminder Emails Can Be Sent After the Deadline

Current behavior:

- Reminder eligibility only checks `now >= deadline - N days`.
- It never checks `now < deadline` or whether the scheduler is within the intended
  milestone window.
- After downtime, the job can send both T-3 and T-1 messages for a challenge that has
  already expired. Their subjects still say the challenge is due in three or one day.

Required fix:

- Never send a pre-deadline reminder when `now >= deadline_at`.
- Define a milestone window, such as the configured daily run's calendar day.
- Decide explicitly whether missed reminders should be skipped or caught up.
- Test normal runs, scheduler downtime, deadlines near midnight, and timezone edges.

### 4.5 A Lab Can Lose Its Last Administrator

Current behavior:

- A Lab Leader can deactivate, delete, or demote any Lab Leader, including itself.
- There is no rule requiring at least one active Lab Leader.

Required fix:

- Reject any update or deletion that would leave the Lab without an active Leader.
- Consider blocking self-deactivation and self-deletion directly.
- Perform the check and mutation in one transaction to avoid concurrent requests
  bypassing the invariant.

### 4.6 Presenter Progress Permissions Are Too Broad

Current behavior:

- Any Presenter can update any Member's status for any challenge in the Lab.
- The original role description associates a Presenter with assigned challenges.

Required fix:

- Decide the intended rule explicitly.
- If Presenters should only manage assigned challenges, require
  `challenge.presenter_id == current.id` for Presenter writes.
- Keep Lab Leaders unrestricted within their Lab.
- Add authorization tests for assigned, unassigned, and cross-tenant challenges.

### 4.7 Focus Platform Rules Are Not Fully Enforced

Current behavior:

- A nonempty credential object is sufficient to make a platform the focus.
- A successful connection test is not stored and is not required.
- An inactive platform can be selected as focus.
- The scheduled task filters for an active focus platform and then behaves as though
  no focus exists.

Required fix:

- Reject focus selection for inactive platforms.
- Store `credentials_verified_at` or an equivalent verification record.
- Invalidate verification whenever credentials or the base URL change.
- Require current verified credentials before setting focus.

### 4.8 Current Semester and Focus Platform Are Not Database Invariants

Current behavior:

- Application code unsets the old current semester or focus platform before setting
  another.
- PostgreSQL has no partial unique index enforcing one current semester and one focus
  platform per Tenant.
- Concurrent requests can therefore leave multiple rows selected.

Required fix:

- Add partial unique indexes on `tenant_id WHERE is_current` and
  `tenant_id WHERE is_focus`.
- Handle uniqueness conflicts as `409` responses.
- Keep the application-level transaction for a clear normal code path.

### 4.9 Progress Allows Contradictory Data

Current behavior:

- Manual input can save Early, Done, or Late without `completed_at`.
- Missing can be saved with a completion timestamp.
- A caller can select Early or Late without the status agreeing with the deadline.

Required fix:

- Define the manual-override contract.
- Prefer accepting a completion timestamp and deriving Early, Done, or Late on the
  server.
- Require no completion timestamp for Missing.
- If explicit status override is necessary, record the override reason separately
  and validate the permitted combinations.

### 4.10 Weekly Report Generation Is Not Idempotent

Current behavior:

- Every job or manual trigger creates another weekly report for the same Lab and
  calendar period.
- A Celery beat restart, repeated delivery, or manual click can create duplicate
  drafts and notifications.

Required fix:

- Add a uniqueness rule covering Tenant, report type, semester, and period.
- Make generation return or update the existing draft for that period.
- Never overwrite a report that has already been approved and sent.

### 4.11 Email Sending and Database State Are Not Atomic

Current behavior:

- Report approval sends SMTP email before committing the report's `sent` status.
- Reminder delivery sends email before committing its ReminderLog.
- A process crash after SMTP succeeds but before the database commit can produce a
  duplicate send on retry.

Required fix:

- Introduce an email outbox table with stable idempotency keys.
- Commit the queued message and business-state transition first.
- Let a worker send queued messages and record delivery attempts.
- For reminders, use the Member/challenge/milestone tuple as the idempotency key.

### 4.12 Report Authorization Conflicts With the User Guide

Current behavior:

- `guideline.md` says Presenters and Members can view reports.
- Every report endpoint, including list and detail, requires Lab Leader.
- The frontend still loads the report list for non-Leaders, causing a `403` instead
  of a read-only report view.

Required fix:

- Allow all active Lab roles to use report list/detail endpoints if the guide is
  correct.
- Keep edit, approve, generate, and export permissions explicit according to product
  policy.
- Otherwise update the guide and hide Reports from unauthorized roles.

### 4.13 Navigation Is Not Fully Role-Aware

Current behavior:

- Reports and Settings appear in every user's sidebar and command palette.
- Settings eventually renders a Leader-only message.
- Reports attempts a forbidden API request for non-Leaders.

Required fix:

- Define required roles on navigation entries.
- Filter the sidebar and command palette from the authenticated Member role.
- Retain backend authorization; hiding navigation is a usability improvement, not a
  security boundary.

### 4.14 Status Synchronization Reprocesses Early Entries

Current behavior:

- Sync skips an existing `DONE` row but does not skip an existing `EARLY` row.
- An unchanged Early completion is reported as updated on every sync run.

Required fix:

- Compare the detected timestamp and derived status to the stored row.
- Add an update only when persisted values actually change.
- Treat both Early and Done as completed states where appropriate.

### 4.15 Historical Reports Exclude Inactive Members

Current behavior:

- Semester-report generation queries only currently active Members.
- A Member deactivated at the end of a semester disappears from a later report for
  that semester, even though its progress still exists.

Required fix:

- Define semester enrollment explicitly, preferably with a membership/enrollment
  table or snapshot.
- Generate historical reports from semester participation, not current account
  activity.

### 4.16 Date and Range Validation Is Incomplete

Current behavior:

- A Semester can have an end date before its start date.
- Challenge points can be negative.
- Challenge deadlines are not checked against Semester dates.
- Optional text fields have inconsistent length constraints.

Required fix:

- Add Pydantic model validators and database check constraints for critical ranges.
- Decide whether out-of-semester challenge deadlines are forbidden or merely warned.
- Add boundary tests for dates, points, and week numbers.

## 5. Missing or Incomplete Features

### 5.1 Password Management

There is no password-change, forgot-password, reset-token, or administrator password
reset flow. This is especially important because new Members receive temporary
passwords. At minimum, implement authenticated password change and Lab Leader reset.

### 5.2 Complete Member Editing

The backend can update only name, role, and activity, while the frontend currently
offers only activate/deactivate and delete. There is no editing UI for profile fields
or saved platform associations, despite a backend replacement endpoint for platform
accounts.

### 5.3 Challenge Editing UI

The backend has a Challenge `PATCH` endpoint, but the frontend supports only creation
and deletion. The guide instead tells users to delete and recreate challenges. Either
build the editing UI or remove the unused endpoint and document immutability as a
real product rule.

### 5.4 Member Self-Service

Members cannot change their profile, password, or external platform identity. All
account linking is controlled by a Lab Leader. This differs from the original PRD's
Member persona description.

### 5.5 Explicit Not-Started State

There is no `not_started` Progress status. An absent row is displayed as a dash in
the progress grid, omitted from dashboard counts, and treated as Missing in reports.
The product needs one shared definition for pre-deadline incomplete work.

### 5.6 Additional Platform Adapters

The adapter interface is extensible, but Root Me is the only installed integration.
TryHackMe and other platforms mentioned as future examples are not implemented.

### 5.7 Persistent Notification System

The notification bell derives two conditions from the dashboard response. There is
no notification table, read/unread state, dismissal, history, or direct action from
each notification.

### 5.8 Tenant Deletion and Automated Offboarding

Super Admin can suspend but cannot delete a Lab. Single-Tenant export and deletion
remain manual operational procedures. This is explicitly deferred for v1 but should
be tracked if formal offboarding or data-erasure requirements apply.

### 5.9 Per-Lab Backup and Restore

Only full-database backup and restore are automated. Per-Lab export is a documented
manual SQL/CSV process, and per-Lab restore is not implemented.

### 5.10 Automated Test Coverage

The repository contains no application test suite. Missing coverage includes:

- Authentication and authorization.
- Tenant isolation and RLS behavior.
- Member, Semester, Challenge, and Progress invariants.
- Root Me response parsing and retry behavior.
- Reminder milestone behavior.
- Weekly-report idempotency.
- Email approval and failure handling.
- Backup retention and failure behavior.
- Frontend role-based workflows.

The GitHub Actions workflow was intentionally removed, so any future tests will also
need a chosen execution strategy, such as local pre-push checks or a separately
approved CI workflow.

## 6. Existing Quality Problems

### Frontend lint failures

ESLint currently reports `react-hooks/set-state-in-effect` errors in six pages:

- `frontend/app/dashboard/challenges/page.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/dashboard/platforms/page.tsx`
- `frontend/app/dashboard/reports/page.tsx`
- `frontend/app/dashboard/semesters/page.tsx`
- `frontend/app/dashboard/settings/page.tsx`

The data-loading pattern should be made consistent and should handle cancellation,
loading state, and rejected requests rather than throwing from detached async work.

### Migration formatting warning

`backend/alembic/versions/4e4c28eb0260_initial_schema.py` contains trailing
whitespace in its revision header. This is harmless at runtime but fails
`git diff --check` when the file is introduced as a new diff.

### Documentation drift

The documentation and implementation disagree in several places:

- Report visibility for Members and Presenters.
- Whether challenges can be edited.
- Whether users can change temporary passwords.
- Whether a successful platform connection test is mandatory before focus selection.
- Older README design notes describe UI limitations that the current frontend has
  already addressed.

Documentation should be updated in the same change as each product decision.

## 7. Recommended Repair Order

### Priority 0: Tenant and account safety

1. Block suspended-Tenant sessions on every request.
2. Handle global duplicate emails safely.
3. Protect the final active Lab Leader.
4. Restrict Presenter writes to the intended challenge scope.
5. Add tenant-isolation and authorization tests.

### Priority 1: Correct automation behavior

1. Fix overdue reminder delivery.
2. Make weekly report generation idempotent.
3. Add durable/idempotent email delivery.
4. Fix sync change detection for completed entries.
5. Add automation tests with controlled clocks and mocked external services.

### Priority 2: Correct reporting and data invariants

1. Define Not Started versus Missing.
2. Fix current-semester dashboard counts.
3. Add database constraints for focus/current uniqueness.
4. Validate Semester, Challenge, and Progress state combinations.
5. Preserve historical semester participation.

### Priority 3: Complete user workflows

1. Implement password change and reset.
2. Add Member and platform-account editing.
3. Resolve Challenge editing policy and UI.
4. Resolve report visibility and role-aware navigation.
5. Add Member self-service where appropriate.

### Priority 4: Operational maturity

1. Add a meaningful automated test suite.
2. Choose local checks or CI based on the team's preferred workflow.
3. Add structured monitoring for job and email failures.
4. Decide whether automated Tenant offboarding and per-Tenant restore are required.
5. Reconcile README, operations documentation, and the user guide.

## 8. Suggested Definition of Done

A repair should not be considered complete only because the happy path works. For
each change:

1. Define the business rule in plain language.
2. Enforce it in the backend.
3. Add a database constraint where the database can express the invariant.
4. Make the frontend expose only valid actions and handle failures clearly.
5. Add tests for success, authorization failure, tenant isolation, invalid input,
   concurrency where relevant, and retry behavior.
6. Update `README.md`, `OPERATIONS.md`, or `guideline.md` when user-visible behavior
   changes.

