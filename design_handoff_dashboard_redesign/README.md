# Handoff: HSLab CTF Classroom — Dashboard Redesign

## Overview
A visual + UX redesign of the HSLab CTF Classroom frontend (Lab dashboard, Super Admin console, and login), moving from the current light-only, `max-w-5xl`, top-pill-nav layout to a wide, sidebar-driven, hacker-professional layout with a working light/dark theme toggle, a command palette, toast notifications, and consistent hover/transition polish.

## About the Design Files
The bundled file (`HSLab Redesign.dc.html`) is a **design reference built in HTML** — an interactive prototype showing the intended look, structure, and behavior (including working theme toggle, sidebar collapse, command palette, and toasts via inline JS/React). It is **not production code to copy directly**. The task is to **recreate this design inside the existing Next.js codebase** (`frontend/`, App Router, Tailwind v4, the hand-rolled `components/ui/` kit) using its established patterns — Tailwind utility classes, the existing CSS-variable theming approach in `app/globals.css`, and the existing component kit extended as needed — not by embedding the HTML/JS file as-is.

Open the file directly in a browser to click through every page, toggle theme, resize the window (responsive/sidebar-collapse behavior), and trigger toasts.

## Fidelity
**High-fidelity.** Colors (as OKLCH values, convertible to hex), typography, spacing, layout structure, and interaction behavior are final — implement pixel-close using the codebase's Tailwind + CSS-variable setup. Sample data (member names, challenge names, stats) is placeholder — wire to real data.

## Screens / Views

### 1. Sidebar shell (shared across all app pages)
- **Purpose**: primary navigation, replaces the old single top pill-nav bar.
- **Layout**: fixed-height flex row — `<aside>` sidebar (width 232px expanded / 68px collapsed to icon-rail / off-canvas drawer under 900px viewport width) + a flex-1 main column (topbar + scrollable content).
- **Sidebar structure top-to-bottom**:
  - Brand header (60px tall, border-bottom): 30×30px rounded-8px accent-colored logo mark with `>_` glyph, "HSLab CTF" title (14.5px/800) + `lab: hslab-core` mono subtitle (11px), hidden when collapsed.
  - Nav list: one row per page (Overview/Members/Semesters/Challenges/Progress/Platforms/Reports/Settings), each a 20×20px icon + label, 9px vertical / 10px horizontal padding, 9px border-radius, active state = `surfaceHover` background + accent-colored text and icon; inactive = transparent, hovers to `surfaceHover`.
  - Divider, then "Admin Console" nav row with a small `ROOT` mono badge pill (accent-tinted red/amber) — visually flags it as elevated/system scope.
  - Footer (border-top): 30×30px avatar-initials chip, name + role (hidden collapsed), sign-out icon button.
  - A small circular collapse toggle button pinned to the sidebar's right edge (desktop only) that flips expanded/icon-rail.
  - Under 900px viewport: sidebar becomes `position:fixed`, slides in from `left:-260px` to `left:0`, with a semi-transparent backdrop click-to-close; a hamburger button appears in the topbar to open it.
- **Icons**: simple 1.75px-stroke line icons (2×2 grid glyph for Overview, two-circle "people" glyph for Members, calendar, target/rings for Challenges, pulse line for Progress, two-linked-circles for Platforms, document-with-lines for Reports, circle+tick-marks for Settings, terminal-with-prompt for Admin Console) — all built from basic primitives (circle/rect/line/polyline), no photographic or illustrative icon set.

### 2. Topbar (shared)
- **Layout**: 60px tall, flex row, 20px horizontal padding, border-bottom, background = surface color.
- **Contents left→right**: hamburger (mobile only) · page title (15px/700) + a `SYSTEM SCOPE` mono badge when on the Console page · spacer · search/command-palette trigger pill (220px wide, shows "Search or jump to…" + `⌘K` hint, opens the command palette) · theme toggle icon button (sun ↔ moon) · notification bell icon button (red dot indicator, opens a 300px dropdown card listing 2 sample notifications) on click.

### 3. Overview page
- Header row: "Overview" title + "Fall 2026 semester · Root Me focus platform" subtitle, right-aligned "Sync now" button (spinning refresh icon while syncing, ~1.3s demo delay, ends with a success toast).
- 4-column responsive stat-card grid (`repeat(auto-fit, minmax(200px,1fr))`): Total members, Active semester, Completion rate, Last sync — each a card with muted label, large mono-font value (26px/700), small colored delta line. Cards lift 2px and their border tints accent color on hover.
- Two-column row below (1.4fr / 1fr): left card is a horizontal 4-segment stacked status bar (Early/Done/Late/Missing, 14px tall, rounded) with a color-keyed legend row below it; right column stacks two small alert-style cards — one with an amber/`statusLateText`-colored border for a "needs a nudge" reminder, one neutral card linking to Reports.

