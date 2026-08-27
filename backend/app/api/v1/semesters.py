import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_member, get_db, require_roles
from app.models.member import Member, MemberRole
from app.models.semester import Semester
from app.models.tenant import Tenant
from app.schemas.report import ReportOut
from app.schemas.semester import SemesterCreate, SemesterOut, SemesterUpdate
from app.services.report_service import generate_semester_report_for_tenant

router = APIRouter(prefix="/semesters", tags=["semesters"])


def _query(db: Session, tenant_id: uuid.UUID):
    return db.query(Semester).filter(Semester.tenant_id == tenant_id)


@router.get("", response_model=list[SemesterOut])
def list_semesters(db: Session = Depends(get_db), current: Member = Depends(get_current_member)):
    return _query(db, current.tenant_id).order_by(Semester.start_date.desc()).all()


@router.post("", response_model=SemesterOut, status_code=status.HTTP_201_CREATED)
def create_semester(
    payload: SemesterCreate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    if payload.is_current:
        _query(db, current.tenant_id).update({Semester.is_current: False})
    semester = Semester(tenant_id=current.tenant_id, **payload.model_dump())
    db.add(semester)
    db.commit()
    db.refresh(semester)
    return semester


@router.patch("/{semester_id}", response_model=SemesterOut)
def update_semester(
    semester_id: uuid.UUID,
    payload: SemesterUpdate,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    semester = _query(db, current.tenant_id).filter(Semester.id == semester_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")

    data = payload.model_dump(exclude_unset=True)
    if data.get("is_current"):
        _query(db, current.tenant_id).update({Semester.is_current: False})
    for key, value in data.items():
        setattr(semester, key, value)

    db.commit()
    db.refresh(semester)
    return semester


@router.post("/{semester_id}/generate-report", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def generate_semester_report(
    semester_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    """PRD §6.11 — manual only, never automatic on end_date (closing out a
    semester is an administrative decision, per the Phase 5 plan)."""
    semester = _query(db, current.tenant_id).filter(Semester.id == semester_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")
    tenant = db.get(Tenant, current.tenant_id)
    return generate_semester_report_for_tenant(db, tenant, semester)


@router.delete("/{semester_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_semester(
    semester_id: uuid.UUID,
    db: Session = Depends(get_db),
    current: Member = Depends(require_roles(MemberRole.LAB_LEADER)),
):
    semester = _query(db, current.tenant_id).filter(Semester.id == semester_id).first()
    if not semester:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Semester not found")
    db.delete(semester)
    db.commit()
