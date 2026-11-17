import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.core.config import settings
from app.db import get_db
from app.models import Business, Membership, User
from app.security import hash_password
from app.models import utc_now

router = APIRouter(prefix="/staff", tags=["staff management"])
ALLOWED_ROLES = {"admin", "manager", "employee", "hr"}

class StaffInviteCreate(BaseModel):
    email: EmailStr
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

def send_invite_email(email: str, business_name: str, invite_url: str):
    if not settings.smtp_host or not settings.smtp_from_email:
        return False
    message = EmailMessage()
    message["Subject"] = f"You have been invited to {business_name} on BusinessBrain"
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message.set_content(f"You have been invited to join {business_name} on BusinessBrain.\n\nAccept your invitation using this secure link (expires in 48 hours):\n{invite_url}\n\nIf you were not expecting this invitation, you can ignore this email.")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
    return True

@router.get("")
def list_staff(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = get_membership(current_user, db)
    rows = db.execute(select(Membership, User).join(User, User.id == Membership.user_id).where(Membership.business_id == membership.business_id).order_by(Membership.created_at)).all()
    return [{"id": m.id, "user_id": u.id, "full_name": u.full_name, "email": u.email, "role": m.role, "active": u.is_active, "joined_at": m.created_at} for m, u in rows]

@router.get("/invitations")
def list_invitations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import StaffInvitation
    membership = require_admin(current_user, db)
    rows = db.scalars(select(StaffInvitation).where(StaffInvitation.business_id == membership.business_id).order_by(StaffInvitation.created_at.desc())).all()
    return [{"id": x.id, "email": x.email, "role": x.role, "status": x.status, "expires_at": x.expires_at, "created_at": x.created_at} for x in rows]

@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def create_invitation(payload: StaffInviteCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models import StaffInvitation
    membership = require_admin(current_user, db)
    email = str(payload.email).lower().strip()
    business = db.get(Business, membership.business_id)
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user and db.scalar(select(Membership).where(Membership.user_id == existing_user.id, Membership.business_id == membership.business_id)):
        raise HTTPException(status_code=409, detail="This person is already a member of your business.")
    pending = db.scalar(select(StaffInvitation).where(StaffInvitation.business_id == membership.business_id, StaffInvitation.email == email, StaffInvitation.status == "pending"))
    if pending and pending.expires_at > utc_now():
        raise HTTPException(status_code=409, detail="A pending invitation already exists for this email address.")
    raw_token = secrets.token_urlsafe(36)
    invite = StaffInvitation(id=str(uuid4()), business_id=membership.business_id, invited_by_user_id=current_user.id, email=email, role=payload.role, token_hash=hashlib.sha256(raw_token.encode()).hexdigest(), status="pending", expires_at=utc_now()+timedelta(hours=48), created_at=utc_now())
    db.add(invite)
    db.commit()
    base_url = settings.frontend_base_url.rstrip("/")
    invite_url = f"{base_url}/?staff_invite={raw_token}"
    try:
        sent = send_invite_email(email, business.name, invite_url)
    except Exception:
        db.delete(invite)
        db.commit()
        raise HTTPException(status_code=502, detail="The invitation email could not be sent. Check the email service configuration and try again.")
    if not sent:
        return {"id": invite.id, "email": email, "role": invite.role, "status": invite.status, "expires_at": invite.expires_at, "email_sent": False, "message": "Invitation saved, but email delivery is not configured. Configure SMTP to send invitation links."}
    return {"id": invite.id, "email": email, "role": invite.role, "status": invite.status, "expires_at": invite.expires_at, "email_sent": True}

@router.post("/accept", status_code=status.HTTP_201_CREATED)
def accept_invitation(payload: StaffAccept, db: Session = Depends(get_db)):
    from app.models import StaffInvitation
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    invite = db.scalar(select(StaffInvitation).where(StaffInvitation.token_hash == token_hash, StaffInvitation.status == "pending"))
    if not invite or invite.expires_at <= utc_now():
        raise HTTPException(status_code=400, detail="This invitation is invalid, expired or already used.")
    email = invite.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user:
        if db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.business_id == invite.business_id)):
            raise HTTPException(status_code=409, detail="This account already belongs to the business.")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="This account is disabled. Contact the business owner.")
    else:
        user = User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password))
        db.add(user)
        db.flush()
    db.add(Membership(user_id=user.id, business_id=invite.business_id, role=invite.role))
    invite.status = "accepted"
    invite.accepted_at = utc_now()
    db.commit()
    return {"accepted": True, "message": "Your account has joined the business. You can now sign in using your email and password."}

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
