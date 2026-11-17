import hashlib
import hmac
import secrets
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import Membership, POSConnection, POSTransaction, User
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
        business_id=connection.business_id, connection_id=connection.id,
        external_transaction_id=payload.external_transaction_id,
        branch_name=payload.branch_name, till_name=payload.till_name,
        transaction_type=payload.transaction_type, occurred_at=occurred_at,
        currency=payload.currency.upper(), gross_amount=payload.gross_amount,
        discount_amount=payload.discount_amount, tax_amount=payload.tax_amount,
        net_amount=payload.net_amount, payment_method=payload.payment_method,
    )
    db.add(record)
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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_reader(membership)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(select(POSTransaction.transaction_type, func.sum(POSTransaction.net_amount), func.count(POSTransaction.id)).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.occurred_at >= since,
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
        days=days, transaction_count=transaction_count,
        sales_total=f"{sales:.2f}", refunds_total=f"{refunds:.2f}",
        net_sales=f"{sales - refunds:.2f}", void_count=void_count,
    )
