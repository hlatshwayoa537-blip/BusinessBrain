import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import InventoryItem, InventoryMovement, Membership, PurchaseOrder, PurchaseOrderEvent, PurchaseOrderLine, Supplier, User

router = APIRouter(prefix="/procurement", tags=["supplier and purchasing"])
MANAGERS = {"owner", "admin", "manager"}
MEMBERS = MANAGERS | {"staff", "employee", "hr"}
ZERO = Decimal("0.00")


def membership_for(user: User, db: Session) -> Membership:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership or membership.role not in MEMBERS:
        raise HTTPException(status_code=403, detail="A business workspace with procurement access is required.")
    return membership


def require_manager(membership: Membership) -> None:
    if membership.role not in MANAGERS:
        raise HTTPException(status_code=403, detail="Only an owner, administrator or manager can change procurement records.")


def add_event(db: Session, order: PurchaseOrder, user: User, event_type: str, details: dict | None = None, idempotency_key: str | None = None) -> PurchaseOrderEvent:
    event = PurchaseOrderEvent(
        id=str(uuid.uuid4()), purchase_order_id=order.id, business_id=order.business_id,
        actor_user_id=user.id, event_type=event_type,
        details_json=json.dumps(details or {}, sort_keys=True), idempotency_key=idempotency_key,
    )
    db.add(event)
    return event


def supplier_payload(item: Supplier) -> dict:
    return {
        "id": item.id, "name": item.name, "contact_name": item.contact_name,
        "email": item.email, "phone": item.phone, "address": item.address,
        "tax_number": item.tax_number, "notes": item.notes, "is_active": item.is_active,
        "created_at": item.created_at, "updated_at": item.updated_at,
    }


def line_payload(line: PurchaseOrderLine) -> dict:
    quantity = Decimal(line.quantity_ordered)
    received = Decimal(line.quantity_received)
    price = Decimal(line.unit_price)
    tax_rate = Decimal(line.tax_rate)
    subtotal = quantity * price
    tax = subtotal * tax_rate / Decimal("100")
    return {
        "id": line.id, "product_id": line.product_id, "description": line.description,
        "quantity_ordered": f"{quantity:.3f}", "quantity_received": f"{received:.3f}",
        "quantity_outstanding": f"{quantity - received:.3f}",
        "unit_price": f"{price:.2f}", "tax_rate": f"{tax_rate:.2f}",
        "line_subtotal": f"{subtotal:.2f}", "line_tax": f"{tax:.2f}",
        "line_total": f"{subtotal + tax:.2f}",
    }


def order_payload(order: PurchaseOrder, db: Session, include_events: bool = False) -> dict:
    supplier = db.scalar(select(Supplier).where(
        Supplier.id == order.supplier_id, Supplier.business_id == order.business_id,
    ))
    lines = db.scalars(select(PurchaseOrderLine).where(
        PurchaseOrderLine.purchase_order_id == order.id,
        PurchaseOrderLine.business_id == order.business_id,
    ).order_by(PurchaseOrderLine.created_at.asc())).all()
    line_data = [line_payload(line) for line in lines]
    subtotal = sum((Decimal(row["line_subtotal"]) for row in line_data), ZERO)
    tax = sum((Decimal(row["line_tax"]) for row in line_data), ZERO)
    result = {
        "id": order.id, "reference": order.reference, "supplier_id": order.supplier_id,
        "supplier_name": supplier.name if supplier else "Supplier unavailable",
        "status": order.status, "currency": order.currency,
        "expected_delivery_date": order.expected_delivery_date, "notes": order.notes,
        "subtotal": f"{subtotal:.2f}", "tax_total": f"{tax:.2f}",
        "total": f"{subtotal + tax:.2f}", "lines": line_data,
        "created_by_user_id": order.created_by_user_id, "submitted_at": order.submitted_at,
        "received_at": order.received_at, "created_at": order.created_at,
        "updated_at": order.updated_at,
    }
    if include_events:
        events = db.scalars(select(PurchaseOrderEvent).where(
            PurchaseOrderEvent.purchase_order_id == order.id,
            PurchaseOrderEvent.business_id == order.business_id,
        ).order_by(PurchaseOrderEvent.created_at.asc())).all()
        result["events"] = [{
            "id": event.id, "event_type": event.event_type,
            "actor_user_id": event.actor_user_id,
            "details": json.loads(event.details_json or "{}"),
            "created_at": event.created_at,
        } for event in events]
    return result


