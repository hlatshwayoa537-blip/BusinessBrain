from collections import defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import FinanceTransaction, Invoice, Membership, POSTransaction, User
from app.inventory_costing import inventory_costing_summary

router = APIRouter(prefix="/financial-reports", tags=["financial reports"])
TZ = ZoneInfo("Africa/Johannesburg")
ZERO = Decimal("0.00")


def membership_for(user: User, db: Session) -> Membership:
    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at)
    )
    if not membership:
        raise HTTPException(status_code=403, detail="A business workspace is required.")
    if membership.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="You do not have permission to view financial reports.")
    return membership


def period(year: int, month: int | None = None):
    start_date = date(year, month or 1, 1)
    if month:
        end_date = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    else:
        end_date = date(year + 1, 1, 1)
    start = datetime.combine(start_date, time.min, tzinfo=TZ).astimezone(timezone.utc)
    end = datetime.combine(end_date, time.min, tzinfo=TZ).astimezone(timezone.utc)
    return start_date, end_date, start, end


def money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


def report_sources(db: Session, business_id: str, year: int, month: int | None):
    start_date, end_date, start_utc, end_utc = period(year, month)
    manual = list(db.scalars(select(FinanceTransaction).where(
        FinanceTransaction.business_id == business_id,
        FinanceTransaction.occurred_on >= start_date,
        FinanceTransaction.occurred_on < end_date,
        FinanceTransaction.currency == "ZAR",
    )).all())
    pos = list(db.scalars(select(POSTransaction).where(
        POSTransaction.business_id == business_id,
        POSTransaction.occurred_at >= start_utc,
        POSTransaction.occurred_at < end_utc,
        POSTransaction.currency == "ZAR",
    )).all())
    return start_date, end_date, manual, pos


