from sqlalchemy.orm import Session

from app.models.member import Member, MemberRole


class LastLabLeaderError(Exception):
    """§14 — the requested change would leave the Lab with zero active
    Lab Leaders."""


def assert_not_last_lab_leader(db: Session, member: Member) -> None:
    """Call this BEFORE deactivating, deleting, or demoting `member`, in
    the same transaction as that change.

    Locks every active Lab Leader row in this tenant (SELECT ... FOR
    UPDATE) before counting, so two concurrent requests trying to remove
    the last two Leaders at once can't both pass the check before either
    commits — the second has to wait for the first's transaction to
    finish, by which point the count it sees is accurate (§14: "Enforce
    the rule transactionally so concurrent requests cannot bypass it").
    """
    if member.role != MemberRole.LAB_LEADER or not member.active:
        return  # not currently counted as an active Leader anyway

    active_leaders = (
        db.query(Member)
        .filter(Member.tenant_id == member.tenant_id, Member.role == MemberRole.LAB_LEADER, Member.active.is_(True))
        .with_for_update()
        .all()
    )
    remaining = [m for m in active_leaders if m.id != member.id]
    if not remaining:
        raise LastLabLeaderError(
            "This is the Lab's last active Lab Leader — promote another Member to Lab Leader first."
        )
