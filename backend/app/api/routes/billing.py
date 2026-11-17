from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import BusinessReferral, BusinessSubscription, BusinessPOSTerminal, Membership, POSConnection, User

router = APIRouter(prefix="/billing", tags=["billing"])
STANDARD_PRICE = Decimal("499.00")
REFERRAL_PRICE = Decimal("399.00")


def current_business(user: User, db: Session) -> tuple[Membership, str]:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership:
        raise HTTPException(status_code=403, detail="A business workspace is required.")
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only business owners or administrators can manage billing.")
    return membership, membership.business_id


class TerminalCreate(BaseModel):
    external_terminal_id: str = Field(min_length=1, max_length=180)
    display_name: str = Field(min_length=2, max_length=160)
    branch_name: str | None = Field(default=None, max_length=160)
    connection_id: str | None = Field(default=None, min_length=36, max_length=36)


class TerminalStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|inactive)$")


def terminal_payload(row: BusinessPOSTerminal) -> dict:
    return {
        "id": row.id,
        "external_terminal_id": row.external_terminal_id,
        "display_name": row.display_name,
        "branch_name": row.branch_name,
        "connection_id": row.connection_id,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
    }


@router.get("/me")
def billing_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _, business_id = current_business(user, db)
    terminals = db.scalars(
        select(BusinessPOSTerminal).where(BusinessPOSTerminal.business_id == business_id).order_by(BusinessPOSTerminal.created_at.desc())
    ).all()
    active_count = sum(1 for terminal in terminals if terminal.status == "active")
    paid_referrals = db.scalar(
        select(func.count(BusinessReferral.id)).where(
            BusinessReferral.referrer_business_id == business_id,
            BusinessReferral.status == "payment_verified",
        )
    ) or 0
    discount_eligible = paid_referrals >= 5
    unit_price = REFERRAL_PRICE if discount_eligible else STANDARD_PRICE
    subscription = db.scalar(select(BusinessSubscription).where(BusinessSubscription.business_id == business_id))
    if subscription:
        subscription.active_pos_count = active_count
        subscription.referral_discount_applied = discount_eligible
        subscription.updated_at = datetime.now(timezone.utc)
        db.commit()
    return {
        "currency": "ZAR",
        "subscription_status": subscription.status if subscription else "not_started",
        "payment_status": "not_configured",
        "payment_provider": subscription.payment_provider if subscription else None,
        "active_pos_terminals": active_count,
        "inactive_pos_terminals": len(terminals) - active_count,
        "verified_direct_referrals": paid_referrals,
        "referral_discount_eligible": discount_eligible,
        "unit_price_per_pos_month": str(unit_price),
        "estimated_monthly_total": str((unit_price * active_count).quantize(Decimal("0.01"))),
        "standard_unit_price": str(STANDARD_PRICE),
        "referral_unit_price": str(REFERRAL_PRICE),
        "terminals": [terminal_payload(row) for row in terminals],
        "notice": "Billing is not yet connected to a payment provider. This is a pricing estimate only; no payment has been collected and the subscription is not active.",
    }


@router.post("/terminals", status_code=status.HTTP_201_CREATED)
def register_terminal(payload: TerminalCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _, business_id = current_business(user, db)
    external_id = payload.external_terminal_id.strip()
    if payload.connection_id:
        connection = db.scalar(select(POSConnection).where(
            POSConnection.id == payload.connection_id,
            POSConnection.business_id == business_id,
        ))
        if not connection:
            raise HTTPException(status_code=404, detail="POS connection not found for this business.")
    row = BusinessPOSTerminal(
        business_id=business_id,
        connection_id=payload.connection_id,
        external_terminal_id=external_id,
        display_name=payload.display_name.strip(),
        branch_name=payload.branch_name.strip() if payload.branch_name else None,
        status="active",
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That POS terminal is already registered for this business.") from None
    db.refresh(row)
    return terminal_payload(row)


@router.patch("/terminals/{terminal_id}")
def update_terminal(terminal_id: str, payload: TerminalStatusUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _, business_id = current_business(user, db)
    row = db.scalar(select(BusinessPOSTerminal).where(
        BusinessPOSTerminal.id == terminal_id,
        BusinessPOSTerminal.business_id == business_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="POS terminal not found.")
    row.status = payload.status
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return terminal_payload(row)
