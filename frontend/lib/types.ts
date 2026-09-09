export type MemberRole = "lab_leader" | "presenter" | "member";
export type ProgressStatus = "early" | "done" | "late" | "missing";
export type DetectedBy = "manual" | "sync";

export interface MemberMe {
  id: string;
  tenant_id: string;
  tenant_name: string;
  full_name: string;
  email: string;
  role: MemberRole;
}

export interface SuperAdminMe {
  id: string;
  email: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  created_at: string;
}

export interface LabAttentionItem {
  id: string;
  name: string;
  reason: "not_configured" | "sync_errors";
}

export interface SuperAdminDashboard {
  total_labs: number;
  active_labs: number;
  inactive_labs: number;
  labs_needing_attention: LabAttentionItem[];
}

export interface PlatformAccount {
  id: string;
  platform_id: string;
  external_username: string;
  external_user_id: string;
}

export interface Member {
  id: string;
  full_name: string;
  email: string;
  role: MemberRole;
  active: boolean;
  joined_at: string;
  platform_accounts: PlatformAccount[];
}

export interface Semester {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  report_trigger_date: string;
  report_automation_enabled: boolean;
  report_auto_send: boolean;
}

export type RepeatKind = "never" | "daily" | "weekly" | "biweekly" | "monthly" | "custom";

export interface RepeatSchedule {
  enabled: boolean;
  repeat: RepeatKind;
  time_of_day: string; // "HH:MM:SS"
  day_of_week: number | null; // 0=Monday .. 6=Sunday
  day_of_month: number | null;
  interval_days: number | null;
  last_fired_at?: string;
}

export interface AutomationSettings {
  reminder: RepeatSchedule;
  weekly_report: RepeatSchedule;
  weekly_report_auto_send: boolean;
}

export interface Platform {
  id: string;
  name: string;
  adapter_type: string;
  base_url: string | null;
  is_focus: boolean;
  is_active: boolean;
  has_credentials: boolean;
  credentials_verified_at: string | null;
}

export interface TestConnectionResult {
  ok: boolean;
  detail: string;
}

export interface ResolveUserResult {
  external_user_id: string | null;
  matched: boolean;
}

export interface ChallengeLookupResult {
  title: string | null;
  category: string | null;
  score: number | null;
  url: string | null;
}

export interface SyncNowResult {
  members_checked: number;
  updated: Array<{ member_id: string; challenge_id: string; status: ProgressStatus; completed_at: string }>;
  conflicts: Array<{ member_id: string; challenge_id: string; detected_completed_at: string }>;
  errors: string[];
}

export interface Challenge {
  id: string;
  semester_id: string;
  platform_id: string;
  week_number: number;
  title: string;
  category: string | null;
  difficulty: string | null;
  external_challenge_id: string | null;
  external_url: string | null;
  presenter_id: string | null;
  deadline_at: string;
  points: number | null;
}

export interface ChallengeSearchResult {
  external_challenge_id: string;
  title: string | null;
  category: string | null;
  language: string | null;
  url: string | null;
}

export interface Progress {
  id: string;
  member_id: string;
  challenge_id: string;
  status: ProgressStatus;
  completed_at: string | null;
  detected_by: DetectedBy;
  note: string | null;
}

export interface PendingReport {
  id: string;
  period_start: string;
  period_end: string;
}

export interface SemesterReportNudge {
  semester_id: string;
  semester_name: string;
  end_date: string;
}

export interface LabDashboard {
  member_count: number;
  active_member_count: number;
  semester_count: number;
  challenge_count: number;
  current_semester_name: string | null;
  status_counts: Record<ProgressStatus, number>;
  focus_platform_name: string | null;
  focus_platform_configured: boolean;
  last_sync_run_at: string | null;
  last_sync_status: string | null;
  reminders_sent_this_week: number;
  pending_report: PendingReport | null;
  semester_report_nudge: SemesterReportNudge | null;
}

export type ReportStatus = "draft" | "sent";

export interface Report {
  id: string;
  type: string;
  period_start: string;
  period_end: string;
  status: ReportStatus;
  content: string | null;
  generated_at: string | null;
  sent_at: string | null;
  approved_by: string | null;
  recipient_email: string | null;
}

export interface ReportSendAttempt {
  id: string;
  attempted_at: string;
  recipient_email: string;
  kind: "initial" | "retry" | "resend";
  status: "success" | "failed";
  error_detail: string | null;
  attempted_by_email: string;
}

export interface Notification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  target_type: string | null;
  target_id: string | null;
  read_at: string | null;
  dismissed_at: string | null;
  created_at: string;
}

export interface SyncRun {
  id: string;
  platform_id: string;
  platform_name: string;
  run_at: string;
  status: string;
  members_checked: number;
  updated_count: number;
  conflicts_count: number;
  errors: string | null;
}

export interface JobRun {
  id: string;
  job_type: string;
  run_at: string;
  status: string;
  detail: string | null;
}

export interface SystemJobRun {
  id: string;
  job_type: string;
  run_at: string;
  status: string;
  detail: string | null;
}

export interface AuditLogEntry {
  id: string;
  tenant_id: string | null;
  actor_type: string;
  actor_label: string;
  action: string;
  target_type: string | null;
  target_id: string | null;
  summary: string;
  created_at: string;
}

export interface DeletionPreview {
  tenant_name: string;
  member_count: number;
  semester_count: number;
  challenge_count: number;
  progress_count: number;
  report_count: number;
  platform_count: number;
}

export interface TenantDataJob {
  id: string;
  tenant_id: string;
  job_type: "export" | "backup" | "restore";
  status: string;
  format_version: string;
  requested_by_email: string;
  downloaded_at: string | null;
  error_detail: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface SMTPConfig {
  host: string | null;
  port: number | null;
  username: string | null;
  from_address: string | null;
  use_tls: boolean | null;
  has_credentials: boolean;
}

export interface TenantSettings {
  smtp: SMTPConfig;
  professor_email: string | null;
}

export interface PlatformFeedbackEntry {
  id: string;
  tenant_id: string;
  tenant_name: string;
  member_email: string;
  member_role: string;
  message: string;
  created_at: string;
}
