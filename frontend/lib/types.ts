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
}

export interface Platform {
  id: string;
  name: string;
  adapter_type: string;
  base_url: string | null;
  is_focus: boolean;
  is_active: boolean;
  has_credentials: boolean;
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
  presenter_id: string | null;
  deadline_at: string;
  points: number | null;
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
