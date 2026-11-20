import json
import re
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import (
    Membership, PurchaseOrder, PurchaseOrderLine, Supplier, SupplierInvoice,
    SupplierInvoiceEvent, SupplierInvoiceLine, SupplierInvoicePayable, SupplierInvoicePayment, User,
)

router = APIRouter(prefix="/supplier-invoices", tags=["supplier invoice matching"])
MANAGERS = {"owner", "admin", "manager"}
MEMBERS = MANAGERS | {"staff", "employee", "hr"}
CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def membership_for(user: User, db: Session) -> Membership:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership or membership.role not in MEMBERS:
        raise HTTPException(status_code=403, detail="A business workspace with supplier invoice access is required.")
    return membership


def require_manager(membership: Membership) -> None:
    if membership.role not in MANAGERS:
        raise HTTPException(status_code=403, detail="Only an owner, administrator or manager can change supplier invoices.")


def normalized_reference(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


class SupplierInvoiceLineInput(BaseModel):
    description: str = Field(min_length=2, max_length=240)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)
    purchase_order_line_id: str | None = None


class SupplierInvoiceCreate(BaseModel):
    supplier_id: str
    purchase_order_id: str | None = None
    supplier_reference: str = Field(min_length=1, max_length=100)
    invoice_date: date
    due_date: date | None = None
    currency: str = Field(default="ZAR", min_length=3, max_length=3)
    stated_subtotal: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    stated_tax_total: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    stated_total: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[SupplierInvoiceLineInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def dates_and_reference(self):
        if self.due_date and self.due_date < self.invoice_date:
            raise ValueError("Due date cannot be before invoice date.")
        if not normalized_reference(self.supplier_reference):
            raise ValueError("Supplier invoice reference must contain letters or numbers.")
        return self


class ApprovalInput(BaseModel):
    override_reason: str | None = Field(default=None, min_length=8, max_length=1000)


class SupplierPaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_date: date
    payment_method: str = Field(default="manual", min_length=2, max_length=40)
    reference: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=12, max_length=80)
    notes: str | None = Field(default=None, max_length=1000)


def add_event(db: Session, invoice: SupplierInvoice, user: User, event_type: str, details: dict) -> None:
    db.add(SupplierInvoiceEvent(
        id=str(uuid.uuid4()), invoice_id=invoice.id, business_id=invoice.business_id,
        actor_user_id=user.id, event_type=event_type,
        details_json=json.dumps(details, sort_keys=True, default=str),
    ))


