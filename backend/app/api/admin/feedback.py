from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_super_admin, get_db
from app.db.session import bind_super_admin_context
from app.models.feedback import PlatformFeedback
from app.schemas.feedback import FeedbackOut

router = APIRouter(prefix="/admin/feedback", tags=["admin-feedback"], dependencies=[Depends(get_current_super_admin)])


@router.get("", response_model=list[FeedbackOut])
def list_feedback(
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Every Lab's platform feedback, newest first — cross-tenant by
    design (this isn't Lab data, it's feedback about the platform
    itself)."""
    bind_super_admin_context(db)
    return (
        db.query(PlatformFeedback)
        .order_by(PlatformFeedback.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
