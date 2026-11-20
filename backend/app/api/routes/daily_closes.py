import json
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.business_context import get_business_membership
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import DailyBusinessClose, DailyBusinessCloseAudit, Membership, POSTransaction, User

router = APIRouter(prefix="/daily-closes", tags=["daily-business-close"])
ZERO = Decimal("0.00")


class DailyCloseInput(BaseModel):
    business_date: date
    branch_name: str = Field(default="Main branch", min_length=1, max_length=160)
    currency: str = Field(default="ZAR", pattern=r"^[A-Za-z]{3}$")
    timezone_name: str = Field(default="Africa/Johannesburg", min_length=1, max_length=80)
    expected_cash: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    expected_card: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    expected_other: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    actual_cash: Decimal = Field(default=ZERO, ge=0, max_digits=14, decimal_places=2)
    actual_card: Decimal = Field(default=ZERO, ge=0, max_digits=14, decimal_places=2)
    actual_other: Decimal = Field(default=ZERO, ge=0, max_digits=14, decimal_places=2)
    expenses_total: Decimal = Field(default=ZERO, ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=4000)


class ReviewInput(BaseModel):
    decision: str = Field(pattern=r"^(approved|requires_attention)$")
    note: str | None = Field(default=None, max_length=2000)


def current_membership(user: User, db: Session) -> Membership:
    membership = get_business_membership(user, db)
    if not membership:
        raise HTTPException(status_code=403, detail="A business workspace is required.")
    if membership.role not in {"owner", "admin", "manager", "staff"}:
        raise HTTPException(status_code=403, detail="You do not have access to daily business close.")
    return membership


def require_reviewer(membership: Membership) -> None:
    if membership.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="Only an owner, administrator or manager can review a daily close.")


def as_money(value):
    return f"{Decimal(value or 0):.2f}"


def serialize_close(row: DailyBusinessClose) -> dict:
    expected_values = [row.expected_cash, row.expected_card, row.expected_other]
    expected_total = sum((Decimal(v) for v in expected_values if v is not None), ZERO) if all(v is not None for v in expected_values) else None
    actual_total = Decimal(row.actual_cash) + Decimal(row.actual_card) + Decimal(row.actual_other)
    variance_cash = Decimal(row.actual_cash) - Decimal(row.expected_cash) if row.expected_cash is not None else None
    variance_card = Decimal(row.actual_card) - Decimal(row.expected_card) if row.expected_card is not None else None
    variance_other = Decimal(row.actual_other) - Decimal(row.expected_other) if row.expected_other is not None else None
    variance_total = actual_total - expected_total if expected_total is not None else None
    return {
        "id": row.id, "business_date": row.business_date.isoformat(), "branch_name": row.branch_name,
        "currency": row.currency, "timezone_name": row.timezone_name, "source_type": row.source_type, "pos_transaction_count": row.pos_transaction_count,
        "expected_cash": as_money(row.expected_cash), "expected_card": as_money(row.expected_card),
        "expected_other": as_money(row.expected_other), "expected_total": as_money(expected_total) if expected_total is not None else None,
        "actual_cash": as_money(row.actual_cash), "actual_card": as_money(row.actual_card),
        "actual_other": as_money(row.actual_other), "actual_total": as_money(actual_total),
        "expenses_total": as_money(row.expenses_total),
        "variance_cash": as_money(variance_cash) if variance_cash is not None else None,
        "variance_card": as_money(variance_card) if variance_card is not None else None,
        "variance_other": as_money(variance_other) if variance_other is not None else None,
        "variance_total": as_money(variance_total) if variance_total is not None else None,
        "notes": row.notes, "status": row.status, "review_note": row.review_note,
        "created_by_user_id": row.created_by_user_id, "submitted_by_user_id": row.submitted_by_user_id,
        "reviewed_by_user_id": row.reviewed_by_user_id, "submitted_at": row.submitted_at,
        "reviewed_at": row.reviewed_at, "created_at": row.created_at, "updated_at": row.updated_at,
    }


def audit(db: Session, row: DailyBusinessClose, user: User, action: str, details: dict | None = None) -> None:
    db.add(DailyBusinessCloseAudit(
        id=str(uuid.uuid4()), close_id=row.id, business_id=row.business_id,
        actor_user_id=user.id, action=action, details_json=json.dumps(details or {}, sort_keys=True),
    ))