def scoped_order(order_id: str, business_id: str, db: Session) -> PurchaseOrder:
    order = db.scalar(select(PurchaseOrder).where(
        PurchaseOrder.id == order_id, PurchaseOrder.business_id == business_id,
    ))
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found.")
    return order


def scoped_supplier(supplier_id: str, business_id: str, db: Session, active: bool = False) -> Supplier:
    supplier = db.scalar(select(Supplier).where(
        Supplier.id == supplier_id, Supplier.business_id == business_id,
    ))
    if not supplier or (active and not supplier.is_active):
        raise HTTPException(status_code=404, detail="Active supplier not found.")
    return supplier


class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    contact_name: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=2000)
    tax_number: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    contact_name: str | None = Field(default=None, max_length=160)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=2000)
    tax_number: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None


class PurchaseOrderLineInput(BaseModel):
    description: str = Field(min_length=2, max_length=240)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    tax_rate: Decimal = Field(default=Decimal("0"), ge=0, le=100, max_digits=5, decimal_places=2)
    product_id: str | None = None


class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[PurchaseOrderLineInput] = Field(min_length=1, max_length=100)


class PurchaseOrderUpdate(BaseModel):
    supplier_id: str | None = None
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=4000)
    lines: list[PurchaseOrderLineInput] | None = Field(default=None, min_length=1, max_length=100)


class ReceiptLineInput(BaseModel):
    line_id: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class GoodsReceiptCreate(BaseModel):
    lines: list[ReceiptLineInput] = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=2000)
    location: str = Field(default="Main", min_length=1, max_length=120)
    idempotency_key: str = Field(min_length=16, max_length=80)


