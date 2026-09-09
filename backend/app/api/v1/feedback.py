from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_member, get_db
from app.models.feedback import PlatformFeedback
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.feedback import FeedbackCreate

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    current: Member = Depends(get_current_member),
):
    """Available to every role (lab_leader/presenter/member) — a low-
    friction channel for "does this platform need improving?" feedback,
    reviewed by the Super Admin from the Console (GET /admin/feedback).
    No listing endpoint on this side: it's submit-only, not a two-way
    thread."""
    tenant = db.get(Tenant, current.tenant_id)
    db.add(
        PlatformFeedback(
            tenant_id=current.tenant_id,
            tenant_name=tenant.name,
            member_id=current.id,
            member_email=current.email,
            member_role=current.role.value,
            message=payload.message,
        )
    )
    db.commit()
    return {"ok": True}
