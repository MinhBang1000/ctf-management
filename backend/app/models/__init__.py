# Importing this package registers every model on Base.metadata — needed
# by Alembic autogenerate. Individual modules only depend on app.db.base,
# never on this package, to avoid a circular import.
from app.models.tenant import Tenant
from app.models.super_admin import SuperAdmin
from app.models.member import Member, MemberRole
from app.models.platform import Platform
from app.models.member_platform_account import MemberPlatformAccount
from app.models.semester import Semester
from app.models.challenge import Challenge
from app.models.progress import Progress, ProgressStatus, DetectedBy
from app.models.reminder_log import ReminderLog
from app.models.report import Report
from app.models.sync_log import SyncLog
from app.models.job_run_log import JobRunLog
from app.models.audit_log import AuditLog
from app.models.password_reset_token import PasswordResetToken
from app.models.notification import Notification
from app.models.report_send_attempt import ReportSendAttempt
from app.models.tenant_data_job import TenantDataJob
from app.models.system_job_run_log import SystemJobRunLog
from app.models.feedback import PlatformFeedback
from app.models.automation_settings import TenantAutomationSettings

__all__ = [
    "Tenant",
    "SuperAdmin",
    "Member",
    "MemberRole",
    "Platform",
    "MemberPlatformAccount",
    "Semester",
    "Challenge",
    "Progress",
    "ProgressStatus",
    "DetectedBy",
    "ReminderLog",
    "Report",
    "SyncLog",
    "JobRunLog",
    "AuditLog",
    "PasswordResetToken",
    "Notification",
    "ReportSendAttempt",
    "TenantDataJob",
    "SystemJobRunLog",
    "PlatformFeedback",
    "TenantAutomationSettings",
]
