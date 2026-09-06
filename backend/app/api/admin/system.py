from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_super_admin, get_db
from app.models.system_job_run_log import SystemJobRunLog
from app.schemas.automation import SystemJobRunOut

router = APIRouter(prefix="/admin/system", tags=["admin-system"], dependencies=[Depends(get_current_super_admin)])


@router.get("/job-runs", response_model=list[SystemJobRunOut])
def list_system_job_runs(db: Session = Depends(get_db)):
    """§8 — backup job history (the one job with no single-Tenant scope),
    Super-Admin-only."""
    return db.query(SystemJobRunLog).order_by(SystemJobRunLog.run_at.desc()).limit(100).all()
