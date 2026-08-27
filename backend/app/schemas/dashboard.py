import uuid
from datetime import date, datetime

from pydantic import BaseModel


class StatusCounts(BaseModel):
    early: int = 0
    done: int = 0
    late: int = 0
    missing: int = 0


class PendingReport(BaseModel):
    id: uuid.UUID
    period_start: date
    period_end: date


class SemesterReportNudge(BaseModel):
    semester_id: uuid.UUID
    semester_name: str
    end_date: date


class LabDashboardOut(BaseModel):
    member_count: int
    active_member_count: int
    semester_count: int
    challenge_count: int
    current_semester_name: str | None
    status_counts: StatusCounts
    focus_platform_name: str | None
    focus_platform_configured: bool
    last_sync_run_at: datetime | None
    last_sync_status: str | None
    reminders_sent_this_week: int
    pending_report: PendingReport | None
    semester_report_nudge: SemesterReportNudge | None


class LabAttentionItem(BaseModel):
    id: uuid.UUID
    name: str
    reason: str  # "not_configured" | "sync_errors"


class SuperAdminDashboardOut(BaseModel):
    total_labs: int
    active_labs: int
    inactive_labs: int
    labs_needing_attention: list[LabAttentionItem]