def match_invoice(db: Session, invoice: SupplierInvoice, lines: list[SupplierInvoiceLine]) -> dict:
    flags: list[dict] = []
    line_results = []
    po = None
    if invoice.purchase_order_id:
        po = db.scalar(select(PurchaseOrder).where(
            PurchaseOrder.id == invoice.purchase_order_id,
            PurchaseOrder.business_id == invoice.business_id,
            PurchaseOrder.supplier_id == invoice.supplier_id,
        ))
        if not po:
            flags.append({"code": "purchase_order_supplier_mismatch", "severity": "high", "message": "The purchase order does not belong to this supplier and business."})
    elif any(line.purchase_order_line_id for line in lines):
        flags.append({"code": "purchase_order_missing", "severity": "high", "message": "A purchase order line was selected without a purchase order."})

    for line in lines:
        result = {
            "invoice_line_id": line.id, "description": line.description,
            "quantity_billed": f"{Decimal(line.quantity):.3f}",
            "unit_price_billed": f"{Decimal(line.unit_price):.2f}",
            "tax_rate_billed": f"{Decimal(line.tax_rate):.2f}",
            "purchase_order_line_id": line.purchase_order_line_id,
            "flags": [],
        }
        if not line.purchase_order_line_id or not po:
            result["flags"].append("unmatched_purchase_order_line")
            line_results.append(result)
            flags.append({"code": "unmatched_purchase_order_line", "severity": "medium", "invoice_line_id": line.id, "message": f"'{line.description}' is not linked to a purchase order line."})
            continue
        po_line = db.scalar(select(PurchaseOrderLine).where(
            PurchaseOrderLine.id == line.purchase_order_line_id,
            PurchaseOrderLine.purchase_order_id == po.id,
            PurchaseOrderLine.business_id == invoice.business_id,
        ))
        if not po_line:
            result["flags"].append("purchase_order_line_not_found")
            flags.append({"code": "purchase_order_line_not_found", "severity": "high", "invoice_line_id": line.id, "message": "The selected purchase order line could not be found in this order."})
            line_results.append(result)
            continue
        ordered_price = Decimal(po_line.unit_price)
        ordered_tax = Decimal(po_line.tax_rate)
        received = Decimal(po_line.quantity_received)
        already_billed = db.scalar(
            select(func.coalesce(func.sum(SupplierInvoiceLine.quantity), 0))
            .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceLine.invoice_id)
            .where(
                SupplierInvoiceLine.business_id == invoice.business_id,
                SupplierInvoiceLine.purchase_order_line_id == po_line.id,
                SupplierInvoice.id != invoice.id,
                SupplierInvoice.status.in_(["needs_review", "approved"]),
            )
        ) or ZERO
        available_received = max(ZERO, received - Decimal(already_billed))
        if abs(Decimal(line.unit_price) - ordered_price) > CENT:
            result["flags"].append("unit_price_variance")
            flags.append({"code": "unit_price_variance", "severity": "high", "invoice_line_id": line.id, "message": f"'{line.description}' unit price differs from the purchase order.", "purchase_order_unit_price": f"{ordered_price:.2f}", "invoice_unit_price": f"{Decimal(line.unit_price):.2f}"})
        if Decimal(line.quantity) > available_received:
            result["flags"].append("billed_quantity_exceeds_received")
            flags.append({"code": "billed_quantity_exceeds_received", "severity": "high", "invoice_line_id": line.id, "message": f"'{line.description}' bills more than the received quantity still available to invoice.", "received_quantity": f"{received:.3f}", "previously_billed_quantity": f"{Decimal(already_billed):.3f}", "available_to_invoice": f"{available_received:.3f}", "quantity_billed": f"{Decimal(line.quantity):.3f}"})
        if abs(Decimal(line.tax_rate) - ordered_tax) > Decimal("0.01"):
            result["flags"].append("tax_rate_variance")
            flags.append({"code": "tax_rate_variance", "severity": "medium", "invoice_line_id": line.id, "message": f"'{line.description}' tax rate differs from the purchase order.", "purchase_order_tax_rate": f"{ordered_tax:.2f}", "invoice_tax_rate": f"{Decimal(line.tax_rate):.2f}"})
        result.update({
            "purchase_order_description": po_line.description,
            "purchase_order_quantity": f"{Decimal(po_line.quantity_ordered):.3f}",
            "purchase_order_received_quantity": f"{received:.3f}",
            "purchase_order_unit_price": f"{ordered_price:.2f}",
            "purchase_order_tax_rate": f"{ordered_tax:.2f}",
        })
        line_results.append(result)

    calculated_subtotal = sum((Decimal(x.quantity) * Decimal(x.unit_price) for x in lines), ZERO).quantize(CENT)
    calculated_tax = sum(((Decimal(x.quantity) * Decimal(x.unit_price) * Decimal(x.tax_rate) / Decimal("100")).quantize(CENT) for x in lines), ZERO).quantize(CENT)
    if abs(calculated_subtotal - Decimal(invoice.subtotal)) > CENT:
        flags.append({"code": "invoice_subtotal_mismatch", "severity": "high", "message": "The supplier-stated subtotal does not equal the sum of the invoice lines.", "stated": f"{Decimal(invoice.subtotal):.2f}", "calculated": f"{calculated_subtotal:.2f}"})
    if abs(calculated_tax - Decimal(invoice.tax_total)) > CENT:
        flags.append({"code": "vat_total_mismatch", "severity": "high", "message": "The supplier-stated VAT total does not equal the VAT calculated from the invoice lines.", "stated": f"{Decimal(invoice.tax_total):.2f}", "calculated": f"{calculated_tax:.2f}"})
    if abs(Decimal(invoice.subtotal) + Decimal(invoice.tax_total) - Decimal(invoice.total)) > CENT:
        flags.append({"code": "invoice_total_mismatch", "severity": "high", "message": "The supplier-stated total does not equal subtotal plus VAT."})
    return {
        "status": "matched" if not flags else "requires_review",
        "currency": invoice.currency,
        "supplier_reference": invoice.supplier_reference,
        "purchase_order_reference": po.reference if po else None,
        "line_results": line_results,
        "flags": flags,
        "flag_count": len(flags),
        "calculated_subtotal": f"{calculated_subtotal:.2f}",
        "calculated_tax_total": f"{calculated_tax:.2f}",
        "stated_subtotal": f"{Decimal(invoice.subtotal):.2f}",
        "stated_tax_total": f"{Decimal(invoice.tax_total):.2f}",
        "stated_total": f"{Decimal(invoice.total):.2f}",
        "automatically_posted_to_expenses_or_inventory": False,
    }


