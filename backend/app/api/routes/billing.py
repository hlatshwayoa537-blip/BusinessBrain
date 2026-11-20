from datetime import datetime, timezone
from decimal import Decimal
import ipaddress
import uuid
from urllib.parse import parse_qsl

import httpx
from fastapi import Request
from decimal import Decimal
import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.business_context import get_business_membership
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import BusinessReferral, BusinessSubscription, BusinessPOSTerminal, Membership, POSConnection, POSTransaction, User, PayFastPayment
from app.core.config import settings
from app.services.payfast import build_subscription_checkout, verify_itn_signature

router = APIRouter(prefix="/billing", tags=["billing"])
STANDARD_PRICE = Decimal("499.00")
REFERRAL_PRICE = Decimal("399.00")


def current_business(user: User, db: Session) -> tuple[Membership, str]:
    membership = get_business_membership(user, db)
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
        "source": "connected_pos_feed" if row.connection_id else "manual",
        "status": row.status,
        "created_at": row.created_at.isoformat(),
    }


def sync_discovered_terminals(db: Session, business_id: str) -> int:
    """Create billing terminal records from real POS transactions carrying a till identifier."""
    discovered = db.execute(
        select(
            POSTransaction.connection_id,
            POSTransaction.branch_name,
            POSTransaction.till_name,
        )
        .join(POSConnection, POSConnection.id == POSTransaction.connection_id)
        .where(
            POSTransaction.business_id == business_id,
            POSConnection.business_id == business_id,
            POSConnection.status != "disabled",
            POSTransaction.till_name.is_not(None),
            func.trim(POSTransaction.till_name) != "",
        )
        .distinct()
    ).all()
    created = 0
    for connection_id, branch_name, till_name in discovered:
        branch = (branch_name or "").strip() or None
        till = till_name.strip()
        # Stable per-connection + branch + till key. Till labels alone are not globally unique.
        identity = f"{connection_id}|{branch or ''}|{till}".casefold()
        external_id = "AUTO-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()
        existing = db.scalar(
            select(BusinessPOSTerminal).where(
                BusinessPOSTerminal.business_id == business_id,
                BusinessPOSTerminal.external_terminal_id == external_id,
            )
        )
        if existing:
            # Discovery refreshes descriptive metadata but never overrides a manual status decision.
            if existing.connection_id == connection_id:
                existing.display_name = till[:160]
                existing.branch_name = branch[:160] if branch else None
            continue
        db.add(BusinessPOSTerminal(
            business_id=business_id,
            connection_id=connection_id,
            external_terminal_id=external_id,
            display_name=till[:160],
            branch_name=branch[:160] if branch else None,
            status="active",
        ))
        created += 1
    if created or discovered:
        db.flush()
    return created


