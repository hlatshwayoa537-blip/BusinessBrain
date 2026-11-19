import uuid
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import InventoryItem, InventoryMovement, Membership, User
from app.inventory_costing import inventory_costing_summary

router = APIRouter(prefix="/inventory", tags=["inventory and stock"])
MANAGERS = {"owner", "admin", "manager"}
READERS = MANAGERS | {"staff", "employee"}
ZERO = Decimal("0.000")


def membership_for(user: User, db: Session) -> Membership:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership or membership.role not in READERS:
        raise HTTPException(status_code=403, detail="Inventory access is not available for this account.")
    return membership


def require_manager(membership: Membership) -> None:
    if membership.role not in MANAGERS:
        raise HTTPException(status_code=403, detail="Only an owner, administrator or manager can change inventory.")


def stock_at(db: Session, business_id: str, item_id: str, location: str) -> Decimal:
    value = db.scalar(select(func.coalesce(func.sum(InventoryMovement.quantity_delta), 0)).where(
        InventoryMovement.business_id == business_id,
        InventoryMovement.inventory_item_id == item_id,
        InventoryMovement.location == location,
    ))
    return Decimal(value or 0)


def item_payload(item: InventoryItem, db: Session) -> dict:
    rows = db.execute(select(
        InventoryMovement.location,
        func.coalesce(func.sum(InventoryMovement.quantity_delta), 0),
    ).where(
        InventoryMovement.business_id == item.business_id,
        InventoryMovement.inventory_item_id == item.id,
    ).group_by(InventoryMovement.location).order_by(InventoryMovement.location)).all()
    by_location = {location: f"{Decimal(quantity or 0):.3f}" for location, quantity in rows}
    total = sum((Decimal(value) for value in by_location.values()), ZERO)
    reorder = Decimal(item.reorder_level)
    return {
        "id": item.id, "sku": item.sku, "name": item.name, "unit": item.unit,
        "reorder_level": f"{reorder:.3f}", "is_active": item.is_active,
        "stock_total": f"{total:.3f}", "stock_by_location": by_location,
        "below_reorder_level": reorder > 0 and total <= reorder,
        "negative_stock": total < 0,
        "created_at": item.created_at, "updated_at": item.updated_at,
    }


def scoped_item(item_id: str, business_id: str, db: Session, active: bool = False) -> InventoryItem:
    item = db.scalar(select(InventoryItem).where(
        InventoryItem.id == item_id, InventoryItem.business_id == business_id,
    ))
    if not item or (active and not item.is_active):
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    return item


class InventoryItemCreate(BaseModel):
    sku: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=2, max_length=180)
    unit: str = Field(default="unit", min_length=1, max_length=24)
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)


class InventoryItemUpdate(BaseModel):
    sku: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, min_length=2, max_length=180)
    unit: str | None = Field(default=None, min_length=1, max_length=24)
    reorder_level: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    is_active: bool | None = None


class StockAdjustmentCreate(BaseModel):
    quantity_delta: Decimal = Field(max_digits=14, decimal_places=3)
    location: str = Field(default="Main", min_length=1, max_length=120)
    reason: str = Field(min_length=3, max_length=1000)