@router.get("/suppliers")
def list_suppliers(active_only: bool = Query(default=False), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    statement = select(Supplier).where(Supplier.business_id == membership.business_id)
    if active_only:
        statement = statement.where(Supplier.is_active.is_(True))
    rows = db.scalars(statement.order_by(Supplier.name.asc())).all()
    return [supplier_payload(row) for row in rows]


@router.post("/suppliers", status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    require_manager(membership)
    name = payload.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Supplier name must contain at least two non-space characters.")
    duplicate = db.scalar(select(Supplier.id).where(
        Supplier.business_id == membership.business_id, func.lower(Supplier.name) == name.lower(),
    ))
    if duplicate:
        raise HTTPException(status_code=409, detail="A supplier with this name already exists.")
    item = Supplier(
        id=str(uuid.uuid4()), business_id=membership.business_id, name=name,
        contact_name=payload.contact_name, email=payload.email, phone=payload.phone,
        address=payload.address, tax_number=payload.tax_number, notes=payload.notes, is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return supplier_payload(item)


@router.patch("/suppliers/{supplier_id}")
def update_supplier(supplier_id: str, payload: SupplierUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    require_manager(membership)
    item = scoped_supplier(supplier_id, membership.business_id, db)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if len(changes["name"]) < 2:
            raise HTTPException(status_code=422, detail="Supplier name must contain at least two non-space characters.")
        duplicate = db.scalar(select(Supplier.id).where(
            Supplier.business_id == membership.business_id,
            func.lower(Supplier.name) == changes["name"].lower(), Supplier.id != item.id,
        ))
        if duplicate:
            raise HTTPException(status_code=409, detail="A supplier with this name already exists.")
    for key, value in changes.items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return supplier_payload(item)


@router.get("/purchase-orders")
def list_purchase_orders(status_filter: str | None = Query(default=None, alias="status", pattern=r"^(draft|submitted|partially_received|received|cancelled)$"), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    statement = select(PurchaseOrder).where(PurchaseOrder.business_id == membership.business_id)
    if status_filter:
        statement = statement.where(PurchaseOrder.status == status_filter)
    rows = db.scalars(statement.order_by(PurchaseOrder.created_at.desc()).limit(200)).all()
    return [order_payload(row, db) for row in rows]


@router.post("/purchase-orders", status_code=status.HTTP_201_CREATED)
def create_purchase_order(payload: PurchaseOrderCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    require_manager(membership)
    scoped_supplier(payload.supplier_id, membership.business_id, db, active=True)
    for line in payload.lines:
        if line.product_id:
            db_item = db.scalar(select(InventoryItem).where(
                InventoryItem.id == line.product_id, InventoryItem.business_id == membership.business_id,
                InventoryItem.is_active.is_(True),
            ))
            if not db_item:
                raise HTTPException(status_code=404, detail="Linked inventory item not found.")
    order = PurchaseOrder(
        id=str(uuid.uuid4()), business_id=membership.business_id, supplier_id=payload.supplier_id,
        reference=f"PO-{date.today():%Y%m%d}-{uuid.uuid4().hex[:6].upper()}",
        status="draft", currency="ZAR", expected_delivery_date=payload.expected_delivery_date,
        notes=payload.notes, created_by_user_id=user.id,
    )
    db.add(order)
    db.flush()
    for line in payload.lines:
        db.add(PurchaseOrderLine(
            id=str(uuid.uuid4()), purchase_order_id=order.id, business_id=membership.business_id,
            description=line.description.strip(), quantity_ordered=line.quantity,
            quantity_received=Decimal("0"), unit_price=line.unit_price, tax_rate=line.tax_rate,
            product_id=line.product_id,
        ))
    add_event(db, order, user, "created", {"line_count": len(payload.lines), "status": "draft"})
    db.commit()
    db.refresh(order)
    return order_payload(order, db, include_events=True)


@router.get("/purchase-orders/{order_id}")
def get_purchase_order(order_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    return order_payload(scoped_order(order_id, membership.business_id, db), db, include_events=True)


@router.patch("/purchase-orders/{order_id}")
def update_purchase_order(order_id: str, payload: PurchaseOrderUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    require_manager(membership)
    order = scoped_order(order_id, membership.business_id, db)
    if order.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft purchase orders can be edited.")
    changes = payload.model_dump(exclude_unset=True)
    if "supplier_id" in changes and changes["supplier_id"] is not None:
        scoped_supplier(changes["supplier_id"], membership.business_id, db, active=True)
        order.supplier_id = changes["supplier_id"]
    if "expected_delivery_date" in changes:
        order.expected_delivery_date = changes["expected_delivery_date"]
    if "notes" in changes:
        order.notes = changes["notes"]
    if "lines" in changes and changes["lines"] is not None:
        db.execute(delete(PurchaseOrderLine).where(
            PurchaseOrderLine.purchase_order_id == order.id, PurchaseOrderLine.business_id == membership.business_id,
        ))
        for line in changes["lines"]:
            product_id = line.get("product_id")
            if product_id:
                db_item = db.scalar(select(InventoryItem).where(
                    InventoryItem.id == product_id, InventoryItem.business_id == membership.business_id,
                    InventoryItem.is_active.is_(True),
                ))
                if not db_item:
                    raise HTTPException(status_code=404, detail="Linked inventory item not found.")
            db.add(PurchaseOrderLine(
                id=str(uuid.uuid4()), purchase_order_id=order.id, business_id=membership.business_id,
                description=line["description"].strip(), quantity_ordered=line["quantity"],
                quantity_received=Decimal("0"), unit_price=line["unit_price"],
                tax_rate=line.get("tax_rate", Decimal("0")), product_id=product_id,
            ))
    order.updated_at = datetime.now(timezone.utc)
    add_event(db, order, user, "updated", {"fields": sorted(changes.keys())})
    db.commit()
    db.refresh(order)
    return order_payload(order, db, include_events=True)


@router.post("/purchase-orders/{order_id}/submit")
def submit_purchase_order(order_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    require_manager(membership)
    order = scoped_order(order_id, membership.business_id, db)
    if order.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft purchase orders can be submitted.")
    line_count = db.scalar(select(func.count(PurchaseOrderLine.id)).where(
        PurchaseOrderLine.purchase_order_id == order.id, PurchaseOrderLine.business_id == membership.business_id,
    )) or 0
    if line_count == 0:
        raise HTTPException(status_code=422, detail="Add at least one line before submitting this purchase order.")
    order.status = "submitted"
    order.submitted_at = datetime.now(timezone.utc)
    order.updated_at = order.submitted_at
    add_event(db, order, user, "submitted", {"status": "submitted"})
    db.commit()
    db.refresh(order)
    return order_payload(order, db, include_events=True)


@router.post("/purchase-orders/{order_id}/receive")
def receive_purchase_order(order_id: str, payload: GoodsReceiptCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    require_manager(membership)
    order = scoped_order(order_id, membership.business_id, db)
    if order.status not in {"submitted", "partially_received"}:
        raise HTTPException(status_code=409, detail="Only submitted purchase orders can receive goods.")
    line_ids = [row.line_id for row in payload.lines]
    if len(line_ids) != len(set(line_ids)):
        raise HTTPException(status_code=422, detail="A purchase order line may appear only once per receipt.")
    lines = db.scalars(select(PurchaseOrderLine).where(
        PurchaseOrderLine.purchase_order_id == order.id,
        PurchaseOrderLine.business_id == membership.business_id,
        PurchaseOrderLine.id.in_(line_ids),
    )).all()
    by_id = {line.id: line for line in lines}
    if len(by_id) != len(line_ids):
        raise HTTPException(status_code=404, detail="One or more purchase order lines were not found.")
    received_details = []
    for receipt in payload.lines:
        line = by_id[receipt.line_id]
        new_received = Decimal(line.quantity_received) + receipt.quantity
        if new_received > Decimal(line.quantity_ordered):
            raise HTTPException(status_code=422, detail=f"Received quantity exceeds the outstanding quantity for '{line.description}'.")
        line.quantity_received = new_received
        received_details.append({
            "line_id": line.id, "description": line.description,
            "quantity_received": f"{receipt.quantity:.3f}", "total_received": f"{new_received:.3f}",
        })
    all_lines = db.scalars(select(PurchaseOrderLine).where(
        PurchaseOrderLine.purchase_order_id == order.id, PurchaseOrderLine.business_id == membership.business_id,
    )).all()
    fully_received = all(Decimal(line.quantity_received) >= Decimal(line.quantity_ordered) for line in all_lines)
    order.status = "received" if fully_received else "partially_received"
    if fully_received:
        order.received_at = datetime.now(timezone.utc)
    order.updated_at = datetime.now(timezone.utc)
    location = payload.location.strip()
    if not location:
        raise HTTPException(status_code=422, detail="Enter a stock location.")
    receipt_event = add_event(db, order, user, "goods_received", {
        "lines": received_details, "note": payload.note, "location": location,
    }, idempotency_key=payload.idempotency_key)
    for receipt in payload.lines:
        line = by_id[receipt.line_id]
        if line.product_id:
            db.add(InventoryMovement(
                id=str(uuid.uuid4()), business_id=membership.business_id,
                inventory_item_id=line.product_id, movement_type="purchase_receipt",
                quantity_delta=receipt.quantity, location=location,
                source_type="purchase_order", source_id=order.id,
                source_event_id=receipt_event.id, source_line_id=line.id,
                note=f"Goods received against {order.reference}",
                created_by_user_id=user.id,
            ))
    db.commit()
    db.refresh(order)
    return order_payload(order, db, include_events=True)


@router.post("/purchase-orders/{order_id}/cancel")
def cancel_purchase_order(order_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = membership_for(user, db)
    require_manager(membership)
    order = scoped_order(order_id, membership.business_id, db)
    if order.status not in {"draft", "submitted"}:
        raise HTTPException(status_code=409, detail="This purchase order can no longer be cancelled.")
    received = db.scalar(select(func.count(PurchaseOrderLine.id)).where(
        PurchaseOrderLine.purchase_order_id == order.id,
        PurchaseOrderLine.business_id == membership.business_id,
        PurchaseOrderLine.quantity_received > 0,
    )) or 0
    if received:
        raise HTTPException(status_code=409, detail="A purchase order with received goods cannot be cancelled.")
    order.status = "cancelled"
    order.updated_at = datetime.now(timezone.utc)
    add_event(db, order, user, "cancelled", {"status": "cancelled"})
    db.commit()
    db.refresh(order)
    return order_payload(order, db, include_events=True)