### 4. Members / Challenges pages
- Header row with title/subtitle + a solid accent "+ New member" / "+ New challenge" button (right-aligned).
- A single card containing a plain `<table>`: uppercase muted 11.5px column headers on a tinted header row, each body row separated by a 1px border, row background tints on hover. Members table shows a 26×26px mono-initials avatar chip + name, email (muted), role pill, Root Me ID (mono, muted), and a right-aligned "Edit" text action. Challenges table shows challenge name, week (mono "W6"), platform pill, deadline (muted), points (mono, bold, right-aligned).

### 5. Semesters page
- Header (no action button). Responsive card grid (`minmax(260px,1fr)`): each card shows semester name + status pill (Active/Closed), a date-range subtitle, and a full-width "Generate Report" button.

### 6. Progress page
- Header (no action). Single table: member, challenge, status pill (color per status: Early=blue, Done=green, Late=amber, Missing=red — same 4-state semantic system as the current app, restyled for the new palette), date (mono).

### 7. Platforms page
- Header (no action). Responsive 2-up card grid: each card has a 34×34px platform icon chip, platform name + connection-state text (green "Connected" / muted "Not configured"), a "FOCUS" accent pill when applicable, a muted "Last sync: …" line, and a "Sync now" button.

### 8. Reports page
- Header (no action). Vertical list of report rows, each a card: 36×36px file-icon chip, title + period (muted), a status pill (Draft = amber, Sent = green), and an "Export" button with a download icon (triggers a success toast).

### 9. Settings page
- Header (no action), content capped at 640px width. One card: "SMTP configuration" title, a 2-column Host/Port input grid, then a solid accent "Save" button and an outline "Send test email" button (both trigger toasts).

### 10. Admin Console page
- Reached via the sidebar's "Admin Console" row (kept in the same shell/theme system rather than a separate fixed-dark skin — see Design Tokens note below). Title "System Console" + "Whole-system scope — every Lab" subtitle.
- 3-column stat grid (Total Labs, Active Labs, Members system-wide).
- An amber-bordered "⚠ Labs needing attention" alert card.
- A Labs table: name, member count (muted), status pill (Active=green, Needs attention=amber, Suspended=neutral), created date (mono).

