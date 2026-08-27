import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_roles
from app.models.member import Member, MemberRole
from app.models.report import Report
from app.models.tenant import Tenant
from app.schemas.report import ApproveReportRequest, ReportOut, ReportUpdate
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
    report.content = payload.content
    db.commit()
    db.refresh(report)
    return report


@router.post("/{report_id}/approve", response_model=ReportOut)
def approve_report(
    report_id: uuid.UUID,
    payload: ApproveReportRequest,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    report = _get_or_404(db, current.tenant_id, report_id)
    if report.status != "draft":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Report has already been sent")

    tenant = db.get(Tenant, current.tenant_id)
    report_label = "Semester Report" if report.type == "semester" else "Weekly Report"
    try:
        send_email(
            tenant,
            payload.to_address,
            subject=f"{tenant.name} — {report_label} ({report.period_start} to {report.period_end})",
            body=report.content or "",
        )
    except (EmailConfigError, EmailSendError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    report.status = "sent"
    report.sent_at = datetime.now(timezone.utc)
    report.approved_by = current.email
    db.commit()
    db.refresh(report)
    return report


@router.post("/generate-now", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def generate_now(db: Session = Depends(get_db), current: Member = Depends(require_roles(MemberRole.LAB_LEADER))):
    """Manual trigger for testing, mirroring /sync-now from Phase 2/3 —
    the real generation is the weekly Celery beat task."""
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
