from collections import defaultdict
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import FinanceTransaction, Membership, User
from app.schemas_finance import FinanceSummaryResponse, FinanceTransactionCreate, FinanceTransactionResponse

router = APIRouter(prefix="/finance", tags=["finance"])
ZERO = Decimal("0.00")

def current_membership(user: User, db: Session) -> Membership:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership:
        raise HTTPException(status_code=403, detail="A business workspace is required.")
    return membership

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
    )
    db.add(record)
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
        income_total=f"{income:.2f}",
        expense_total=f"{expenses:.2f}",
        net_total=f"{income - expenses:.2f}",
        outstanding_income=f"{outstanding_income:.2f}",
        unpaid_expenses=f"{unpaid_expenses:.2f}",
        transaction_count=len(records),
        months=[
            {"month": month, "income": f"{monthly[month]['income']:.2f}", "expenses": f"{monthly[month]['expenses']:.2f}"}
            for month in range(1, 13)
        ],
    )
