import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.member import Member, MemberRole
from app.models.report import Report
from app.models.report_send_attempt import ReportSendAttempt
from app.models.tenant import Tenant
from app.schemas.report import (
    ApproveReportRequest,
    ReportOut,
    ReportSendAttemptOut,
    ReportUpdate,
    ResendReportRequest,
)
from app.services.audit_service import record_audit
from app.services.email_service import EmailConfigError, EmailSendError, send_email
from app.services.export_service import (
    ExportNotAvailableError,
    render_semester_report_excel,
    render_semester_report_pdf,
)
from app.services.report_service import generate_weekly_report_for_tenant

router = APIRouter(prefix="/reports", tags=["reports"])


def _query(db: Session, tenant_id: uuid.UUID):
    return db.query(Report).filter(Report.tenant_id == tenant_id)


def _get_or_404(db: Session, tenant_id: uuid.UUID, report_id: uuid.UUID) -> Report:
    report = _query(db, tenant_id).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


def _send_and_record(
    db: Session, report: Report, tenant: Tenant, to_address: str, current: Member, kind: str
) -> ReportSendAttempt:
    """§10/§11 — every attempt (initial, retry, or resend) is recorded
    before the caller decides what to do with the Report's own status,
    so "sent successfully" vs "failed" is always a real queryable history
    even if the HTTP call raises."""
    report_label = "Semester Report" if report.type == "semester" else "Weekly Report"
    try:
        send_email(
            tenant,
            to_address,
            subject=f"{tenant.name} — {report_label} ({report.period_start} to {report.period_end})",
            body=report.content or "",
        )
    except (EmailConfigError, EmailSendError) as exc:
        attempt = ReportSendAttempt(
            report_id=report.id,
            recipient_email=to_address,
            kind=kind,
            status="failed",
            error_detail=str(exc),
            attempted_by_email=current.email,
        )
        db.add(attempt)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    attempt = ReportSendAttempt(
        report_id=report.id,
        recipient_email=to_address,
        kind=kind,
        status="success",
        attempted_by_email=current.email,
    )
    db.add(attempt)
    report.recipient_email = to_address
    return attempt


@router.get("", response_model=list[ReportOut])
def list_reports(db: Session = Depends(get_db), current: Member = Depends(require_roles(MemberRole.LAB_LEADER))):
    return _query(db, current.tenant_id).order_by(Report.generated_at.desc()).all()


@router.get("/{report_id}", response_model=ReportOut)
def get_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    return _get_or_404(db, current.tenant_id, report_id)


@router.get("/{report_id}/send-attempts", response_model=list[ReportSendAttemptOut])
def list_send_attempts(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """§11 — the full history behind a Report's current status: every
    initial/retry/resend attempt, successful or failed."""
    _get_or_404(db, current.tenant_id, report_id)  # 404s before leaking attempt existence
    return (
        db.query(ReportSendAttempt)
        .filter(ReportSendAttempt.report_id == report_id)
        .order_by(ReportSendAttempt.attempted_at.desc())
        .all()
    )


@router.patch("/{report_id}", response_model=ReportOut)
def update_report(
    report_id: uuid.UUID,
    payload: ReportUpdate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    report = _get_or_404(db, current.tenant_id, report_id)
    if report.status != "draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft reports can be edited")
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="report.edited",
        summary=f"Edited draft {report.type} report ({report.period_start} to {report.period_end})",
        target_type="report",
        target_id=report.id,
    )
    report.content = payload.content
    db.commit()
    db.refresh(report)
    return report


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Conservative default (no explicit spec for this): a report that has
    already been sent to the professor is never deletable — it's a real
    record of something that actually happened (and ReportSendAttempt rows
    FK to it), so deleting it would falsify the Lab's own history. Only a
    still-draft report (never sent) can be removed."""
    report = _get_or_404(db, current.tenant_id, report_id)
    if report.status == "sent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete a report that has already been sent")
    record_audit(
        db, tenant_id=current.tenant_id, actor=current, action="report.deleted",
        summary=f"Deleted draft {report.type} report ({report.period_start} to {report.period_end})",
        target_type="report", target_id=report.id,
    )
    db.delete(report)
    db.commit()


@router.post("/{report_id}/approve", response_model=ReportOut)
def approve_report(
    report_id: uuid.UUID,
    payload: ApproveReportRequest,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """Covers both the very first send and a retry after a prior failed
    attempt — either way the Report is still "draft" (only a *successful*
    send flips it to "sent"), so this stays the same endpoint for both;
    see list_send_attempts for which one actually happened."""
    report = _get_or_404(db, current.tenant_id, report_id)
    if report.status != "draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report has already been sent")

    tenant = db.get(Tenant, current.tenant_id)
    had_prior_attempt = db.query(ReportSendAttempt).filter(ReportSendAttempt.report_id == report.id).first() is not None
    _send_and_record(db, report, tenant, payload.to_address, current, kind="retry" if had_prior_attempt else "initial")

    report.status = "sent"
    report.sent_at = datetime.now(timezone.utc)
    report.approved_by = current.email
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="report.retried" if had_prior_attempt else "report.sent",
        summary=f"{'Retried and sent' if had_prior_attempt else 'Sent'} {report.type} report "
        f"({report.period_start} to {report.period_end}) to {payload.to_address}",
        target_type="report",
        target_id=report.id,
    )
    db.commit()
    db.refresh(report)
    return report


@router.post("/{report_id}/resend", response_model=ReportOut)
def resend_report(
    report_id: uuid.UUID,
    payload: ResendReportRequest,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """§11 — deliberately re-sending an ALREADY successfully-sent report.
    Distinct from approve_report's retry-after-failure path: this never
    changes the Report's original status/sent_at/approved_by (those
    describe the original send), only recipient_email (the latest
    known-good delivery target) and the send-attempts history."""
    report = _get_or_404(db, current.tenant_id, report_id)
    if report.status != "sent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only an already-sent report can be resent")
    if not payload.confirm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Resending requires explicit confirmation")

    tenant = db.get(Tenant, current.tenant_id)
    _send_and_record(db, report, tenant, payload.to_address, current, kind="resend")
    record_audit(
        db,
        tenant_id=current.tenant_id,
        actor=current,
        action="report.resent",
        summary=f"Resent {report.type} report ({report.period_start} to {report.period_end}) to {payload.to_address}",
        target_type="report",
        target_id=report.id,
    )
    db.commit()
    db.refresh(report)
    return report


@router.post("/generate-now", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def generate_now(db: Session = Depends(get_db), current: Member = Depends(require_roles(MemberRole.LAB_LEADER))):
    """Manual trigger for testing, mirroring /sync-now from Phase 2/3 —
    the real generation is the weekly Celery beat task. Idempotent (§9):
    repeated calls within the same period update the existing draft."""
    tenant = db.get(Tenant, current.tenant_id)
    report = generate_weekly_report_for_tenant(db, tenant)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Create a Semester before generating a report"
        )
    return report


@router.get("/{report_id}/export.pdf")
def export_report_pdf(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    report = _get_or_404(db, current.tenant_id, report_id)
    try:
        pdf_bytes = render_semester_report_pdf(report)
    except ExportNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    filename = f"semester-report-{report.period_start}-{report.period_end}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{report_id}/export.xlsx")
def export_report_excel(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    report = _get_or_404(db, current.tenant_id, report_id)
    try:
        xlsx_bytes = render_semester_report_excel(report)
    except ExportNotAvailableError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    filename = f"semester-report-{report.period_start}-{report.period_end}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
