# HSLab CTF Classroom — User Guide

This is a guide to **using** HSLab CTF Classroom — every role, every page, every
feature, written for the people who log in and use it day to day (Lab Leaders,
Presenters, Members, and the Super Admin who manages Labs). If you're looking for
how to install/run/deploy the app, see `README.md`. If you're looking for backup,
alerting, or incident-response procedures, see `OPERATIONS.md`.

---

## 1. What this app is

HSLab CTF Classroom tracks a CTF training Lab's progress through a semester of
challenges (typically on Root Me): who's solved what, who's behind, and produces
reports for the professor/mentor overseeing the Lab. Each **Lab** (e.g. "High Speed
Network Lab") is a fully isolated workspace — its members, semesters, challenges, and
data are never visible to another Lab. A separate **Super Admin** oversees the whole
system across every Lab (creating Labs, monitoring health) but does not manage any
one Lab's day-to-day content.

---

## 2. Roles

| Role | Logs in at | Can do |
|---|---|---|
| **Super Admin** | `/console/login` | Create/suspend Labs, see system-wide health. Nothing inside any one Lab. |
| **Lab Leader** | `/login` | Everything inside their Lab: manage members, semesters, challenges, progress, platform credentials, reports, and SMTP settings. |
| **Presenter** | `/login` | Same visibility as a Member, plus can record/edit Progress (e.g. to mark a challenge they presented as done for someone). |
| **Member** | `/login` | Read-only: view members, semesters, challenges, progress, platforms, and reports. Cannot change anything. |

There is no cross-Lab or cross-role access beyond this table — a Member cannot see
another Lab's data, and a Lab Leader cannot see another Lab or act as Super Admin.

---

## 3. Logging in

- **Lab members** (Lab Leader / Presenter / Member): go to `/login`, enter your email
  and password. You'll land on your Lab's **Overview** page.
- **Super Admin**: go to `/console/login` (linked from the bottom of the regular
  login page as "Go to system console"). Lands on the **System Console**.

Accounts are provisioned by whoever manages you — a Lab Leader adds Members (§5.2),
a Super Admin creates the first Lab Leader when creating a new Lab (§10). There is no
self-signup.

---

## 4. The interface

### 4.1 Sidebar

The left sidebar is how you move between pages: **Overview, Members, Semesters,
Challenges, Progress, Platforms, Reports, Settings**. The current page is highlighted.
At the bottom: your name, role, and a sign-out button.

Click the small circular button on the sidebar's right edge to **collapse it to just
icons** (useful on a smaller screen) — your choice is remembered next time you visit.
On a narrow window (under ~900px), the sidebar becomes a slide-in drawer opened via a
hamburger button in the top bar.

### 4.2 Top bar

Across the top of every page:
- **Page title** — and on the Super Admin Console, a red `SYSTEM SCOPE` badge so it's
  never confused with a Lab's own view.
- **Search / jump to a page** — click it, or press **⌘K** (Mac) / **Ctrl+K**
  (Windows/Linux) anywhere, to open the command palette: type a page name and press
  Enter (or click it) to jump straight there. Press Escape or click outside to close.
- **Theme toggle** (sun/moon icon) — switches the whole app between dark and light.
  Your choice is remembered on this device.
- **Notification bell** — click it to see anything waiting on you right now: a weekly
  report ready for review, or a semester that ended without a semester report yet. A
  red dot means there's something there.

### 4.3 Toasts

Actions that change something (saving settings, running a sync, sending a report,
exporting a file) pop up a small confirmation in the bottom-right corner — green for
success, red for an error, blue for informational. They disappear on their own after
a few seconds, or click the ✕ to dismiss early.

---

## 5. Overview page

Your Lab's home page. Shows:

- **Sync now** button (top right) — manually triggers a sync against your Lab's
  focus platform right now, instead of waiting for the scheduled sync. Disabled if no
  focus platform is configured yet (see §9). Shows a spinning icon while running and a
  toast when it finishes (including how many updates it found).
- **Weekly report awaiting approval** banner — appears only when there's a draft
  report ready for you to review; click "Review & send" to jump straight to it.
- **Focus platform not configured** warning — appears if nobody has set up the
  Lab's Root Me credentials yet; automatic sync/reminders can't run until this is
  fixed. Click "Configure now" to jump to Platforms.
- **Stat cards** — active/total members, semester count, challenge count, and
  reminders sent in the last 7 days.
- **Status breakdown** — a bar + legend showing what fraction of Progress right now
  is Early / Done / Late / Missing, plus a nudge card if there are members who need a
  nudge (late or missing), and a shortcut to Reports.

---

## 6. Members

Manage who's in your Lab.

**Viewing** (everyone): a table of every member — name (with an initials avatar),
email, role, linked platform accounts, and active/inactive status.

**Managing** (Lab Leader only):
- **+ New Member** — opens a form: full name, email, a temporary password (they can
  be told to change it — there's no self-service password reset yet, so if someone
  forgets theirs, a Lab Leader currently has to recreate the account), and a role
  (member / presenter / lab_leader).
- **Platform accounts** — link this member's Root Me account so sync can track their
  progress. For each platform: pick the platform, enter their Root Me username, and
  their **Root Me ID (id_auteur)** — this numeric ID, not the username, is what sync
  actually matches on, so it's required for every linked account. Don't know it? Enter
  the username and click **"Tra cứu ID"** ("look up ID") to auto-fill it from Root
  Me — always double-check the result before saving, since it's a lookup, not a
  guaranteed match. Use **+ Add account** to link more than one platform per member.
- **Deactivate / Activate** — an inactive member is excluded from Progress tracking,
  reminders, and reports, but their history is kept (use this instead of deleting
  when someone leaves the Lab temporarily, e.g. a semester off).
- **Delete** — permanently removes the member. Cannot be undone; prefer Deactivate
  unless you're sure.

---

## 7. Semesters

A semester is a training period (e.g. "Fall 2026") that Challenges belong to.

**Viewing** (everyone): every semester as a card, with its date range and a
`current` badge on the active one.

**Managing** (Lab Leader only):
- **+ New Semester** — name, start date, end date, and an optional "set as current"
  checkbox.
- **Set current** — marks a semester as the Lab's active one; this is what drives
  which challenges/progress the Overview page and default filters show.
- **Generate Report** — produces a full **semester report**: per-member ranking,
  cumulative points, and a completion trend across the semester. See §11.2 for the
  full report workflow — this button just kicks it off.
- **Delete** — removes the semester **and all of its challenges**. Cannot be undone.

---

## 8. Challenges

The actual CTF challenges members work through, grouped by week within a semester.

**Viewing** (everyone): a table — week, title, semester, presenter, deadline.

**Managing** (Lab Leader only): **+ New Challenge** opens a form:
- Semester, Platform, and week number.
- **Root Me challenge ID** (optional) + **"Fetch from Root Me"** — if you know the
  Root Me challenge ID, this pre-fills the title, category, and points straight from
  Root Me (review before saving — it's a convenience, not a guarantee of accuracy).
  Linking the Root Me ID here is what lets scheduled sync automatically detect when a
  member completes this specific challenge — without it, this challenge can only be
  tracked manually.
- Title, category, difficulty, points, an optional presenter (who's teaching/covering
  it), and a deadline (date + time).

Challenges can be deleted but not edited after creation — if something's wrong,
delete and recreate it.

---

## 9. Progress

A grid: every active member down the side, every challenge in the selected semester
across the top. Use the semester dropdown (top right) to switch semesters.

- **Member / Presenter**: click any cell to set that member's status for that
  challenge — Early, Done, Late, or Missing. This is how progress gets recorded
  manually (e.g. for a presenter double-checking or overriding automatic sync
  results).
- **Member (read-only role)**: sees the same grid but as status badges only, no
  editing.

A status set here manually takes precedence — automatic sync won't silently overwrite
a manual entry (it flags it as a conflict instead; see §9's sibling section on
Platforms → Sync now results).

**What Early / Done / Late / Missing means**: Done = completed by the deadline;
Early = completed with real time to spare before the deadline; Late = completed after
the deadline passed; Missing = deadline passed with no completion recorded yet.

---

## 10. Platforms

Where your Lab's Root Me credentials live, and where sync is triggered.

Every Lab is seeded with one Root Me platform automatically — you don't create a new
one, you configure the existing one's API key.

**Viewing** (everyone): each platform's connection status (`configured` /
`not configured`), whether it's the Lab's current `focus` platform, and its last sync
time.

**Managing** (Lab Leader only):
1. **Edit** — set the platform's name, base URL, and Root Me **API key** (get this
   from your Lab's Root Me account at `root-me.org/?page=preferences`). The key is
   stored encrypted and is never shown again after saving — if you need to change it,
   you're replacing it, not viewing the old one.
2. **Test connection** — verifies the saved key actually works against Root Me before
   you rely on it. You must run this successfully at least once before you can make a
   platform the Lab's focus.
3. **Make focus** — sets this as the platform scheduled sync, reminders, and the
   Overview "Sync now" button all run against. A Lab has exactly one focus platform
   at a time; switching it mid-semester is supported but flagged clearly in semester
   reports (§11.2) since points/completion from different platforms are never
   silently compared as one continuous scale.
4. **Sync now** — manually runs a sync immediately (only enabled once credentials are
   configured). Reports back how many members were checked, how many Progress
   updates were found, how many were skipped as manual-override conflicts, and any
   errors.

Scheduled sync also runs automatically in the background (daily by default — ask
whoever deployed the app if you need the exact schedule) against whichever platform
is currently marked focus.

---

## 11. Reports

Two kinds of report, both starting as an editable **draft** that a Lab Leader reviews
before it's sent anywhere — nothing goes to your professor automatically.

### 11.1 Weekly report

Generated automatically every Monday (or manually — Lab Leader can click
**"Generate weekly now"** to produce one on demand without waiting). Summarizes the
past week: Done/Late/Missing counts and who's ahead (Early) this week.

### 11.2 Semester report

Generated manually — from the **Semesters** page, click **Generate Report** on any
semester (§7). Covers the whole semester: per-member Done/Late/Missing counts,
cumulative points (challenge points earned, not Root Me's own global score), an
internal ranking, and a completion trend broken out **by challenge week**, not
calendar week. If the semester's challenges span more than one focus platform (the
Lab switched focus mid-semester), the report calls that out explicitly per week/member
rather than blending the numbers.

Semester reports (only) also have **Export PDF** and **Export Excel** buttons,
available whether the report is still a draft or already sent — these render exactly
what was reviewed at generation time, so exporting later won't silently include newer
data that arrived after the report was approved.

### 11.3 Reviewing and sending (either report type, Lab Leader only)

1. Click **Review** on a draft report to open it.
2. Edit the draft text freely in the textbox, then **Save draft** to keep your edits
   without sending yet.
3. Enter the recipient's email under **Send to** (pre-filled from the professor email
   set in Settings §12.2, if any) and click **Approve & Send** — this actually emails
   it and cannot be undone, so you're asked to confirm.

