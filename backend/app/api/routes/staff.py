import hashlib
import secrets
from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.config import settings
from app.db import get_db
from app.models import Business, Membership, User
from app.security import hash_password, verify_password
from app.models import utc_now

router = APIRouter(prefix="/staff", tags=["staff management"])

ALLOWED_ROLES = {"admin", "manager", "employee", "hr"}

class StaffInviteCreate(BaseModel):
    phone: str = Field(min_length=8, max_length=24)
    role: str = Field(pattern=r"^(admin|manager|employee|hr)$")

class StaffAccept(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=128)

class StaffRoleUpdate(BaseModel):
    role: str = Field(pattern=r"^(admin|manager|employee|hr)$")

def get_membership(user: User, db: Session):
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership:
        raise HTTPException(status_code=403, detail="No business workspace is linked to this account.")
    return membership

def require_admin(user: User, db: Session):
    membership = get_membership(user, db)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only the owner or an administrator can manage staff.")
    return membership

@router.get("")
def list_staff(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = get_membership(current_user, db)
    rows = db.execute(select(Membership, User).join(User, User.id == Membership.user_id).where(Membership.business_id == membership.business_id).order_by(Membership.created_at)).all()
    return [{"id": m.id, "user_id": u.id, "full_name": u.full_name, "phone": u.phone, "role": m.role, "active": u.is_active, "joined_at": m.created_at} for m, u in rows]

@router.get("/invitations")
def list_invitations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import StaffInvitation
    membership = require_admin(current_user, db)
    rows = db.scalars(select(StaffInvitation).where(StaffInvitation.business_id == membership.business_id).order_by(StaffInvitation.created_at.desc())).all()
    return [{"id": x.id, "phone": x.phone, "role": x.role, "status": x.status, "expires_at": x.expires_at, "created_at": x.created_at} for x in rows]

@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(payload: StaffInviteCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import StaffInvitation
    membership = require_admin(current_user, db)
    if not payload.phone.strip().startswith("+"):
        raise HTTPException(status_code=422, detail="Enter the WhatsApp number in international format, starting with +, for example +27 82 123 4567.")
    phone = "".join(ch for ch in payload.phone if ch.isdigit())
    if len(phone) < 8 or len(phone) > 15:
        raise HTTPException(status_code=422, detail="Enter a valid WhatsApp number with country code, for example +27 82 123 4567.")
    pending = db.scalar(select(StaffInvitation).where(
        StaffInvitation.business_id == membership.business_id,
        StaffInvitation.phone == phone,
        StaffInvitation.status == "pending"
    ))
    if pending and pending.expires_at > utc_now():
        raise HTTPException(status_code=409, detail="A pending invitation already exists for this WhatsApp number.")
    raw_token = secrets.token_urlsafe(36)
    invite = StaffInvitation(
        id=str(uuid4()), business_id=membership.business_id,
        invited_by_user_id=current_user.id, email=None, phone=phone,
        role=payload.role,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        status="pending", expires_at=utc_now()+timedelta(hours=48), created_at=utc_now()
    )
    db.add(invite)
    db.commit()
    invite_url = f"{settings.frontend_base_url.rstrip('/')}/?staff_invite={raw_token}"
    return {"id": invite.id, "phone": phone, "role": invite.role, "status": invite.status, "expires_at": invite.expires_at, "invite_url": invite_url}

@router.post("/accept", status_code=status.HTTP_201_CREATED)
def accept_invitation(payload: StaffAccept, db: Session = Depends(get_db)):
    from app.models import StaffInvitation
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    invite = db.scalar(select(StaffInvitation).where(StaffInvitation.token_hash == token_hash, StaffInvitation.status == "pending"))
    if not invite or invite.expires_at <= utc_now():
        raise HTTPException(status_code=400, detail="This invitation is invalid, expired or already used.")
    phone = "".join(ch for ch in (invite.phone or "") if ch.isdigit())
    if len(phone) < 8:
        raise HTTPException(status_code=400, detail="This invitation does not contain a valid WhatsApp number.")
    candidates = db.scalars(select(User).where(User.phone.is_not(None))).all()
    matches = [candidate for candidate in candidates if "".join(ch for ch in (candidate.phone or "") if ch.isdigit()) == phone]
    if len(matches) > 1:
        raise HTTPException(status_code=409, detail="This WhatsApp number is linked to multiple accounts. Contact the business owner.")
    user = matches[0] if matches else None
    if user:
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=403, detail="A BusinessBrain account already uses this WhatsApp number. Enter that account password to accept the invitation.")
        if db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.business_id == invite.business_id)):
            raise HTTPException(status_code=409, detail="This account already belongs to the business.")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="This account is disabled. Contact the business owner.")
    else:
        # The database currently requires a unique email. This private, non-deliverable
        # alias preserves that constraint without asking staff for or sending email.
        account_alias = f"staff+{phone}@accounts.businessbrain.invalid"
        user = User(email=account_alias, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password), phone=phone)
        db.add(user)
        db.flush()
    if not user.phone:
        user.phone = phone
    db.add(Membership(user_id=user.id, business_id=invite.business_id, role=invite.role))
    invite.status = "accepted"
    invite.accepted_at = utc_now()
    db.commit()
    return {"accepted": True, "phone": phone, "message": "Your account has joined the business."}

@router.patch("/{membership_id}")
def update_staff_role(membership_id: str, payload: StaffRoleUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owner_membership = require_admin(current_user, db)
    target = db.scalar(select(Membership).where(Membership.id == membership_id, Membership.business_id == owner_membership.business_id))
    if not target:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    if target.role == "owner":
        raise HTTPException(status_code=403, detail="The business owner role cannot be changed here.")
    if target.user_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot change your own role.")
    target.role = payload.role
    db.commit()
    return {"id": target.id, "role": target.role}

@router.delete("/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_staff(membership_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    owner_membership = require_admin(current_user, db)
    target = db.scalar(select(Membership).where(Membership.id == membership_id, Membership.business_id == owner_membership.business_id))
    if not target:
        raise HTTPException(status_code=404, detail="Staff member not found.")
    if target.role == "owner" or target.user_id == current_user.id:
        raise HTTPException(status_code=403, detail="The business owner or your own account cannot be removed.")
    db.delete(target)
    db.commit()
    return None
