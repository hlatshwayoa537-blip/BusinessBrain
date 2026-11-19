import csv
import hashlib
import io
import hmac
import secrets
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import InventoryItem, InventoryMovement, Membership, POSConnection, POSTransaction, POSTransactionLine, User
from app.inventory_costing import current_weighted_average_cost
from app.schemas_pos import POSConnectionCreate, POSConnectionCreated, POSConnectionResponse, POSIngestTransaction, POSTransactionResponse, POSSalesSummary

router = APIRouter(prefix="/pos", tags=["POS integrations"])
ZERO = Decimal("0.00")

def current_membership(user: User, db: Session) -> Membership:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership:
        raise HTTPException(status_code=403, detail="A business workspace is required.")
    return membership

def require_reader(membership: Membership) -> None:
    if membership.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="You do not have permission to view POS data.")

def require_admin(membership: Membership) -> None:
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only business owners or administrators can manage POS connections.")

def secret_digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()

@router.get("/connections", response_model=list[POSConnectionResponse])
def list_connections(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = current_membership(user, db)
    require_reader(membership)
    rows = db.scalars(select(POSConnection).where(POSConnection.business_id == membership.business_id).order_by(POSConnection.created_at.desc())).all()
    return list(rows)

@router.post("/connections", response_model=POSConnectionCreated, status_code=status.HTTP_201_CREATED)
def create_connection(payload: POSConnectionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = current_membership(user, db)
    require_admin(membership)
    secret = secrets.token_urlsafe(32)
    connection = POSConnection(
        business_id=membership.business_id,
        created_by_user_id=user.id,
        provider_name=payload.provider_name,
        display_name=payload.display_name,
        integration_method=payload.integration_method,
        status="pending",
        secret_hash=secret_digest(secret),
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return POSConnectionCreated(
        id=connection.id, provider_name=connection.provider_name, display_name=connection.display_name,
        integration_method=connection.integration_method, status=connection.status,
        created_at=connection.created_at, last_received_at=connection.last_received_at, webhook_secret=secret,
    )

@router.post("/connections/{connection_id}/rotate-secret")
def rotate_connection_secret(connection_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = current_membership(user, db)
    require_admin(membership)
    connection = db.scalar(select(POSConnection).where(POSConnection.id == connection_id, POSConnection.business_id == membership.business_id))
    if not connection or connection.status == "disabled":
        raise HTTPException(status_code=404, detail="Active POS connection not found.")
    secret = secrets.token_urlsafe(32)
    connection.secret_hash = secret_digest(secret)
    db.commit()
    return {"webhook_secret": secret}

@router.post("/connections/{connection_id}/disable", response_model=POSConnectionResponse)
def disable_connection(connection_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = current_membership(user, db)
    require_admin(membership)
    connection = db.scalar(select(POSConnection).where(POSConnection.id == connection_id, POSConnection.business_id == membership.business_id))
    if not connection:
        raise HTTPException(status_code=404, detail="POS connection not found.")
    connection.status = "disabled"
    connection.disabled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(connection)
    return connection

@router.post("/ingest/{connection_id}", response_model=POSTransactionResponse, status_code=status.HTTP_201_CREATED)
def ingest_transaction(
    connection_id: str,
    payload: POSIngestTransaction,
    x_vexion_secret: str | None = Header(default=None, alias="X-Vexion-Secret"),
    db: Session = Depends(get_db),
):
    connection = db.get(POSConnection, connection_id)
    if not connection or connection.status == "disabled" or not x_vexion_secret:
        raise HTTPException(status_code=401, detail="Valid POS connection credentials are required.")
    if not hmac.compare_digest(connection.secret_hash, secret_digest(x_vexion_secret)):
        raise HTTPException(status_code=401, detail="Valid POS connection credentials are required.")
    occurred_at = payload.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    record = POSTransaction(
        id=str(uuid.uuid4()), business_id=connection.business_id, connection_id=connection.id,
        external_transaction_id=payload.external_transaction_id,
        branch_name=payload.branch_name, till_name=payload.till_name,
        transaction_type=payload.transaction_type, occurred_at=occurred_at,
        currency=payload.currency.upper(), gross_amount=payload.gross_amount,
        discount_amount=payload.discount_amount, tax_amount=payload.tax_amount,
        net_amount=payload.net_amount, payment_method=payload.payment_method,
    )
    db.add(record)
    stock_location = (payload.branch_name or "").strip()[:120] or "Main"
    for line_number, item in enumerate(payload.items, start=1):
        sku = item.sku.strip() if item.sku and item.sku.strip() else None
        inventory_item = None
        if sku:
            inventory_item = db.scalar(select(InventoryItem).where(
                InventoryItem.business_id == connection.business_id,
                func.lower(InventoryItem.sku) == sku.lower(),
                InventoryItem.is_active.is_(True),
            ))
        line_total = item.quantity * item.unit_price
        line = POSTransactionLine(
            id=str(uuid.uuid4()), transaction_id=record.id, business_id=connection.business_id,
            line_number=line_number, sku=sku, description=item.description,
            quantity=item.quantity, unit_price=item.unit_price, line_total=line_total,
            inventory_item_id=inventory_item.id if inventory_item else None,
        )
        db.add(line)
        if record.transaction_type == "sale" and inventory_item:
            weighted_unit_cost = current_weighted_average_cost(db, connection.business_id, inventory_item.id, stock_location, item.quantity)
            db.add(InventoryMovement(
                id=str(uuid.uuid4()), business_id=connection.business_id,
                inventory_item_id=inventory_item.id, movement_type="pos_sale",
                quantity_delta=-item.quantity, location=stock_location,
                source_type="pos_transaction", source_id=record.id,
                source_event_id=record.id, source_line_id=line.id, unit_cost=weighted_unit_cost,
                note=f"POS sale {record.external_transaction_id}",
                created_by_user_id=connection.created_by_user_id,
            ))
    connection.last_received_at = datetime.now(timezone.utc)
    connection.status = "active"
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This POS transaction has already been received.") from None
    db.refresh(record)
    return record

@router.get("/transactions", response_model=list[POSTransactionResponse])
def list_transactions(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_reader(membership)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    statement = select(POSTransaction).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.occurred_at >= since,
    ).order_by(POSTransaction.occurred_at.desc()).limit(limit)
    return list(db.scalars(statement).all())

@router.get("/summary", response_model=POSSalesSummary)
def sales_summary(
    days: int = Query(default=7, ge=1, le=365),
    currency: str = Query(default="ZAR", pattern="^[A-Za-z]{3}$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_reader(membership)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(select(POSTransaction.transaction_type, func.sum(POSTransaction.net_amount), func.count(POSTransaction.id)).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.occurred_at >= since,
        POSTransaction.currency == currency.upper(),
    ).group_by(POSTransaction.transaction_type)).all()
    sales = ZERO
    refunds = ZERO
    void_count = 0
    transaction_count = 0
    for kind, total, count in rows:
        transaction_count += count
        if kind == "sale":
            sales += Decimal(total or 0)
        elif kind == "refund":
            refunds += Decimal(total or 0)
        elif kind == "void":
            void_count += count
    return POSSalesSummary(
        currency=currency.upper(), days=days, transaction_count=transaction_count,
        sales_total=f"{sales:.2f}", refunds_total=f"{refunds:.2f}",
        net_sales=f"{sales - refunds:.2f}", void_count=void_count,
    )


@router.get("/analytics/daily")
def daily_sales_analytics(
    days: int = Query(default=30, ge=1, le=365),
    currency: str = Query(default="ZAR", pattern="^[A-Za-z]{3}$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_reader(membership)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day_expr = func.date(POSTransaction.occurred_at)
    rows = db.execute(select(day_expr, POSTransaction.transaction_type, func.sum(POSTransaction.net_amount), func.count(POSTransaction.id)).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.occurred_at >= since,
        POSTransaction.currency == currency.upper(),
    ).group_by(day_expr, POSTransaction.transaction_type).order_by(day_expr)).all()
    grouped = {}
    for day_value, kind, total, count in rows:
        day_key = day_value.isoformat() if hasattr(day_value, "isoformat") else str(day_value)
        item = grouped.setdefault(day_key, {"date": day_key, "sales": Decimal("0.00"), "refunds": Decimal("0.00"), "net_sales": Decimal("0.00"), "transaction_count": 0, "void_count": 0})
        item["transaction_count"] += count
        if kind == "sale":
            item["sales"] += Decimal(total or 0)
        elif kind == "refund":
            item["refunds"] += Decimal(total or 0)
        elif kind == "void":
            item["void_count"] += count
    output = []
    for day_key in sorted(grouped):
        item = grouped[day_key]
        item["net_sales"] = item["sales"] - item["refunds"]
        output.append({
            "date": item["date"], "sales": f"{item['sales']:.2f}", "refunds": f"{item['refunds']:.2f}",
            "net_sales": f"{item['net_sales']:.2f}", "transaction_count": item["transaction_count"], "void_count": item["void_count"],
        })
    return {"currency": currency.upper(), "days": days, "items": output}

@router.get("/analytics/branches")
def branch_sales_analytics(
    days: int = Query(default=30, ge=1, le=365),
    currency: str = Query(default="ZAR", pattern="^[A-Za-z]{3}$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_reader(membership)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    branch_expr = func.coalesce(POSTransaction.branch_name, "Unassigned")
    rows = db.execute(select(branch_expr, POSTransaction.transaction_type, func.sum(POSTransaction.net_amount), func.count(POSTransaction.id)).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.occurred_at >= since,
        POSTransaction.currency == currency.upper(),
    ).group_by(branch_expr, POSTransaction.transaction_type)).all()
    grouped = {}
    for branch, kind, total, count in rows:
        item = grouped.setdefault(branch, {"branch": branch, "sales": Decimal("0.00"), "refunds": Decimal("0.00"), "net_sales": Decimal("0.00"), "transaction_count": 0, "void_count": 0})
        item["transaction_count"] += count
        if kind == "sale":
            item["sales"] += Decimal(total or 0)
        elif kind == "refund":
            item["refunds"] += Decimal(total or 0)
        elif kind == "void":
            item["void_count"] += count
    output = []
    for item in grouped.values():
        item["net_sales"] = item["sales"] - item["refunds"]
        output.append({
            "branch": item["branch"], "sales": f"{item['sales']:.2f}", "refunds": f"{item['refunds']:.2f}",
            "net_sales": f"{item['net_sales']:.2f}", "transaction_count": item["transaction_count"], "void_count": item["void_count"],
        })
    return {"currency": currency.upper(), "days": days, "items": sorted(output, key=lambda row: Decimal(row["net_sales"]), reverse=True)}

@router.get("/analytics/tills")
def till_sales_analytics(
    days: int = Query(default=30, ge=1, le=365),
    currency: str = Query(default="ZAR", pattern="^[A-Za-z]{3}$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_reader(membership)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    branch_expr = func.coalesce(POSTransaction.branch_name, "Unassigned")
    till_expr = func.coalesce(POSTransaction.till_name, "Unassigned")
    rows = db.execute(select(branch_expr, till_expr, POSTransaction.transaction_type, func.sum(POSTransaction.net_amount), func.count(POSTransaction.id)).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.occurred_at >= since,
        POSTransaction.currency == currency.upper(),
    ).group_by(branch_expr, till_expr, POSTransaction.transaction_type)).all()
    grouped = {}
    for branch, till, kind, total, count in rows:
        key = (branch, till)
        item = grouped.setdefault(key, {"branch": branch, "till": till, "sales": Decimal("0.00"), "refunds": Decimal("0.00"), "net_sales": Decimal("0.00"), "transaction_count": 0})
        item["transaction_count"] += count
        if kind == "sale":
            item["sales"] += Decimal(total or 0)
        elif kind == "refund":
            item["refunds"] += Decimal(total or 0)
    output = []
    for item in grouped.values():
        item["net_sales"] = item["sales"] - item["refunds"]
        output.append({"branch":item["branch"],"till":item["till"],"net_sales":f"{item['net_sales']:.2f}","transaction_count":item["transaction_count"]})
    return {"currency": currency.upper(), "days": days, "items": sorted(output, key=lambda row: Decimal(row["net_sales"]), reverse=True)}


@router.post("/connections/{connection_id}/import-csv")
def import_csv_transactions(
    connection_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Import an approved POS CSV export into the same idempotent transaction ledger."""
    membership = current_membership(user, db)
    require_admin(membership)
    connection = db.scalar(select(POSConnection).where(
        POSConnection.id == connection_id,
        POSConnection.business_id == membership.business_id,
    ))
    if not connection or connection.status == "disabled":
        raise HTTPException(status_code=404, detail="Active POS connection not found.")
    csv_text = payload.get("csv_text")
    mapping = payload.get("mapping")
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise HTTPException(status_code=422, detail="Choose a non-empty CSV file.")
    if len(csv_text.encode("utf-8")) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV files must be 5 MB or smaller.")
    if not isinstance(mapping, dict):
        raise HTTPException(status_code=422, detail="Column mapping is required.")
    required = ("external_transaction_id", "occurred_at", "gross_amount", "net_amount")
    if any(not isinstance(mapping.get(key), str) or not mapping[key].strip() for key in required):
        raise HTTPException(status_code=422, detail="Map transaction ID, date/time, gross amount and net amount.")
    try:
        reader = csv.DictReader(io.StringIO(csv_text.lstrip("\\ufeff")))
        headers = reader.fieldnames or []
        if not headers:
            raise HTTPException(status_code=422, detail="The CSV file must contain a header row.")
        if any(column not in headers for column in mapping.values() if column):
            raise HTTPException(status_code=422, detail="A mapped column is not present in the CSV file.")
        imported = 0
        duplicates = 0
        rejected = []
        seen = set()
        for line_number, row in enumerate(reader, start=2):
            if line_number > 5001:
                raise HTTPException(status_code=413, detail="A maximum of 5,000 transactions can be imported at once.")
            if not any((value or "").strip() for value in row.values()):
                continue
            try:
                def value(field, default=None):
                    column = mapping.get(field)
                    raw = row.get(column) if column else None
                    return raw.strip() if isinstance(raw, str) and raw.strip() else default
                transaction_id = value("external_transaction_id")
                if not transaction_id:
                    raise ValueError("Transaction ID is missing.")
                if transaction_id in seen:
                    duplicates += 1
                    continue
                seen.add(transaction_id)
                payload_data = {
                    "external_transaction_id": transaction_id,
                    "occurred_at": value("occurred_at"),
                    "transaction_type": (value("transaction_type", "sale") or "sale").lower(),
                    "currency": (value("currency", "ZAR") or "ZAR").upper(),
                    "gross_amount": value("gross_amount"),
                    "discount_amount": value("discount_amount", "0"),
                    "tax_amount": value("tax_amount", "0"),
                    "net_amount": value("net_amount"),
                    "branch_name": value("branch_name"),
                    "till_name": value("till_name"),
                    "payment_method": value("payment_method"),
                }
                clean = POSIngestTransaction.model_validate(payload_data)
                exists = db.scalar(select(POSTransaction.id).where(
                    POSTransaction.connection_id == connection.id,
                    POSTransaction.external_transaction_id == clean.external_transaction_id,
                ))
                if exists:
                    duplicates += 1
                    continue
                occurred_at = clean.occurred_at
                if occurred_at.tzinfo is None:
                    occurred_at = occurred_at.replace(tzinfo=timezone.utc)
                db.add(POSTransaction(
                    business_id=connection.business_id, connection_id=connection.id,
                    external_transaction_id=clean.external_transaction_id,
                    branch_name=clean.branch_name, till_name=clean.till_name,
                    transaction_type=clean.transaction_type, occurred_at=occurred_at,
                    currency=clean.currency.upper(), gross_amount=clean.gross_amount,
                    discount_amount=clean.discount_amount, tax_amount=clean.tax_amount,
                    net_amount=clean.net_amount, payment_method=clean.payment_method,
                ))
                imported += 1
            except Exception as exc:
                from pydantic import ValidationError
                if isinstance(exc, HTTPException):
                    raise
                reason = str(exc)
                if isinstance(exc, ValidationError):
                    reason = "; ".join(error["msg"] for error in exc.errors())
                rejected.append({"row": line_number, "reason": reason[:240]})
        if imported:
            connection.last_received_at = datetime.now(timezone.utc)
            connection.status = "active"
        db.commit()
        return {"imported": imported, "duplicates": duplicates, "rejected": rejected, "rows_processed": imported + duplicates + len(rejected)}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=422, detail="The CSV could not be processed. Check its delimiter and column headings.") from None