A sent report becomes read-only — you can still open it to view what was sent and
when, and who approved it, but it can't be edited further.

Presenters and Members can view any report's content (draft or sent) but can't edit
or send.

---

## 12. Settings (Lab Leader only)

### 12.1 SMTP

The email server used to actually send reminders and reports. Set Host, Port,
Username, Password, and a From address, then **Save SMTP settings**. If you haven't
configured this, the app falls back to a system-wide default (if the deployment has
one set up) — the badge next to "SMTP" shows whether your Lab has its own config or
is riding on the system default. Use **Send a test email** to confirm it actually
works before relying on it for a real report.

### 12.2 Professor email

The email address that pre-fills the "Send to" field when approving a weekly report
(§11.3) — saved here once so you don't have to retype it every week. You still
explicitly confirm the recipient every single time you send; this only saves typing.

---

## 13. Reminders (automatic, no action needed)

The app automatically emails a member directly (no Lab Leader approval step, since
this is internal to the Lab) when a challenge deadline is 3 days away (T-3) or 1 day
away (T-1) and they haven't completed it yet (no Progress recorded, or marked
Missing/Late). Each member gets reminded about each challenge/milestone at most once.
Reminders need SMTP configured (§12.1) to actually go out — check the "Reminders sent"
stat on Overview to confirm they're working.