@router.get("/items")
def list_inventory_items(
    active_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    statement = select(InventoryItem).where(InventoryItem.business_id == membership.business_id)
    if active_only:
        statement = statement.where(InventoryItem.is_active.is_(True))
    items = db.scalars(statement.order_by(InventoryItem.name.asc()).limit(1000)).all()
    return [item_payload(item, db) for item in items]


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    payload: InventoryItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    require_manager(membership)
    name = payload.name.strip()
    sku = payload.sku.strip() if payload.sku else None
    if len(name) < 2 or (payload.sku is not None and not sku):
        raise HTTPException(status_code=422, detail="Enter a valid item name and SKU.")
    if sku and db.scalar(select(InventoryItem.id).where(
        InventoryItem.business_id == membership.business_id,
        func.lower(InventoryItem.sku) == sku.lower(),
    )):
        raise HTTPException(status_code=409, detail="This SKU is already used in this business.")
    item = InventoryItem(
        id=str(uuid.uuid4()), business_id=membership.business_id, sku=sku,
        name=name, unit=payload.unit.strip(), reorder_level=payload.reorder_level,
        is_active=True,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item_payload(item, db)


@router.patch("/items/{item_id}")
def update_inventory_item(
    item_id: str,
    payload: InventoryItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    require_manager(membership)
    item = scoped_item(item_id, membership.business_id, db)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
        if len(changes["name"]) < 2:
            raise HTTPException(status_code=422, detail="Item name must contain at least two non-space characters.")
    if "sku" in changes and changes["sku"] is not None:
        changes["sku"] = changes["sku"].strip() or None
        if changes["sku"] and db.scalar(select(InventoryItem.id).where(
            InventoryItem.business_id == membership.business_id,
            func.lower(InventoryItem.sku) == changes["sku"].lower(),
            InventoryItem.id != item.id,
        )):
            raise HTTPException(status_code=409, detail="This SKU is already used in this business.")
    if "unit" in changes and changes["unit"] is not None:
        changes["unit"] = changes["unit"].strip()
        if not changes["unit"]:
            raise HTTPException(status_code=422, detail="Unit cannot be blank.")
    for key, value in changes.items():
        setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item_payload(item, db)


@router.get("/movements")
def list_inventory_movements(
    item_id: str | None = None,
    location: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    statement = select(InventoryMovement).where(InventoryMovement.business_id == membership.business_id)
    if item_id:
        scoped_item(item_id, membership.business_id, db)
        statement = statement.where(InventoryMovement.inventory_item_id == item_id)
    if location:
        statement = statement.where(InventoryMovement.location == location)
    rows = db.scalars(statement.order_by(InventoryMovement.created_at.desc()).limit(limit)).all()
    item_ids = {row.inventory_item_id for row in rows}
    names = {}
    if item_ids:
        names = {item.id: item.name for item in db.scalars(select(InventoryItem).where(
            InventoryItem.business_id == membership.business_id,
            InventoryItem.id.in_(item_ids),
        )).all()}
    return [{
        "id": row.id, "inventory_item_id": row.inventory_item_id,
        "item_name": names.get(row.inventory_item_id, "Item unavailable"),
        "movement_type": row.movement_type, "quantity_delta": f"{Decimal(row.quantity_delta):.3f}",
        "location": row.location, "source_type": row.source_type, "source_id": row.source_id,
        "unit_cost": f"{Decimal(row.unit_cost):.4f}" if row.unit_cost is not None else None,
        "note": row.note, "created_by_user_id": row.created_by_user_id, "created_at": row.created_at,
    } for row in rows]


@router.post("/items/{item_id}/adjustments", status_code=status.HTTP_201_CREATED)
def create_stock_adjustment(
    item_id: str,
    payload: StockAdjustmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    require_manager(membership)
    item = db.scalar(select(InventoryItem).where(
        InventoryItem.id == item_id, InventoryItem.business_id == membership.business_id,
    ).with_for_update())
    if not item or not item.is_active:
        raise HTTPException(status_code=404, detail="Active inventory item not found.")
    delta = payload.quantity_delta
    if delta == 0:
        raise HTTPException(status_code=422, detail="Stock adjustment must be greater or less than zero.")
    location = payload.location.strip()
    if not location:
        raise HTTPException(status_code=422, detail="Enter a stock location.")
    current = stock_at(db, membership.business_id, item.id, location)
    if current + delta < 0:
        raise HTTPException(status_code=422, detail=f"Adjustment would make stock negative. Current recorded stock at {location}: {current:.3f} {item.unit}.")
    movement_type = "adjustment_in" if delta > 0 else "adjustment_out"
    movement = InventoryMovement(
        id=str(uuid.uuid4()), business_id=membership.business_id,
        inventory_item_id=item.id, movement_type=movement_type,
        quantity_delta=delta, location=location, source_type="manual_adjustment",
        note=payload.reason.strip(), created_by_user_id=user.id,
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    return {
        "id": movement.id, "inventory_item_id": item.id, "item_name": item.name,
        "movement_type": movement.movement_type, "quantity_delta": f"{Decimal(movement.quantity_delta):.3f}",
        "location": movement.location, "note": movement.note, "created_at": movement.created_at,
        "stock_after": f"{stock_at(db, membership.business_id, item.id, location):.3f}",
    }


@router.get("/profitability")
def inventory_profitability(
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    if membership.role not in MANAGERS:
        raise HTTPException(status_code=403, detail="Only an owner, administrator or manager can view profitability.")
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="End date must be on or after start date.")
    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=422, detail="Profitability periods cannot exceed 366 calendar days.")
    tz = ZoneInfo("Africa/Johannesburg")
    start_utc = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    end_exclusive = date.fromordinal(end_date.toordinal() + 1)
    end_utc = datetime.combine(end_exclusive, time.min, tzinfo=tz).astimezone(timezone.utc)
    summary = inventory_costing_summary(db, membership.business_id, start_utc, end_utc)
    rows = []
    for item in summary["products"]:
        cost_complete = item["uncosted_quantity"] == 0 and (item["costed_quantity"] > 0 or item["quantity_returned"] > 0)
        cogs = item["cogs"]
        revenue = item["line_revenue"]
        rows.append({
            "inventory_item_id": item["inventory_item_id"], "sku": item["sku"],
            "description": item["description"], "quantity_sold": f"{item['quantity_sold']:.3f}",
            "quantity_returned": f"{item['quantity_returned']:.3f}",
            "net_quantity_sold": f"{(item['quantity_sold'] - item['quantity_returned']):.3f}",
            "line_revenue_before_transaction_discounts": f"{revenue:.2f}",
            "refund_line_revenue": f"{item['refund_line_revenue']:.2f}",
            "net_line_revenue_before_transaction_discounts": f"{(revenue - item['refund_line_revenue']):.2f}",
            "costed_quantity": f"{item['costed_quantity']:.3f}",
            "uncosted_quantity": f"{item['uncosted_quantity']:.3f}",
            "cost_of_goods_sold": f"{cogs:.2f}" if cost_complete else None,
            "gross_profit_before_transaction_discounts": f"{revenue - item['refund_line_revenue'] - cogs:.2f}" if cost_complete else None,
            "cost_status": "complete" if cost_complete else "incomplete",
        })
    return {
        "period": {"start": start_date.isoformat(), "end_inclusive": end_date.isoformat(), "timezone": "Africa/Johannesburg"},
        "currency": "ZAR", "sales_transaction_count": summary["sales_transaction_count"],
        "sales_line_count": summary["sales_line_count"],
        "refund_transaction_count": summary["refund_transaction_count"],
        "uncosted_line_count": summary["uncosted_line_count"],
        "uncosted_quantity": f"{summary['uncosted_quantity']:.3f}",
        "cost_of_goods_sold": f"{summary['cogs']:.2f}" if summary["complete"] else None,
        "cost_status": "complete" if summary["complete"] else "incomplete",
        "products": rows,
        "limitations": [
            "Costs use quantity-weighted purchase receipt prices recorded before the POS sale was ingested.",
            "Opening stock without a recorded purchase receipt has no assumed cost.",
            "Transaction-level discounts are not allocated across product lines.",
            "Refunds reverse COGS only when linked to the original sale line and restocked; unlinked or uncosted refunds keep coverage incomplete.",
            "Historical POS sales received before cost snapshots were introduced remain uncosted.",
        ],
    }
