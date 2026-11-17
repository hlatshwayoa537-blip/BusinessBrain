from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Business, BusinessReferral, BusinessReferralProfile, Membership, User
from app.schemas import AuthResponse, BusinessProfileUpdate, BusinessResponse, LoginRequest, RegisterRequest, UserResponse
from app.security import create_access_token, decode_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)

def build_auth_response(user: User, business: Business) -> AuthResponse:
    return AuthResponse(access_token=create_access_token(user.id), user=UserResponse.model_validate(user), business=business)

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
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
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
    return user

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/business/profile", response_model=BusinessResponse)
def get_business_profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> BusinessResponse:
    membership = db.scalar(select(Membership).where(Membership.user_id == current_user.id).order_by(Membership.created_at))
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