---

## 14. Super Admin: System Console

Reached at `/console/login`, entirely separate from any Lab. Shows:

- **Stat cards** — total, active, and inactive Labs system-wide.
- **Labs needing attention** — any Lab whose focus platform isn't configured, or
  whose last sync had errors — a quick health check across every Lab without having
  to log into each one.
- **Labs table** — every Lab, its status, and creation date. **Suspend** an active
  Lab (its members can no longer log in) or **Reactivate** a suspended one.
- **New Lab** — creates a Lab plus its first Lab Leader account in one step: Lab
  name, a URL-safe slug, and the leader's name/email/temporary password. That Lab
  Leader can then add their own Members, Semesters, Challenges, etc. — the Super
  Admin doesn't manage any of that.

---

## 15. Typical workflows

**Onboarding a new Lab (Super Admin)**: Console → New Lab → give the Lab Leader their
temporary password out-of-band (Slack/email) → they log in at `/login` and change
nothing needs to change from their side; from here on it's entirely their Lab.

**Setting up a new Lab for the first time (Lab Leader)**: Platforms → edit the seeded
Root Me platform with your API key → Test connection → Make focus → Semesters →
create your first semester and set it current → Challenges → add each week's
challenges (use "Fetch from Root Me" if you have the Root Me challenge ID) → Members
→ add your members with their Root Me IDs → Settings → configure SMTP so reminders
and reports can actually send.

**Adding one new member mid-semester**: Members → New Member → fill in their info →
link their Root Me account via "Tra cứu ID" or by entering their ID manually → done;
they'll start showing up in the next sync and in Progress.

**Closing out a semester**: Semesters → Generate Report on the ending semester →
Reports → Review the draft, edit if needed → Approve & Send to your professor →
optionally Export PDF/Excel for your own records.

---

## 16. Tips

- **Dark/light mode and sidebar collapse are per-device**, not per-account — they
  won't follow you to a different browser or computer.
- **The command palette (⌘K/Ctrl+K)** is the fastest way to jump between pages
  without touching the sidebar.
- **Deactivate, don't delete**, when a member might come back — deletion is
  permanent and loses their history.
- **Test connection before Make focus** — the button is disabled until you do, on
  purpose, so a Lab never ends up with sync silently failing against an untested key.
- If something you expect to see isn't there (a member, a challenge, a report),
  double-check you're looking at the right **semester** — most pages filter by the
  currently selected or current semester.
