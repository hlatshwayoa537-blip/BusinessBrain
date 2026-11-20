from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Membership, User


def get_business_membership(user: User, db: Session) -> Membership:
    """Resolve the user's selected workspace, falling back to their first membership for legacy tokens."""
    selected_business_id = getattr(user, "active_business_id", None)
    statement = select(Membership).where(Membership.user_id == user.id)
    if selected_business_id:
        statement = statement.where(Membership.business_id == selected_business_id)
    else:
        statement = statement.order_by(Membership.created_at, Membership.id)
    membership = db.scalar(statement)
    if not membership:
        raise HTTPException(status_code=403, detail="You do not have access to this business workspace.")
    return membership