@router.get("/me")
def billing_overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _, business_id = current_business(user, db)
    sync_discovered_terminals(db, business_id)
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
    if not subscription:
        subscription = BusinessSubscription(business_id=business_id)
        db.add(subscription)
    subscription.active_pos_count = active_count
    subscription.referral_discount_applied = discount_eligible
    subscription.unit_price = STANDARD_PRICE
    subscription.discounted_unit_price = REFERRAL_PRICE
    subscription.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(subscription)
    return {
        "currency": "ZAR",
        "subscription_status": subscription.status if subscription else "not_started",
        "payment_status": "paid" if subscription and subscription.status == "active" else ("pending" if subscription and subscription.status == "pending" else "not_configured"),
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
        "notice": "PayFast payments are only marked active after a verified payment notification. Pricing shown is calculated from the current active POS terminal count.",
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


PAYFAST_ALLOWED_NETWORKS = tuple(ipaddress.ip_network(value) for value in (
    "197.97.145.144/28", "41.74.179.192/27", "102.216.36.0/28",
    "102.216.36.128/28", "144.126.193.139/32",
))


def _payfast_source_allowed(remote_addr: str | None) -> bool:
    if not remote_addr:
        return False
    try:
        address = ipaddress.ip_address(remote_addr)
    except ValueError:
        return False
    return any(address in network for network in PAYFAST_ALLOWED_NETWORKS)


def _confirm_payfast_itn(raw_body: bytes, sandbox: bool) -> bool:
    endpoint = (
        "https://sandbox.payfast.co.za/eng/query/validate"
        if sandbox else "https://www.payfast.co.za/eng/query/validate"
    )
    try:
        response = httpx.post(
            endpoint,
            content=raw_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        return response.status_code == 200 and response.text.strip() == "VALID"
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="PayFast verification is temporarily unavailable.") from None


@router.post("/payfast/checkout")
def create_payfast_checkout(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _, business_id = current_business(user, db)
    if not all((settings.payfast_merchant_id, settings.payfast_merchant_key, settings.payfast_passphrase)):
        raise HTTPException(status_code=503, detail="PayFast merchant credentials are not configured.")
    sync_discovered_terminals(db, business_id)
    terminals = db.scalars(select(BusinessPOSTerminal).where(
        BusinessPOSTerminal.business_id == business_id,
        BusinessPOSTerminal.status == "active",
    )).all()
    terminal_count = len(terminals)
    if terminal_count < 1:
        raise HTTPException(status_code=400, detail="Register at least one active POS terminal before subscribing.")
    paid_referrals = db.scalar(select(func.count(BusinessReferral.id)).where(
        BusinessReferral.referrer_business_id == business_id,
        BusinessReferral.status == "payment_verified",
    )) or 0
    discounted = paid_referrals >= 5
    unit_price = REFERRAL_PRICE if discounted else STANDARD_PRICE
    amount = (unit_price * terminal_count).quantize(Decimal("0.01"))
    subscription = db.scalar(select(BusinessSubscription).where(BusinessSubscription.business_id == business_id))
    if not subscription:
        subscription = BusinessSubscription(business_id=business_id)
        db.add(subscription)
        db.flush()
    if subscription.status == "active" and subscription.provider_subscription_reference:
        raise HTTPException(status_code=409, detail="This business already has an active PayFast subscription.")
    subscription.status = "pending"
    subscription.payment_provider = "payfast"
    subscription.active_pos_count = terminal_count
    subscription.referral_discount_applied = discounted
    subscription.updated_at = datetime.now(timezone.utc)
    payment_reference = str(uuid.uuid4())
    payment = PayFastPayment(
        business_id=business_id,
        subscription_id=subscription.id,
        m_payment_id=payment_reference,
        amount=amount,
        currency="ZAR",
        terminal_count=terminal_count,
        unit_price=unit_price,
        referral_discount_applied=discounted,
        status="pending",
    )
    db.add(payment)
    db.flush()
    base_url = settings.frontend_base_url.rstrip("/")
    try:
        checkout_url, fields = build_subscription_checkout(
            merchant_id=settings.payfast_merchant_id,
            merchant_key=settings.payfast_merchant_key,
            passphrase=settings.payfast_passphrase,
            sandbox=settings.payfast_sandbox,
            return_url=f"{base_url}/billing?payment=pending",
            cancel_url=f"{base_url}/billing?payment=cancelled",
            notify_url=f"{settings.api_v1_prefix}/billing/payfast/itn",
            payment_id=payment_reference,
            amount=amount,
            email=user.email,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from None
    db.commit()
    return {"checkout_url": checkout_url, "fields": fields, "payment_reference": payment_reference,
            "amount": str(amount), "currency": "ZAR", "status": "pending_verification"}


@router.post("/payfast/itn")
async def receive_payfast_itn(request: Request, db: Session = Depends(get_db)) -> dict:
    raw_body = await request.body()
    try:
        pairs = parse_qsl(raw_body.decode("utf-8"), keep_blank_values=True, strict_parsing=True)
    except (UnicodeDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="Malformed PayFast notification.") from None
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=400, detail="Duplicate PayFast notification fields are not accepted.")
    data = dict(pairs)
    supplied_signature = data.get("signature", "")
    if not verify_itn_signature(pairs, supplied_signature, settings.payfast_passphrase or None):
        raise HTTPException(status_code=400, detail="Invalid PayFast signature.")
    if data.get("merchant_id") != settings.payfast_merchant_id:
        raise HTTPException(status_code=400, detail="PayFast merchant ID mismatch.")
    if not _payfast_source_allowed(request.client.host if request.client else None):
        raise HTTPException(status_code=403, detail="PayFast notification source is not allowed.")
    if not _confirm_payfast_itn(raw_body, settings.payfast_sandbox):
        raise HTTPException(status_code=400, detail="PayFast could not validate this notification.")
    payment_reference = data.get("m_payment_id", "")
    payment = db.scalar(select(PayFastPayment).where(PayFastPayment.m_payment_id == payment_reference))
    if not payment:
        raise HTTPException(status_code=404, detail="Unknown PayFast payment reference.")
    if payment.status == "verified":
        if payment.pf_payment_id == data.get("pf_payment_id"):
            return {"status": "accepted", "duplicate": True}
        raise HTTPException(status_code=409, detail="Payment reference was already used.")
    if data.get("payment_status") != "COMPLETE":
        payment.status = "failed"
        db.commit()
        return {"status": "recorded", "payment_status": data.get("payment_status", "unknown")}
    try:
        received_amount = Decimal(data.get("amount_gross", ""))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PayFast payment amount.") from None
    if not received_amount.is_finite() or received_amount != Decimal(payment.amount):
        raise HTTPException(status_code=400, detail="PayFast payment amount does not match the expected amount.")
    provider_payment_id = data.get("pf_payment_id", "").strip()
    if not provider_payment_id:
        raise HTTPException(status_code=400, detail="PayFast payment ID is missing.")
    subscription = db.scalar(select(BusinessSubscription).where(
        BusinessSubscription.id == payment.subscription_id,
        BusinessSubscription.business_id == payment.business_id,
    ))
    if not subscription:
        raise HTTPException(status_code=409, detail="Subscription record is unavailable.")
    payment.status = "verified"
    payment.pf_payment_id = provider_payment_id
    payment.provider_subscription_token = data.get("token") or None
    payment.verified_at = datetime.now(timezone.utc)
    subscription.status = "active"
    subscription.payment_provider = "payfast"
    subscription.provider_subscription_reference = data.get("token") or None
    subscription.provider_customer_reference = provider_payment_id
    subscription.active_pos_count = payment.terminal_count
    subscription.referral_discount_applied = payment.referral_discount_applied
    subscription.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "accepted", "payment_status": "verified"}