def payable_payload(payable: SupplierInvoicePayable, db: Session) -> dict:
    payments = db.scalars(select(SupplierInvoicePayment).where(
        SupplierInvoicePayment.payable_id == payable.id,
        SupplierInvoicePayment.business_id == payable.business_id,
    ).order_by(SupplierInvoicePayment.payment_date.asc(), SupplierInvoicePayment.created_at.asc())).all()
    supplier = db.scalar(select(Supplier).where(
        Supplier.id == payable.supplier_id, Supplier.business_id == payable.business_id,
    ))
    invoice = db.scalar(select(SupplierInvoice).where(
        SupplierInvoice.id == payable.invoice_id, SupplierInvoice.business_id == payable.business_id,
    ))
    return {
        "id": payable.id, "invoice_id": payable.invoice_id, "supplier_id": payable.supplier_id,
        "supplier_name": supplier.name if supplier else "Supplier unavailable",
        "supplier_reference": invoice.supplier_reference if invoice else "Invoice unavailable",
        "currency": payable.currency, "total_amount": f"{Decimal(payable.total_amount):.2f}",
        "amount_paid": f"{Decimal(payable.amount_paid):.2f}",
        "balance_due": f"{Decimal(payable.balance_due):.2f}", "due_date": payable.due_date,
        "status": payable.status, "created_at": payable.created_at, "updated_at": payable.updated_at,
        "payments": [{
            "id": p.id, "amount": f"{Decimal(p.amount):.2f}", "currency": p.currency,
            "payment_date": p.payment_date, "payment_method": p.payment_method,
            "reference": p.reference, "notes": p.notes, "recorded_by_user_id": p.recorded_by_user_id,
            "created_at": p.created_at,
        } for p in payments],
    }


def invoice_payload(invoice: SupplierInvoice, db: Session, include_events: bool = False) -> dict:
    supplier = db.scalar(select(Supplier).where(Supplier.id == invoice.supplier_id, Supplier.business_id == invoice.business_id))
    payable = db.scalar(select(SupplierInvoicePayable).where(
        SupplierInvoicePayable.invoice_id == invoice.id,
        SupplierInvoicePayable.business_id == invoice.business_id,
    ))
    lines = db.scalars(select(SupplierInvoiceLine).where(
        SupplierInvoiceLine.invoice_id == invoice.id,
        SupplierInvoiceLine.business_id == invoice.business_id,
    )).all()
    result = {
        "id": invoice.id, "supplier_id": invoice.supplier_id,
        "supplier_name": supplier.name if supplier else "Supplier unavailable",
        "purchase_order_id": invoice.purchase_order_id,
        "supplier_reference": invoice.supplier_reference,
        "invoice_date": invoice.invoice_date, "due_date": invoice.due_date,
        "currency": invoice.currency, "subtotal": f"{Decimal(invoice.subtotal):.2f}",
        "tax_total": f"{Decimal(invoice.tax_total):.2f}", "total": f"{Decimal(invoice.total):.2f}",
        "status": invoice.status, "match_results": json.loads(invoice.match_results_json or "{}"),
        "notes": invoice.notes, "created_at": invoice.created_at,
        "approved_by_user_id": invoice.approved_by_user_id, "approved_at": invoice.approved_at,
        "payable": payable_payload(payable, db) if payable else None,
        "lines": [{
            "id": line.id, "purchase_order_line_id": line.purchase_order_line_id,
            "description": line.description, "quantity": f"{Decimal(line.quantity):.3f}",
            "unit_price": f"{Decimal(line.unit_price):.2f}", "tax_rate": f"{Decimal(line.tax_rate):.2f}",
            "line_subtotal": f"{Decimal(line.line_subtotal):.2f}",
            "line_tax": f"{Decimal(line.line_tax):.2f}", "line_total": f"{Decimal(line.line_total):.2f}",
        } for line in lines],
    }
    if include_events:
        events = db.scalars(select(SupplierInvoiceEvent).where(
            SupplierInvoiceEvent.invoice_id == invoice.id,
            SupplierInvoiceEvent.business_id == invoice.business_id,
        ).order_by(SupplierInvoiceEvent.created_at.asc())).all()
        result["events"] = [{
            "event_type": e.event_type, "actor_user_id": e.actor_user_id,
            "details": json.loads(e.details_json or "{}"), "created_at": e.created_at,
        } for e in events]
    return result


