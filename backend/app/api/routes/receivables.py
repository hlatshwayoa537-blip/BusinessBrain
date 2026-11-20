import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.business_context import get_business_membership
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import CustomerInvoicePayment, Invoice, Membership, User

router = APIRouter(prefix="/receivables", tags=["customer receivables"])
MANAGERS = {"owner", "admin", "manager"}
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def membership_for(user: User, db: Session) -> Membership:
    membership = get_business_membership(user, db)
    if not membership or membership.role not in MANAGERS:
        raise HTTPException(status_code=403, detail="A business workspace with finance access is required.")
    return membership


def require_manager(membership: Membership) -> None:
    if membership.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="Only an owner, administrator or manager can record customer receipts.")


class CustomerReceiptCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_date: date
    payment_method: str = Field(default="manual", min_length=2, max_length=40)
    reference: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=12, max_length=80)
    notes: str | None = Field(default=None, max_length=1000)


def payment_payload(payment: CustomerInvoicePayment) -> dict:
    return {
        "id": payment.id, "amount": f"{Decimal(payment.amount):.2f}",
        "currency": payment.currency, "payment_date": payment.payment_date.isoformat(),
        "payment_method": payment.payment_method, "reference": payment.reference,
        "notes": payment.notes, "recorded_at": payment.created_at.isoformat(),
        "verification": "manually_recorded_not_bank_verified",
    }


def invoice_receivable_payload(invoice: Invoice, db: Session, today: date) -> dict:
    payments = db.scalars(select(CustomerInvoicePayment).where(
        CustomerInvoicePayment.invoice_id == invoice.id,
        CustomerInvoicePayment.business_id == invoice.business_id,
    ).order_by(CustomerInvoicePayment.payment_date.asc(), CustomerInvoicePayment.created_at.asc())).all()
    paid = sum((Decimal(row.amount) for row in payments), ZERO)
    balance = max(ZERO, Decimal(invoice.total) - paid)
    days_overdue = max(0, (today - invoice.due_date).days) if balance > ZERO else 0
    return {
        "id": invoice.id, "invoice_number": invoice.invoice_number,
        "customer_name": invoice.customer_name, "customer_email": invoice.customer_email,
        "issue_date": invoice.issue_date.isoformat(), "due_date": invoice.due_date.isoformat(),
        "currency": invoice.currency, "status": "paid" if balance == ZERO else (
            "overdue" if invoice.due_date < today else invoice.status
        ),
        "invoice_total": f"{Decimal(invoice.total):.2f}", "amount_received": f"{paid:.2f}",
        "balance_due": f"{balance:.2f}", "days_overdue": days_overdue,
        "payments": [payment_payload(row) for row in payments],
    }


@router.get("/summary")
def receivables_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    today = date.today()
    invoices = db.scalars(select(Invoice).where(
        Invoice.business_id == membership.business_id,
        Invoice.status.in_(["sent", "overdue", "paid"]),
    ).order_by(Invoice.due_date.asc(), Invoice.created_at.asc())).all()
    rows = [invoice_receivable_payload(invoice, db, today) for invoice in invoices]
    outstanding = [row for row in rows if Decimal(row["balance_due"]) > ZERO]
    totals: dict[str, Decimal] = {}
    buckets: dict[str, dict[str, Decimal]] = {}
    for row in outstanding:
        currency = row["currency"]
        totals[currency] = totals.get(currency, ZERO) + Decimal(row["balance_due"])
        bucket = "not_due" if row["days_overdue"] == 0 else "1_30" if row["days_overdue"] <= 30 else "31_60" if row["days_overdue"] <= 60 else "61_plus"
        if currency not in buckets:
            buckets[currency] = {key: ZERO for key in ("not_due", "1_30", "31_60", "61_plus")}
        buckets[currency][bucket] += Decimal(row["balance_due"])
    return {
        "as_of": today.isoformat(),
        "invoice_count": len(rows),
        "open_invoice_count": len(outstanding),
        "outstanding_by_currency": {key: f"{value:.2f}" for key, value in totals.items()},
        "aging_by_currency": {currency: {key: f"{value:.2f}" for key, value in values.items()} for currency, values in buckets.items()},
        "invoices": rows,
        "limitations": [
            "Receipts are manually recorded; they are not independently bank-verified unless separately matched to an imported bank statement.",
            "Draft and cancelled invoices are excluded. Only sent, overdue and paid invoices are included.",
            "This is an accounts-receivable ledger, not a live bank balance or guaranteed collection forecast."
        ],
    }


@router.post("/invoices/{invoice_id}/receipts", status_code=status.HTTP_201_CREATED)
def record_customer_receipt(
    invoice_id: str, payload: CustomerReceiptCreate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    require_manager(membership)
    invoice = db.scalar(select(Invoice).where(
        Invoice.id == invoice_id, Invoice.business_id == membership.business_id
    ).with_for_update())
    if not invoice:
        raise HTTPException(status_code=404, detail="Customer invoice not found.")
    if invoice.status in {"draft", "cancelled"}:
        raise HTTPException(status_code=409, detail="Only sent customer invoices can receive payments.")
    existing = db.scalar(select(CustomerInvoicePayment).where(
        CustomerInvoicePayment.business_id == membership.business_id,
        CustomerInvoicePayment.idempotency_key == payload.idempotency_key,
    ))
    if existing:
        if existing.invoice_id != invoice.id or Decimal(existing.amount) != payload.amount or existing.payment_date != payload.payment_date or existing.reference != payload.reference:
            raise HTTPException(status_code=409, detail="This idempotency key was already used for a different receipt.")
        return {"receipt": payment_payload(existing), "receivable": invoice_receivable_payload(invoice, db, date.today()), "replayed": True}
    payments = db.scalars(select(CustomerInvoicePayment).where(
        CustomerInvoicePayment.invoice_id == invoice.id,
        CustomerInvoicePayment.business_id == membership.business_id,
    )).all()
    paid = sum((Decimal(row.amount) for row in payments), ZERO)
    balance = Decimal(invoice.total) - paid
    if payload.amount > balance:
        raise HTTPException(status_code=409, detail=f"Receipt exceeds the remaining invoice balance of {balance:.2f} {invoice.currency}.")
    receipt = CustomerInvoicePayment(
        id=str(uuid.uuid4()), business_id=membership.business_id, invoice_id=invoice.id,
        amount=payload.amount, currency=invoice.currency, payment_date=payload.payment_date,
        payment_method=payload.payment_method, reference=payload.reference,
        idempotency_key=payload.idempotency_key, notes=payload.notes,
        recorded_by_user_id=user.id,
    )
    db.add(receipt)
    new_paid = paid + payload.amount
    if new_paid == Decimal(invoice.total):
        invoice.status = "paid"
        invoice.paid_at = datetime.now(timezone.utc)
    elif invoice.status == "paid":
        invoice.status = "sent"
        invoice.paid_at = None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Receipt could not be recorded because the invoice or idempotency key changed. Refresh and retry.") from None
    db.refresh(receipt)
    db.refresh(invoice)
    return {"receipt": payment_payload(receipt), "receivable": invoice_receivable_payload(invoice, db, date.today()), "replayed": False}
