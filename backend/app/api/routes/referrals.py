import secrets
import string

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import Business, BusinessReferral, BusinessReferralProfile, Membership, User

router = APIRouter(prefix="/referrals", tags=["business-referrals"])


def current_business(user: User, db: Session) -> tuple[Membership, Business]:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership:
        raise HTTPException(status_code=403, detail="A business workspace is required.")
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only business owners or administrators can manage referrals.")
    business = db.get(Business, membership.business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business workspace not found.")
    return membership, business


def create_referral_code(db: Session, business_id: str) -> BusinessReferralProfile:
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = "VEX" + "".join(secrets.choice(alphabet) for _ in range(8))
        profile = BusinessReferralProfile(business_id=business_id, referral_code=code)
        db.add(profile)
        try:
            db.flush()
            return profile
        except IntegrityError:
            db.rollback()
            # Another request may have created this business's code at the same time.
            existing = db.scalar(select(BusinessReferralProfile).where(BusinessReferralProfile.business_id == business_id))
            if existing:
                return existing
            # Otherwise retry only for the extremely unlikely random-code collision.
    raise HTTPException(status_code=503, detail="Could not generate a referral code. Please try again.")

@router.get("/me")
def my_referrals(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _, business = current_business(current_user, db)
    profile = db.scalar(select(BusinessReferralProfile).where(BusinessReferralProfile.business_id == business.id))
    if not profile:
        profile = create_referral_code(db, business.id)
        db.commit()
        db.refresh(profile)

    rows = db.execute(
        select(BusinessReferral, Business.name)
        .join(Business, Business.id == BusinessReferral.referred_business_id)
        .where(BusinessReferral.referrer_business_id == business.id)
        .order_by(BusinessReferral.created_at.desc())
    ).all()
    registered_count = len(rows)
    paid_count = sum(1 for referral, _ in rows if referral.status == "payment_verified")
    return {
        "referral_code": profile.referral_code,
        "registered_referrals": registered_count,
        "payment_verified_referrals": paid_count,
        "required_referrals": 5,
        "remaining_to_qualify": max(0, 5 - paid_count),
        "discount_eligible": paid_count >= 5,
        "discount_status": "eligible" if paid_count >= 5 else "not_yet_eligible",
        "referrals": [
            {
                "id": referral.id,
                "business_name": name,
                "status": referral.status,
                "created_at": referral.created_at.isoformat(),
            }
            for referral, name in rows
        ],
        "reward_terms": {
            "standard_price_per_pos_month": 499,
            "qualified_price_per_pos_month": 399,
            "qualification": "Five directly referred businesses with verified subscription payments.",
            "payment_verification_available": False,
            "note": "Referral registrations are tracked, but VEXION does not yet have a subscription payment integration. No referral is counted as payment-verified and no R399 discount is activated automatically.",
        },
    }