@router.get("")
def list_daily_closes(
    business_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    statement = select(DailyBusinessClose).where(DailyBusinessClose.business_id == membership.business_id)
    if business_date:
        statement = statement.where(DailyBusinessClose.business_date == business_date)
    rows = db.scalars(statement.order_by(DailyBusinessClose.business_date.desc(), DailyBusinessClose.branch_name).limit(100)).all()
    return [serialize_close(row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def save_daily_close(
    payload: DailyCloseInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    branch = payload.branch_name.strip()
    currency = payload.currency.upper()
    try:
        tz = ZoneInfo(payload.timezone_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=422, detail="Choose a valid business timezone.") from None
    local_start = datetime.combine(payload.business_date, time.min, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    start_utc = local_start.astimezone(timezone.utc)
    end_utc = local_end.astimezone(timezone.utc)
    pos_rows = db.scalars(select(POSTransaction).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.currency == currency,
        POSTransaction.occurred_at >= start_utc,
        POSTransaction.occurred_at < end_utc,
        POSTransaction.branch_name == branch,
    )).all()

    if pos_rows:
        expected = {"cash": ZERO, "card": ZERO, "other": ZERO}
        for transaction in pos_rows:
            amount = Decimal(transaction.net_amount or 0)
            if transaction.transaction_type == "refund":
                amount = -abs(amount)
            elif transaction.transaction_type == "void":
                continue
            method = (transaction.payment_method or "").casefold()
            bucket = "cash" if "cash" in method else "card" if any(x in method for x in ("card", "visa", "master", "credit", "debit")) else "other"
            expected[bucket] += amount
        source_type = "pos"
        expected_cash, expected_card, expected_other = expected["cash"], expected["card"], expected["other"]
    else:
        if any(value is None for value in (payload.expected_cash, payload.expected_card, payload.expected_other)):
            raise HTTPException(status_code=422, detail="No POS transactions were found for this branch and date. Enter expected cash, card and other totals manually.")
        source_type = "manual"
        expected_cash, expected_card, expected_other = payload.expected_cash, payload.expected_card, payload.expected_other

    row = db.scalar(select(DailyBusinessClose).where(
        DailyBusinessClose.business_id == membership.business_id,
        DailyBusinessClose.branch_name == branch,
        DailyBusinessClose.business_date == payload.business_date,
    ))
    action = "created"
    if row:
        if row.status not in {"draft", "requires_attention"}:
            raise HTTPException(status_code=409, detail="This business day has already been submitted. A reviewed close cannot be overwritten.")
        action = "updated"
        row.source_type = source_type
        row.currency = currency
        row.timezone_name = payload.timezone_name
        row.expected_cash, row.expected_card, row.expected_other = expected_cash, expected_card, expected_other
        row.actual_cash, row.actual_card, row.actual_other = payload.actual_cash, payload.actual_card, payload.actual_other
        row.expenses_total = payload.expenses_total
        row.pos_transaction_count = len(pos_rows)
        row.notes = payload.notes
        row.status = "draft"
        row.submitted_by_user_id = None
        row.submitted_at = None
        row.review_note = None
        row.reviewed_by_user_id = None
        row.reviewed_at = None
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = DailyBusinessClose(
            id=str(uuid.uuid4()), business_id=membership.business_id, branch_name=branch,
            business_date=payload.business_date, currency=currency, timezone_name=payload.timezone_name, source_type=source_type,
            expected_cash=expected_cash, expected_card=expected_card, expected_other=expected_other,
            actual_cash=payload.actual_cash, actual_card=payload.actual_card, actual_other=payload.actual_other,
            expenses_total=payload.expenses_total, pos_transaction_count=len(pos_rows), notes=payload.notes,
            status="draft", created_by_user_id=user.id,
        )
        db.add(row)
    audit(db, row, user, action, {"source_type": source_type, "pos_transaction_count": len(pos_rows)})
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A close for this branch and date already exists. Refresh and reopen it.") from None
    db.refresh(row)
    return serialize_close(row)


@router.post("/{close_id}/submit")
def submit_daily_close(
    close_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    row = db.scalar(select(DailyBusinessClose).where(
        DailyBusinessClose.id == close_id, DailyBusinessClose.business_id == membership.business_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Daily close not found.")
    if row.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft close can be submitted.")
    row.status = "submitted"
    row.submitted_by_user_id = user.id
    row.submitted_at = datetime.now(timezone.utc)
    audit(db, row, user, "submitted")
    db.commit()
    db.refresh(row)
    return serialize_close(row)


@router.post("/{close_id}/review")
def review_daily_close(
    close_id: str,
    payload: ReviewInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_reviewer(membership)
    row = db.scalar(select(DailyBusinessClose).where(
        DailyBusinessClose.id == close_id, DailyBusinessClose.business_id == membership.business_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Daily close not found.")
    if row.status != "submitted":
        raise HTTPException(status_code=409, detail="Only a submitted close can be reviewed.")
    row.status = payload.decision
    row.review_note = payload.note
    row.reviewed_by_user_id = user.id
    row.reviewed_at = datetime.now(timezone.utc)
    audit(db, row, user, payload.decision, {"note": payload.note})
    db.commit()
    db.refresh(row)
    return serialize_close(row)


@router.get("/{close_id}/audit")
def daily_close_audit(
    close_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    row = db.scalar(select(DailyBusinessClose).where(
        DailyBusinessClose.id == close_id, DailyBusinessClose.business_id == membership.business_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Daily close not found.")
    events = db.scalars(select(DailyBusinessCloseAudit).where(
        DailyBusinessCloseAudit.close_id == row.id,
        DailyBusinessCloseAudit.business_id == membership.business_id,
    ).order_by(DailyBusinessCloseAudit.created_at.asc())).all()
    return [{"id": e.id, "actor_user_id": e.actor_user_id, "action": e.action,
             "details": json.loads(e.details_json or "{}"), "created_at": e.created_at} for e in events]


@router.get("/{close_id}/reconciliation")
def reconcile_daily_close(
    close_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compare a saved daily close with the current POS ledger without changing either source."""
    membership = current_membership(user, db)
    row = db.scalar(select(DailyBusinessClose).where(
        DailyBusinessClose.id == close_id,
        DailyBusinessClose.business_id == membership.business_id,
    ))
    if not row:
        raise HTTPException(status_code=404, detail="Daily close not found.")

    actual_received = {
        "cash": as_money(row.actual_cash),
        "card": as_money(row.actual_card),
        "other": as_money(row.actual_other),
    }
    if row.source_type != "pos":
        return {
            "close_id": row.id,
            "status": "manual_baseline",
            "source_type": "manual",
            "message": "This close used manually entered expected totals. No POS baseline was recorded, so a POS reconciliation cannot be verified.",
            "pos_transaction_count": 0,
            "pos_totals": None,
            "close_expected": None,
            "actual_received": actual_received,
            "variance_vs_pos": None,
        }

    try:
        tz = ZoneInfo(row.timezone_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=409, detail="The saved business timezone is invalid; reconciliation cannot be calculated.") from None

    local_start = datetime.combine(row.business_date, time.min, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    start_utc = local_start.astimezone(timezone.utc)
    end_utc = local_end.astimezone(timezone.utc)
    transactions = db.scalars(select(POSTransaction).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.currency == row.currency,
        POSTransaction.branch_name == row.branch_name,
        POSTransaction.occurred_at >= start_utc,
        POSTransaction.occurred_at < end_utc,
    )).all()

    totals = {"cash": ZERO, "card": ZERO, "other": ZERO}
    counted = 0
    for transaction in transactions:
        if transaction.transaction_type == "void":
            continue
        amount = Decimal(transaction.net_amount or 0)
        if transaction.transaction_type == "refund":
            amount = -abs(amount)
        method = (transaction.payment_method or "").casefold()
        bucket = "cash" if "cash" in method else "card" if any(
            token in method for token in ("card", "visa", "master", "credit", "debit")
        ) else "other"
        totals[bucket] += amount
        counted += 1

    if counted == 0:
        return {
            "close_id": row.id,
            "status": "pos_data_missing",
            "source_type": "pos",
            "message": "No non-void matching POS transactions are currently available for this branch and date. The saved POS baseline cannot be independently rechecked.",
            "saved_pos_transaction_count": row.pos_transaction_count,
            "pos_transaction_count": 0,
            "pos_totals": None,
            "close_expected": {
                "cash": as_money(row.expected_cash),
                "card": as_money(row.expected_card),
                "other": as_money(row.expected_other),
            },
            "actual_received": actual_received,
            "variance_vs_pos": None,
        }

    current_expected = {
        "cash": Decimal(row.expected_cash or 0),
        "card": Decimal(row.expected_card or 0),
        "other": Decimal(row.expected_other or 0),
    }
    changed = any(totals[key] != current_expected[key] for key in totals)
    variances = {
        key: Decimal(getattr(row, f"actual_{key}")) - totals[key]
        for key in totals
    }
    return {
        "close_id": row.id,
        "status": "source_changed" if changed else "reconciled",
        "source_type": "pos",
        "message": (
            "The current POS ledger differs from the POS figures saved with this close. Review late, corrected or newly imported transactions."
            if changed else
            "The current POS ledger matches the expected figures saved with this close. Differences below compare counted/confirmed receipts against POS totals."
        ),
        "saved_pos_transaction_count": row.pos_transaction_count,
        "pos_transaction_count": counted,
        "pos_totals": {key: as_money(value) for key, value in totals.items()},
        "close_expected": {key: as_money(value) for key, value in current_expected.items()},
        "actual_received": actual_received,
        "variance_vs_pos": {key: as_money(value) for key, value in variances.items()},
    }