### 11. Login (preview toggle)
- Accessed via a small top-right "back to app preview" / sidebar sign-out affordance in the prototype (this is a prototype-only shortcut — implement as its own route in the real app, same as today's `/login` and `/console/login`).
- Centered 380px card on a full-bleed background with a faint animated grid-line texture. Logo mark + "HSLab CTF" wordmark. A 2-tab segmented control ("Lab sign in" / "Root access") switching a small mono hint line at the bottom between `/login` and `/console/login` semantics. Email + password inputs, solid accent "Sign in →" submit button.

## Interactions & Behavior
- **Theme toggle**: click the sun/moon icon in the topbar to flip the entire app between dark and light instantly (all colors are CSS custom properties / recomputed tokens — implement as a single class or `data-theme` attribute swap, not per-component logic). Persist the user's choice (e.g. `localStorage`).
- **Sidebar collapse**: desktop-only circular toggle button shrinks the sidebar to a 68px icon rail (labels/section-badges hidden, icons centered); state should persist across navigation (and ideally across sessions).
- **Responsive breakpoint**: at viewport width < 900px, the sidebar becomes an off-canvas drawer (slide-in from the left with a click-to-dismiss backdrop) opened via a hamburger button that appears in the topbar; the collapse toggle hides on this breakpoint.
- **Command palette**: opened via the search pill or a `⌘K`/`Ctrl+K` global shortcut. Centered modal, autofocused text input, live-filters the same list of pages shown in the sidebar, click or Enter navigates and closes it; `Escape` or backdrop click closes it.
- **Notifications**: bell icon opens a dropdown (not a page navigation) listing recent nudges/report-ready notices; a small red dot indicates unread state.
- **Toast notifications**: bottom-right stack, slide/scale in (`~250ms`, ease-out), auto-dismiss after ~3.6s, manually dismissible via an ✕ button, color-coded left border + icon per type (success=green, error=red, info=blue). Trigger on: sync complete, export, save settings, test email sent, add member/challenge placeholder actions.
- **Hover states**: nav rows and buttons get a background tint on hover; stat/platform/semester cards lift (`translateY(-2px)`) and their border tints to the accent color; table rows tint background on hover; all transitions ~120–200ms ease.
- **Animations**: page content fades/slides up ~250ms on page switch; toasts and the command palette use a subtle scale-in; the sync button's icon spins continuously while a sync is in progress.
- **Loading states**: not deeply modeled in the prototype (sample data is static) — the real implementation should add skeleton placeholders for tables/stat cards while data loads, replacing the current app's "renders null until data arrives" behavior.
- **Error states**: not modeled in the prototype — surface form/API errors as inline field errors plus an error-type toast, not to be silently swallowed.

## State Management
- `theme`: `'dark' | 'light'` — persisted, toggled from the topbar.
- `page` / current route: which nav item is active (drives sidebar highlight + topbar title + content).
- `sidebarCollapsed`: boolean, desktop only, persisted.
- `mobileNavOpen`: boolean, transient, closes on navigation or backdrop click.
- `commandOpen` + `commandQuery`: transient, for the command palette.
- `bellOpen`: transient, for the notifications dropdown.
- `toasts`: an array of `{id, type, message}`, each auto-expiring — implement as a small global toast context/hook so any page/action can push one.
- `syncing`: boolean per sync action, drives the spinning icon and button label.

## Design Tokens

All colors are defined as CSS custom properties recomputed per theme (values below in OKLCH; convert to hex/HSL as the codebase's Tailwind v4 `@theme inline` setup prefers).

**Dark theme**
```
--bg: oklch(0.16 0.014 250)       --surface: oklch(0.20 0.016 250)   --surface-hover: oklch(0.245 0.017 250)
--border: oklch(0.30 0.018 250)   --fg: oklch(0.94 0.01 250)         --muted: oklch(0.63 0.02 250)
--accent: oklch(0.78 0.17 152)    --accent-fg: oklch(0.14 0.02 152)  --accent-2: oklch(0.75 0.15 210)
--sidebar-bg: oklch(0.12 0.014 250)
```

**Light theme**
```
--bg: oklch(0.98 0.004 250)       --surface: oklch(1 0 0)            --surface-hover: oklch(0.965 0.006 250)
--border: oklch(0.90 0.006 250)   --fg: oklch(0.20 0.01 250)         --muted: oklch(0.50 0.015 250)
--accent: oklch(0.52 0.15 152)    --accent-fg: oklch(1 0 0)          --accent-2: oklch(0.50 0.14 210)
--sidebar-bg: oklch(1 0 0)
```

**Semantic status colors** (same 4-state system as today — early/done/late/missing — re-tuned per theme so they stay legible on both light and dark surfaces; see the `statusEarlyText/Bg`, `statusDoneText/Bg`, `statusLateText/Bg`, `statusMissingText/Bg` values in the prototype's logic for exact per-theme pairs). Keep this as one shared mapping (equivalent to today's `StatusBadge` component) rather than re-deriving colors per page.

**Typography**: Sans = **Manrope** (400/500/600/700/800) for all UI text, replacing Geist Sans. Mono = **JetBrains Mono** (400–700) for numeric/data values (stat counters, IDs, dates, points) and the `>_` brand mark, replacing Geist Mono — same "data gets mono" intent as today's `.font-data` utility, just a different mono family for a more overtly technical/terminal feel.

**Spacing/radius**: cards and inputs use 8–12px border-radius; page content padding 28px top / 32px sides; card gaps 14px; content max-width ~1560px (vs. today's `max-w-5xl`/`max-w-4xl`) — this is the "wider workspace" change.

**Note on the two-skins decision**: today's app deliberately gives the Super Admin console a fixed dark, no-accent identity that never changes with light/dark. This redesign **replaces** that with one global theme (light/dark toggle applies everywhere, including Console) and instead marks "system scope" with a small `ROOT`/`SYSTEM SCOPE` badge in the sidebar and topbar. Confirm this tradeoff is acceptable before implementing — it's a deliberate reversal of a documented PRD decision (README §14.1), not an oversight.

## Assets
No external image/icon assets — all icons are inline SVGs built from basic primitives (circle, rect, line, polyline, and two simple standard glyph paths for the bell and moon-crescent). Recreate them as an SVG icon component set (or swap in `lucide-react`, which is already an installed-but-unused dependency per the README) matching the shapes described under "Sidebar shell" above. Fonts load from Google Fonts (Manrope, JetBrains Mono) — swap for self-hosted `next/font` as the codebase already does for Geist.

## Files
- `HSLab Redesign.dc.html` — the full interactive design reference (open in any browser; no build step).
