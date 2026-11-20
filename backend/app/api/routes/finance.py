from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.business_context import get_business_membership
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import FinanceTransaction, Membership, POSTransaction, User
from app.schemas_finance import FinanceSummaryResponse, FinanceTransactionCreate, FinanceTransactionResponse, FinanceTransactionUpdate

router = APIRouter(prefix="/finance", tags=["finance"])
ZERO = Decimal("0.00")
BUSINESS_TIMEZONE = ZoneInfo("Africa/Johannesburg")

def current_membership(user: User, db: Session) -> Membership:
    membership = get_business_membership(user, db)
    if not membership:
        raise HTTPException(status_code=403, detail="A business workspace is required.")
    return membership

def require_finance_reader(membership: Membership) -> None:
    if membership.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="You do not have permission to view this business's financial records.")

def require_finance_admin(membership: Membership) -> None:
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only business owners or administrators can add or delete financial records.")

@router.get("/transactions", response_model=list[FinanceTransactionResponse])
def list_transactions(
    kind: str | None = Query(default=None, pattern="^(income|expense)$"),
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_finance_reader(membership)
    statement = select(FinanceTransaction).where(FinanceTransaction.business_id == membership.business_id)
    if kind:
        statement = statement.where(FinanceTransaction.kind == kind)
    if year:
        statement = statement.where(FinanceTransaction.occurred_on >= date(year, 1, 1), FinanceTransaction.occurred_on < date(year + 1, 1, 1))
    statement = statement.order_by(FinanceTransaction.occurred_on.desc(), FinanceTransaction.created_at.desc())
    return list(db.scalars(statement).all())

@router.post("/transactions", response_model=FinanceTransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: FinanceTransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_finance_admin(membership)
    if payload.kind != "expense" and any((payload.payee_name, payload.due_on, payload.payment_method, payload.tax_amount)):
        raise HTTPException(status_code=422, detail="Payee, due date, payment method and supplier VAT details are only valid for expenses.")
    if payload.status == "unpaid" and payload.paid_on is not None:
        raise HTTPException(status_code=422, detail="An unpaid record cannot have a paid date.")
    record = FinanceTransaction(
        business_id=membership.business_id,
        created_by_user_id=user.id,
        kind=payload.kind,
        category=payload.category,
        description=payload.description,
        amount=payload.amount,
        currency="ZAR",
        status=payload.status,
        occurred_on=payload.occurred_on,
        reference=payload.reference,
        notes=payload.notes,
        payee_name=payload.payee_name,
        due_on=payload.due_on,
        paid_on=payload.paid_on or (datetime.now(BUSINESS_TIMEZONE).date() if payload.status == "paid" else None),
        payment_method=payload.payment_method,
        tax_amount=payload.tax_amount,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

@router.patch("/transactions/{transaction_id}", response_model=FinanceTransactionResponse)
def update_transaction(
    transaction_id: str,
    payload: FinanceTransactionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_finance_admin(membership)
    record = db.scalar(select(FinanceTransaction).where(
        FinanceTransaction.id == transaction_id,
        FinanceTransaction.business_id == membership.business_id,
    ))
    if not record:
        raise HTTPException(status_code=404, detail="Financial record not found.")
    changes = payload.model_dump(exclude_unset=True)
    if record.kind != "expense" and any(key in changes for key in {"due_on", "payee_name", "payment_method", "tax_amount"}):
        raise HTTPException(status_code=422, detail="Expense details can only be changed on expense records.")
    for key, value in changes.items():
        setattr(record, key, value)
    if "status" in changes:
        if record.status == "paid" and "paid_on" not in changes and record.paid_on is None:
            record.paid_on = datetime.now(BUSINESS_TIMEZONE).date()
        elif record.status == "unpaid":
            record.paid_on = None
    db.commit()
    db.refresh(record)
    return record

@router.delete("/transactions/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_finance_admin(membership)
    record = db.scalar(select(FinanceTransaction).where(
        FinanceTransaction.id == transaction_id,
        FinanceTransaction.business_id == membership.business_id,
    ))
    if not record:
        raise HTTPException(status_code=404, detail="Financial record not found.")
    db.delete(record)
    db.commit()
    return None

@router.get("/summary", response_model=FinanceSummaryResponse)
def finance_summary(
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = current_membership(user, db)
    require_finance_reader(membership)
    selected_year = year or date.today().year
    records = list(db.scalars(select(FinanceTransaction).where(
        FinanceTransaction.business_id == membership.business_id,
        FinanceTransaction.occurred_on >= date(selected_year, 1, 1),
        FinanceTransaction.occurred_on < date(selected_year + 1, 1, 1),
    )).all())
    income = ZERO
    expenses = ZERO
    outstanding_income = ZERO
    unpaid_expenses = ZERO
    monthly = defaultdict(lambda: {"income": ZERO, "expenses": ZERO})
    pos_sales = ZERO
    pos_refunds = ZERO
    pos_transaction_count = 0
    # Reporting periods follow South African business dates, not UTC calendar dates.
    period_start = datetime(selected_year, 1, 1, tzinfo=BUSINESS_TIMEZONE).astimezone(timezone.utc)
    period_end = datetime(selected_year + 1, 1, 1, tzinfo=BUSINESS_TIMEZONE).astimezone(timezone.utc)
    pos_rows = db.scalars(select(POSTransaction).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.occurred_at >= period_start,
        POSTransaction.occurred_at < period_end,
        POSTransaction.currency == "ZAR",
    )).all()
    for pos_record in pos_rows:
        occurred_at = pos_record.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        business_month = occurred_at.astimezone(BUSINESS_TIMEZONE).month
        if pos_record.transaction_type == "sale":
            pos_sales += Decimal(pos_record.net_amount)
            monthly[business_month]["income"] += Decimal(pos_record.net_amount)
            pos_transaction_count += 1
        elif pos_record.transaction_type == "refund":
            pos_refunds += Decimal(pos_record.net_amount)
            monthly[business_month]["income"] -= Decimal(pos_record.net_amount)
            pos_transaction_count += 1
    for record in records:
        amount = Decimal(record.amount)
        if record.kind == "income":
            if record.status == "paid":
                income += amount
                monthly[record.occurred_on.month]["income"] += amount
            else:
                outstanding_income += amount
        elif record.status == "paid":
            expenses += amount
            monthly[record.occurred_on.month]["expenses"] += amount
        else:
            unpaid_expenses += amount
    return FinanceSummaryResponse(
        year=selected_year,
        income_total=f"{income + pos_sales - pos_refunds:.2f}",
        manual_income_total=f"{income:.2f}",
        pos_sales_total=f"{pos_sales:.2f}",
        pos_refunds_total=f"{pos_refunds:.2f}",
        pos_net_income_total=f"{pos_sales - pos_refunds:.2f}",
        pos_transaction_count=pos_transaction_count,
        expense_total=f"{expenses:.2f}",
        net_total=f"{income + pos_sales - pos_refunds - expenses:.2f}",
        outstanding_income=f"{outstanding_income:.2f}",
        unpaid_expenses=f"{unpaid_expenses:.2f}",
        transaction_count=len(records),
        months=[
            {"month": month, "income": f"{monthly[month]['income']:.2f}", "expenses": f"{monthly[month]['expenses']:.2f}"}
            for month in range(1, 13)
        ],
    )