@router.get("")
def list_supplier_invoices(
    status_filter: str | None = Query(default=None, alias="status", pattern=r"^(needs_review|approved)$"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    stmt = select(SupplierInvoice).where(SupplierInvoice.business_id == membership.business_id)
    if status_filter:
        stmt = stmt.where(SupplierInvoice.status == status_filter)
    rows = db.scalars(stmt.order_by(SupplierInvoice.created_at.desc()).limit(200)).all()
    return [invoice_payload(row, db) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_supplier_invoice(payload: SupplierInvoiceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    require_manager(membership)
    supplier = db.scalar(select(Supplier).where(
        Supplier.id == payload.supplier_id, Supplier.business_id == membership.business_id,
    ))
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    po = None
    if payload.purchase_order_id:
        po = db.scalar(select(PurchaseOrder).where(
            PurchaseOrder.id == payload.purchase_order_id,
            PurchaseOrder.business_id == membership.business_id,
            PurchaseOrder.supplier_id == supplier.id,
        ))
        if not po:
            raise HTTPException(status_code=404, detail="Purchase order for this supplier was not found.")
    normalized = normalized_reference(payload.supplier_reference)
    duplicate = db.scalar(select(SupplierInvoice.id).where(
        SupplierInvoice.business_id == membership.business_id,
        SupplierInvoice.supplier_id == supplier.id,
        SupplierInvoice.normalized_reference == normalized,
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail="This supplier invoice reference has already been recorded for this supplier.")
    if payload.currency.upper() != "ZAR":
        raise HTTPException(status_code=422, detail="Supplier invoice matching currently supports ZAR only.")
    if any(line.purchase_order_line_id for line in payload.lines) and not po:
        raise HTTPException(status_code=422, detail="Select the purchase order before linking invoice lines.")
    linked_po_lines = [line.purchase_order_line_id for line in payload.lines if line.purchase_order_line_id]
    if len(linked_po_lines) != len(set(linked_po_lines)):
        raise HTTPException(status_code=422, detail="Each purchase order line may be matched only once on a supplier invoice.")
    now = datetime.now(timezone.utc)
    invoice = SupplierInvoice(
        id=str(uuid.uuid4()), business_id=membership.business_id, supplier_id=supplier.id,
        purchase_order_id=po.id if po else None, supplier_reference=payload.supplier_reference.strip(),
        normalized_reference=normalized, invoice_date=payload.invoice_date, due_date=payload.due_date,
        currency="ZAR", subtotal=payload.stated_subtotal, tax_total=payload.stated_tax_total,
        total=payload.stated_total, status="needs_review", match_results_json="{}",
        notes=payload.notes, created_by_user_id=user.id, created_at=now, updated_at=now,
    )
    db.add(invoice)
    db.flush()
    lines = []
    for row in payload.lines:
        if row.purchase_order_line_id:
            po_line = db.scalar(select(PurchaseOrderLine).where(
                PurchaseOrderLine.id == row.purchase_order_line_id,
                PurchaseOrderLine.purchase_order_id == po.id,
                PurchaseOrderLine.business_id == membership.business_id,
            ))
            if not po_line:
                raise HTTPException(status_code=404, detail="Linked purchase order line not found.")
        subtotal = (row.quantity * row.unit_price).quantize(CENT)
        tax = (subtotal * row.tax_rate / Decimal("100")).quantize(CENT)
        line = SupplierInvoiceLine(
            id=str(uuid.uuid4()), invoice_id=invoice.id, business_id=membership.business_id,
            purchase_order_line_id=row.purchase_order_line_id, description=row.description.strip(),
            quantity=row.quantity, unit_price=row.unit_price, tax_rate=row.tax_rate,
            line_subtotal=subtotal, line_tax=tax, line_total=subtotal + tax,
        )
        db.add(line)
        lines.append(line)
    db.flush()
    results = match_invoice(db, invoice, lines)
    invoice.match_results_json = json.dumps(results, sort_keys=True)
    add_event(db, invoice, user, "created_and_matched", {
        "supplier_reference": invoice.supplier_reference, "purchase_order_id": invoice.purchase_order_id,
        "flag_count": results["flag_count"], "flags": [f["code"] for f in results["flags"]],
    })
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This supplier invoice reference has already been recorded.")
    db.refresh(invoice)
    return invoice_payload(invoice, db, include_events=True)


@router.get("/{invoice_id}")
def get_supplier_invoice(invoice_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    invoice = db.scalar(select(SupplierInvoice).where(
        SupplierInvoice.id == invoice_id, SupplierInvoice.business_id == membership.business_id,
    ))
    if not invoice:
        raise HTTPException(status_code=404, detail="Supplier invoice not found.")
    return invoice_payload(invoice, db, include_events=True)


@router.post("/{invoice_id}/approve")
def approve_supplier_invoice(invoice_id: str, payload: ApprovalInput, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    require_manager(membership)
    invoice = db.scalar(select(SupplierInvoice).where(
        SupplierInvoice.id == invoice_id, SupplierInvoice.business_id == membership.business_id,
    ).with_for_update())
    if not invoice:
        raise HTTPException(status_code=404, detail="Supplier invoice not found.")
    if invoice.status == "approved":
        raise HTTPException(status_code=409, detail="Supplier invoice has already been approved.")
    results = json.loads(invoice.match_results_json or "{}")
    flags = results.get("flags", [])
    reason = (payload.override_reason or "").strip()
    if flags and len(reason) < 8:
        raise HTTPException(status_code=409, detail="This invoice has unresolved matching flags. Provide a documented override reason to approve it.")
    invoice.status = "approved"
    invoice.approved_by_user_id = user.id
    invoice.approved_at = datetime.now(timezone.utc)
    invoice.updated_at = invoice.approved_at
    payable = db.scalar(select(SupplierInvoicePayable).where(
        SupplierInvoicePayable.invoice_id == invoice.id,
        SupplierInvoicePayable.business_id == membership.business_id,
    ).with_for_update())
    if not payable:
        payable = SupplierInvoicePayable(
            id=str(uuid.uuid4()), business_id=membership.business_id, invoice_id=invoice.id,
            supplier_id=invoice.supplier_id, currency=invoice.currency,
            total_amount=invoice.total, amount_paid=ZERO, balance_due=invoice.total,
            due_date=invoice.due_date, status="open",
            created_at=invoice.approved_at, updated_at=invoice.approved_at,
        )
        db.add(payable)
    add_event(db, invoice, user, "approved_with_override" if flags else "approved", {
        "override_reason": reason or None, "overridden_flags": [f["code"] for f in flags],
        "accounts_payable_created": True,
        "note": "Approval creates an accounts-payable liability only. It does not record a payment, create an expense transaction, or post inventory. Goods received are already handled by the purchase-order receipt workflow.",
    })
    db.commit()
    db.refresh(invoice)
    return invoice_payload(invoice, db, include_events=True)



@router.get("/payables/list")
def list_supplier_payables(
    status_filter: str | None = Query(default=None, alias="status", pattern=r"^(open|partially_paid|paid)$"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    stmt = select(SupplierInvoicePayable).where(
        SupplierInvoicePayable.business_id == membership.business_id,
    )
    if status_filter:
        stmt = stmt.where(SupplierInvoicePayable.status == status_filter)
    rows = db.scalars(stmt.order_by(SupplierInvoicePayable.due_date.asc(), SupplierInvoicePayable.created_at.desc()).limit(500)).all()
    return [payable_payload(row, db) for row in rows]


@router.post("/{invoice_id}/payments", status_code=status.HTTP_201_CREATED)
def record_supplier_invoice_payment(
    invoice_id: str, payload: SupplierPaymentCreate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    require_manager(membership)
    invoice = db.scalar(select(SupplierInvoice).where(
        SupplierInvoice.id == invoice_id, SupplierInvoice.business_id == membership.business_id,
    ).with_for_update())
    if not invoice:
        raise HTTPException(status_code=404, detail="Supplier invoice not found.")
    if invoice.status != "approved":
        raise HTTPException(status_code=409, detail="Only approved supplier invoices can have payments recorded.")
    payable = db.scalar(select(SupplierInvoicePayable).where(
        SupplierInvoicePayable.invoice_id == invoice.id,
        SupplierInvoicePayable.business_id == membership.business_id,
    ).with_for_update())
    if not payable:
        raise HTTPException(status_code=409, detail="The approved invoice has no accounts-payable record.")
    existing = db.scalar(select(SupplierInvoicePayment).where(
        SupplierInvoicePayment.business_id == membership.business_id,
        SupplierInvoicePayment.idempotency_key == payload.idempotency_key,
    ))
    if existing:
        same_request = (
            existing.invoice_id == invoice.id
            and Decimal(existing.amount) == payload.amount
            and existing.payment_date == payload.payment_date
            and existing.payment_method == payload.payment_method.strip()
            and existing.reference == (payload.reference.strip() if payload.reference else None)
        )
        if not same_request:
            raise HTTPException(status_code=409, detail="This idempotency key was already used for a different payment.")
        return {"payment": {
            "id": existing.id, "amount": f"{Decimal(existing.amount):.2f}",
            "payment_date": existing.payment_date, "reference": existing.reference,
        }, "payable": payable_payload(payable, db), "replayed": True}
    amount = payload.amount.quantize(CENT)
    if amount <= ZERO:
        raise HTTPException(status_code=422, detail="Payment amount must be at least one cent.")
    balance = Decimal(payable.balance_due).quantize(CENT)
    if amount > balance:
        raise HTTPException(status_code=409, detail=f"Payment exceeds the outstanding balance of {balance:.2f}.")
    payment = SupplierInvoicePayment(
        id=str(uuid.uuid4()), business_id=membership.business_id, payable_id=payable.id,
        invoice_id=invoice.id, amount=amount, currency=payable.currency,
        payment_date=payload.payment_date, payment_method=payload.payment_method.strip(),
        reference=payload.reference.strip() if payload.reference else None,
        idempotency_key=payload.idempotency_key, notes=payload.notes,
        recorded_by_user_id=user.id, created_at=datetime.now(timezone.utc),
    )
    payable.amount_paid = (Decimal(payable.amount_paid) + amount).quantize(CENT)
    payable.balance_due = (Decimal(payable.total_amount) - Decimal(payable.amount_paid)).quantize(CENT)
    payable.status = "paid" if payable.balance_due == ZERO else "partially_paid"
    payable.updated_at = datetime.now(timezone.utc)
    db.add(payment)
    add_event(db, invoice, user, "payment_recorded", {
        "payment_id": payment.id, "amount": f"{amount:.2f}", "currency": payable.currency,
        "payment_date": payload.payment_date.isoformat(), "payment_method": payment.payment_method,
        "reference": payment.reference, "remaining_balance": f"{Decimal(payable.balance_due):.2f}",
        "note": "Manually recorded payment; not independently verified against a bank statement.",
    })
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This payment idempotency key has already been used.")
    db.refresh(payment)
    db.refresh(payable)
    return {"payment": {
        "id": payment.id, "amount": f"{Decimal(payment.amount):.2f}",
        "payment_date": payment.payment_date, "reference": payment.reference,
    }, "payable": payable_payload(payable, db), "replayed": False}
