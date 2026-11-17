import secrets
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import Invoice, InvoiceLineItem, Membership, User
from app.schemas_invoices import InvoiceCreate, InvoiceResponse, InvoiceStatusUpdate

router = APIRouter(prefix="/invoices", tags=["invoices"])
CENT = Decimal("0.01")

def current_membership(user: User, db: Session) -> Membership:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership:
        raise HTTPException(status_code=403, detail="A business workspace is required.")
    return membership

def require_reader(membership: Membership) -> None:
    if membership.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="You do not have permission to view invoices.")

def require_admin(membership: Membership) -> None:
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only business owners or administrators can manage invoices.")

def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)

def invoice_query(invoice_id: str, business_id: str):
    return select(Invoice).options(selectinload(Invoice.lines)).where(
        Invoice.id == invoice_id, Invoice.business_id == business_id
    )

@router.get("", response_model=list[InvoiceResponse])
def list_invoices(
    invoice_status: str | None = Query(default=None, alias="status", pattern="^(draft|sent|paid|overdue|cancelled)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_reader(membership)
    statement = select(Invoice).options(selectinload(Invoice.lines)).where(Invoice.business_id == membership.business_id)
    if invoice_status:
        statement = statement.where(Invoice.status == invoice_status)
    statement = statement.order_by(Invoice.created_at.desc())
    return list(db.scalars(statement).all())

@router.post("", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_admin(membership)
    subtotal = Decimal("0.00")
    tax_total = Decimal("0.00")
    calculated_lines = []
    for line in payload.lines:
        line_subtotal = money(line.quantity * line.unit_price)
        line_tax = money(line_subtotal * line.tax_rate / Decimal("100"))
        line_total = line_subtotal + line_tax
        subtotal += line_subtotal
        tax_total += line_tax
        calculated_lines.append({
            "description": line.description, "quantity": line.quantity, "unit_price": line.unit_price,
            "tax_rate": line.tax_rate, "line_subtotal": line_subtotal, "line_tax": line_tax, "line_total": line_total,
        })
    invoice_number = "VX-" + str(payload.issue_date.year) + "-" + secrets.token_hex(3).upper()
    invoice = Invoice(
        business_id=membership.business_id, created_by_user_id=user.id, invoice_number=invoice_number,
        customer_name=payload.customer_name, customer_email=str(payload.customer_email) if payload.customer_email else None,
        customer_phone=payload.customer_phone, customer_address=payload.customer_address,
        issue_date=payload.issue_date, due_date=payload.due_date, currency=payload.currency.upper(),
        status="draft", subtotal=subtotal, tax_total=tax_total, total=subtotal + tax_total, notes=payload.notes,
    )
    db.add(invoice)
    db.flush()
    for line in calculated_lines:
        db.add(InvoiceLineItem(invoice_id=invoice.id, **line))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Invoice number collision. Please create the invoice again.") from None
    return db.scalar(invoice_query(invoice.id, membership.business_id))

@router.get("/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = current_membership(user, db)
    require_reader(membership)
    invoice = db.scalar(invoice_query(invoice_id, membership.business_id))
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice

@router.patch("/{invoice_id}/status", response_model=InvoiceResponse)
def update_invoice_status(
    invoice_id: str,
    payload: InvoiceStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_admin(membership)
    invoice = db.scalar(invoice_query(invoice_id, membership.business_id))
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    if invoice.status == "cancelled":
        raise HTTPException(status_code=409, detail="Cancelled invoices cannot be changed.")
    invoice.status = payload.status
    invoice.paid_at = datetime.now(timezone.utc) if payload.status == "paid" else None
    db.commit()
    return db.scalar(invoice_query(invoice.id, membership.business_id))
