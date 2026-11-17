import hashlib
import json
import logging
import os
import secrets
import smtplib
import urllib.error
import urllib.request
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

logger = logging.getLogger(__name__)
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
    subject = f"You have been invited to {business_name} on BusinessBrain"
    body = (
        f"You have been invited to join {business_name} on BusinessBrain.\n\n"
        f"Accept your invitation using this secure link (expires in 48 hours):\n{invite_url}\n\n"
        "If you were not expecting this invitation, you can ignore this email."
    )

    # Resend uses HTTPS, which is permitted on Render's Free web services.
    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    resend_from_email = os.getenv("RESEND_FROM_EMAIL", "").strip()
    if resend_api_key:
        if not resend_from_email:
            raise RuntimeError("RESEND_FROM_EMAIL is not configured")
        payload = json.dumps({"from": resend_from_email, "to": [email], "subject": subject, "text": body}).encode("utf-8")
        request = urllib.request.Request(
            "https://api.resend.com/emails", data=payload,
            headers={"Authorization": "Bearer " + resend_api_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status not in (200, 201):
                    raise RuntimeError("Resend returned HTTP " + str(response.status))
        except urllib.error.HTTPError as exc:
            logger.error("Resend email API rejected request (http_status=%s)", exc.code)
            raise RuntimeError("Resend email API returned HTTP " + str(exc.code)) from None
        return True

    # Google Apps Script Gmail relay uses HTTPS, so it works on Render Free.
    relay_url = os.getenv("GMAIL_APPS_SCRIPT_URL", "").strip()
    relay_secret = os.getenv("GMAIL_APPS_SCRIPT_SECRET", "").strip()
    if relay_url or relay_secret:
        if not relay_url or not relay_secret:
            raise RuntimeError("Gmail Apps Script relay configuration is incomplete")
        payload = json.dumps({
            "secret": relay_secret, "to": email, "subject": subject, "text": body
        }).encode("utf-8")
        request = urllib.request.Request(
            relay_url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                result = json.loads(response.read().decode("utf-8"))
                if response.status != 200 or not result.get("ok"):
                    raise RuntimeError("Gmail relay rejected the email request")
        except urllib.error.HTTPError as exc:
            logger.error("Gmail relay returned HTTP %s", exc.code)
            raise RuntimeError("Gmail relay returned HTTP " + str(exc.code)) from None
        return True

    # SMTP fallback for paid hosts that permit SMTP egress.
    if not settings.smtp_host or not settings.smtp_from_email:
        return False
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message.set_content(body)
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
        logger.exception(
            "Staff invitation email delivery failed (resend_key_configured=%s, resend_from_configured=%s, gmail_relay_configured=%s, smtp_host_configured=%s)",
            bool(os.getenv("RESEND_API_KEY")),
            bool(os.getenv("RESEND_FROM_EMAIL")),
            bool(os.getenv("GMAIL_APPS_SCRIPT_URL") and os.getenv("GMAIL_APPS_SCRIPT_SECRET")),
            bool(settings.smtp_host),
        )
        db.delete(invite)
        db.commit()
        raise HTTPException(status_code=502, detail="The invitation email could not be sent. Check the email service configuration and try again.")
    if not sent:
        return {"id": invite.id, "email": email, "role": invite.role, "status": invite.status, "expires_at": invite.expires_at, "email_sent": False, "message": "Invitation saved, but email delivery is not configured. Configure the Gmail Apps Script relay, Resend (HTTPS), or SMTP to send invitation links."}
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