@router.get("/profit-loss")
def profit_loss(
    year: int = Query(ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    start_date, end_date, manual, pos = report_sources(db, membership.business_id, year, month)
    pos_sales = sum((Decimal(row.net_amount) for row in pos if row.transaction_type == "sale"), ZERO)
    pos_refunds = sum((abs(Decimal(row.net_amount)) for row in pos if row.transaction_type == "refund"), ZERO)
    manual_income = sum((Decimal(row.amount) for row in manual if row.kind == "income" and row.status == "paid"), ZERO)
    manual_expenses = sum((Decimal(row.amount) for row in manual if row.kind == "expense" and row.status == "paid"), ZERO)
    outstanding_income = sum((Decimal(row.amount) for row in manual if row.kind == "income" and row.status != "paid"), ZERO)
    unpaid_expenses = sum((Decimal(row.amount) for row in manual if row.kind == "expense" and row.status != "paid"), ZERO)
    expense_categories = defaultdict(lambda: ZERO)
    for row in manual:
        if row.kind == "expense" and row.status == "paid":
            expense_categories[row.category] += Decimal(row.amount)
    revenue = pos_sales - pos_refunds + manual_income
    start_utc = datetime.combine(start_date, time.min, tzinfo=TZ).astimezone(timezone.utc)
    end_utc = datetime.combine(end_date, time.min, tzinfo=TZ).astimezone(timezone.utc)
    costing = inventory_costing_summary(db, membership.business_id, start_utc, end_utc)
    cogs_complete = costing["complete"] and pos_refunds == ZERO
    cogs_status = "complete" if cogs_complete else ("incomplete" if costing["sales_transaction_count"] or pos_refunds > ZERO else "not_available")
    gross_profit = revenue - costing["cogs"] if cogs_complete else None
    return {
        "period": {"start": start_date.isoformat(), "end_exclusive": end_date.isoformat(), "timezone": "Africa/Johannesburg"},
        "currency": "ZAR",
        "revenue": {"pos_sales": money(pos_sales), "pos_refunds": money(pos_refunds), "manual_paid_income": money(manual_income), "total": money(revenue)},
        "expenses": {"manual_paid_expenses": money(manual_expenses), "by_category": [{"category": key, "amount": money(value)} for key, value in sorted(expense_categories.items())], "total": money(manual_expenses)},
        "cost_of_goods_sold": money(costing["cogs"]) if cogs_complete else None,
        "gross_profit": money(gross_profit) if gross_profit is not None else None,
        "gross_profit_status": cogs_status,
        "net_result": money(gross_profit - manual_expenses) if gross_profit is not None else None,
        "net_result_before_cogs": money(revenue - manual_expenses),
        "not_included": {"unpaid_manual_income": money(outstanding_income), "unpaid_manual_expenses": money(unpaid_expenses), "inventory_cost_of_goods_sold": None if cogs_complete else cogs_status},
        "source_counts": {"pos_transactions": len(pos), "manual_finance_records": len(manual)},
        "data_quality": {"pos_feed_received": len(pos) > 0, "expenses_are_complete": False, "inventory_costing_complete": cogs_status, "uncosted_pos_lines": costing["uncosted_line_count"], "note": "COGS is included only when every recorded POS sale line has a linked inventory item and receipt cost, and no POS refunds require cost reversal. Missing costs are never treated as zero. Supplier purchase orders are not treated as paid expenses."},
    }


@router.get("/cash-flow")
def cash_flow(
    year: int = Query(ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    start_date, end_date, manual, pos = report_sources(db, membership.business_id, year, month)
    pos_inflows = sum((Decimal(row.net_amount) for row in pos if row.transaction_type == "sale"), ZERO)
    pos_refunds = sum((abs(Decimal(row.net_amount)) for row in pos if row.transaction_type == "refund"), ZERO)
    paid_income = sum((Decimal(row.amount) for row in manual if row.kind == "income" and row.status == "paid"), ZERO)
    paid_expenses = sum((Decimal(row.amount) for row in manual if row.kind == "expense" and row.status == "paid"), ZERO)
    return {
        "period": {"start": start_date.isoformat(), "end_exclusive": end_date.isoformat(), "timezone": "Africa/Johannesburg"},
        "currency": "ZAR",
        "recorded_operating_flows": {
            "pos_sales_received": money(pos_inflows),
            "pos_refunds_recorded": money(pos_refunds),
            "manual_paid_income": money(paid_income),
            "manual_paid_expenses": money(paid_expenses),
            "net_recorded_flow": money(pos_inflows - pos_refunds + paid_income - paid_expenses),
        },
        "bank_reconciliation": {"status": "not_connected", "balance": None, "message": "No bank feed or bank statement reconciliation is connected. POS takings are not represented as bank-settled funds."},
        "source_counts": {"pos_transactions": len(pos), "manual_finance_records": len(manual)},
    }


@router.get("/vat")
def vat_summary(
    year: int = Query(ge=2000, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    start_date, end_date, _, _ = period(year, month)
    invoices = list(db.scalars(select(Invoice).where(
        Invoice.business_id == membership.business_id,
        Invoice.issue_date >= start_date,
        Invoice.issue_date < end_date,
        Invoice.status.notin_({"draft", "cancelled"}),
        Invoice.currency == "ZAR",
    )).all())
    output_vat = sum((Decimal(invoice.tax_total) for invoice in invoices), ZERO)
    return {
        "period": {"start": start_date.isoformat(), "end_exclusive": end_date.isoformat(), "timezone": "Africa/Johannesburg"},
        "currency": "ZAR",
        "output_vat_on_issued_invoices": money(output_vat),
        "issued_invoice_count": len(invoices),
        "input_vat": None,
        "input_vat_status": "not_tracked",
        "estimated_vat_payable": None,
        "message": "Input VAT cannot be calculated reliably yet: supplier tax invoices and verified VAT amounts on paid purchases are not recorded. This is a management summary, not a VAT return or tax advice.",
        "source": "Issued VEXION invoices only; POS tax and supplier purchase orders are not included in this VAT figure.",
    }
