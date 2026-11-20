import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.core.config import settings
from app.api.business_context import get_business_membership
from app.models import Business, BusinessReferral, BusinessReferralProfile, Membership, User, UserActionToken
from app.schemas import AuthResponse, BusinessProfileUpdate, BusinessResponse, LoginRequest, PasswordResetConfirm, PasswordResetRequest, RegisterRequest, UserResponse
from app.security import create_access_token, decode_access_token, decode_access_token_business_id, decode_access_token_version, hash_password, verify_password
from app.services.email import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)

def build_auth_response(user: User, business: Business) -> AuthResponse:
    return AuthResponse(access_token=create_access_token(user.id, business.id, user.token_version), user=UserResponse.model_validate(user), business=business)

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    user = User(email=email, full_name=payload.full_name.strip(), password_hash=hash_password(payload.password))
    referrer_profile = None
    if payload.referral_code:
        code = payload.referral_code.strip().upper()
        referrer_profile = db.scalar(select(BusinessReferralProfile).where(BusinessReferralProfile.referral_code == code))
        if not referrer_profile:
            raise HTTPException(status_code=400, detail="That VEXION referral code is not valid.")
    business = Business(name=payload.business_name.strip(), industry=payload.industry.strip(), country=payload.country.upper(), profile_image_data_url=payload.profile_image_data_url)
    db.add_all([user, business])
    db.flush()
    db.add(Membership(user_id=user.id, business_id=business.id, role="owner"))
    if referrer_profile:
        db.add(BusinessReferral(referrer_business_id=referrer_profile.business_id, referred_business_id=business.id, status="pending_payment"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from None
    db.refresh(user)
    db.refresh(business)
    return build_auth_response(user, business)

@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    identifier = (payload.identifier or (str(payload.email) if payload.email else "")).strip()
    if not identifier:
        raise HTTPException(status_code=422, detail="Enter your email address or WhatsApp number.")
    if "@" in identifier:
        user = db.scalar(select(User).where(User.email == identifier.lower()))
    else:
        phone_digits = "".join(ch for ch in identifier if ch.isdigit())
        if len(phone_digits) < 8 or len(phone_digits) > 15:
            raise HTTPException(status_code=401, detail="Incorrect WhatsApp number or password.")
        candidates = db.scalars(select(User).where(User.phone.is_not(None))).all()
        matches = [candidate for candidate in candidates if "".join(ch for ch in (candidate.phone or "") if ch.isdigit()) == phone_digits]
        user = matches[0] if len(matches) == 1 else None
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email/WhatsApp number or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled.")
    membership = get_business_membership(user, db)
    if not membership:
        raise HTTPException(status_code=403, detail="No business workspace is linked to this account.")
    business = db.get(Business, membership.business_id)
    if not business:
        raise HTTPException(status_code=403, detail="Business workspace is unavailable.")
    return build_auth_response(user, business)

def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required.", headers={"WWW-Authenticate": "Bearer"})
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account is unavailable.")
    if decode_access_token_version(credentials.credentials) != user.token_version:
        raise HTTPException(status_code=401, detail="This access token has been revoked. Please sign in again.")
    user.active_business_id = decode_access_token_business_id(credentials.credentials)
    return user


@router.get("/businesses")
def list_business_workspaces(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        select(Membership, Business)
        .join(Business, Business.id == Membership.business_id)
        .where(Membership.user_id == current_user.id)
        .order_by(Membership.created_at, Membership.id)
    ).all()
    return [
        {"id": business.id, "name": business.name, "industry": business.industry, "country": business.country,
         "role": membership.role, "active": business.id == getattr(current_user, "active_business_id", None)}
        for membership, business in rows
    ]


@router.post("/business/switch")
def switch_business_workspace(payload: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    business_id = payload.get("business_id")
    if not isinstance(business_id, str) or len(business_id) != 36:
        raise HTTPException(status_code=422, detail="A valid business workspace ID is required.")
    membership = db.scalar(select(Membership).where(
        Membership.user_id == current_user.id, Membership.business_id == business_id
    ))
    if not membership:
        raise HTTPException(status_code=403, detail="You do not have access to this business workspace.")
    business = db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business workspace not found.")
    return {"access_token": create_access_token(current_user.id, business.id, current_user.token_version), "token_type": "bearer",
            "business": BusinessResponse.model_validate(business),
            "user": UserResponse.model_validate(current_user)}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/business/profile", response_model=BusinessResponse)
def get_business_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> BusinessResponse:
    membership = get_business_membership(current_user, db)
    if not membership:
        raise HTTPException(status_code=404, detail="Business workspace not found.")
    business = db.get(Business, membership.business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business workspace not found.")
    return BusinessResponse.model_validate(business)

@router.patch("/business/profile", response_model=BusinessResponse)
def update_business_profile(payload: BusinessProfileUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> BusinessResponse:
    membership = db.scalar(select(Membership).where(Membership.user_id == current_user.id).order_by(Membership.created_at))
    if not membership:
        raise HTTPException(status_code=404, detail="Business workspace not found.")
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only business owners or administrators can edit this profile.")
    business = db.get(Business, membership.business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business workspace not found.")
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("country") is not None:
        changes["country"] = changes["country"].upper()
    if changes.get("contact_email") is not None:
        changes["contact_email"] = str(changes["contact_email"]).lower()
    for field, value in changes.items():
        setattr(business, field, value)
    db.commit()
    db.refresh(business)
    return BusinessResponse.model_validate(business)


@router.post("/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(payload: PasswordResetRequest, db: Session = Depends(get_db)) -> dict:
    # Check mail configuration before looking up the account so this response
    # does not reveal whether a particular email address is registered.
    if not settings.smtp_host or not settings.smtp_from_email:
        raise HTTPException(status_code=503, detail="Password recovery email is not configured.")
    email = str(payload.email).strip().lower()
    user = db.scalar(select(User).where(User.email == email))
    now = datetime.now(timezone.utc)
    if user and user.is_active:
        recent = db.scalar(select(UserActionToken).where(
            UserActionToken.user_id == user.id,
            UserActionToken.purpose == "password_reset",
            UserActionToken.used_at.is_(None),
            UserActionToken.created_at >= now - timedelta(seconds=60),
        ))
        if not recent:
            db.execute(update(UserActionToken).where(
                UserActionToken.user_id == user.id,
                UserActionToken.purpose == "password_reset",
                UserActionToken.used_at.is_(None),
            ).values(used_at=now))
            raw_token = secrets.token_urlsafe(32)
            token_record = UserActionToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
                purpose="password_reset",
                expires_at=now + timedelta(minutes=30),
            )
            db.add(token_record)
            db.commit()
            reset_url = f"{settings.frontend_base_url.rstrip('/')}/?reset_token={quote(raw_token)}"
            try:
                send_password_reset_email(user.email, user.full_name, reset_url)
            except Exception:
                token_record.used_at = now
                db.commit()
                logger.exception("Password reset email delivery failed for user_id=%s", user.id)
    return {"message": "If an active account exists for that email, password reset instructions will be sent."}


@router.post("/password-reset/confirm")
def confirm_password_reset(payload: PasswordResetConfirm, db: Session = Depends(get_db)) -> dict:
    now = datetime.now(timezone.utc)
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    token_record = db.scalar(select(UserActionToken).where(
        UserActionToken.token_hash == token_hash,
        UserActionToken.purpose == "password_reset",
        UserActionToken.used_at.is_(None),
        UserActionToken.expires_at > now,
    ))
    if not token_record:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or has expired.")
    user = db.get(User, token_record.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or has expired.")
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    db.execute(update(UserActionToken).where(
        UserActionToken.user_id == user.id,
        UserActionToken.purpose == "password_reset",
        UserActionToken.used_at.is_(None),
    ).values(used_at=now))
    db.commit()
    return {"message": "Password reset successfully. Sign in with your new password."}
