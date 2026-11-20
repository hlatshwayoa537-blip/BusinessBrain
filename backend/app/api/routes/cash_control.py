from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.business_context import get_business_membership
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import (
    BankStatementImport, BankStatementTransaction, CustomerInvoicePayment,
    FinanceTransaction, Invoice, Membership, SupplierInvoicePayable, User,
)

router = APIRouter(prefix="/cash-control", tags=["cash control and liquidity"])
BUSINESS_TZ = ZoneInfo("Africa/Johannesburg")
ZERO = Decimal("0.00")


def membership_for(user: User, db: Session) -> Membership:
    membership = get_business_membership(user, db)
    if not membership or membership.role not in {"owner", "admin", "manager"}:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="A business workspace with finance access is required.")
    return membership


def fmt(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01')):.2f}"


@router.get("/overview")
def cash_control_overview(
    horizon_days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    today = datetime.now(BUSINESS_TZ).date()
    horizon_end = today + timedelta(days=horizon_days)
    business_id = membership.business_id

    # A bank balance is shown only when the newest imported transaction for
    # that account/currency actually carries a running balance.
    bank_rows = db.execute(
        select(BankStatementTransaction, BankStatementImport.account_label)
        .join(BankStatementImport, BankStatementImport.id == BankStatementTransaction.import_id)
        .where(BankStatementTransaction.business_id == business_id)
        .order_by(
            BankStatementImport.account_label.asc(),
            BankStatementTransaction.currency.asc(),
            BankStatementTransaction.transaction_date.desc(),
            BankStatementTransaction.created_at.desc(),
        )
    ).all()
    latest_by_account = {}
    for transaction, account_label in bank_rows:
        key = (account_label, transaction.currency)
        if key not in latest_by_account:
            latest_by_account[key] = transaction

    cash_accounts = []
    cash_totals = defaultdict(lambda: ZERO)
    known_cash_totals = defaultdict(lambda: ZERO)
    for (account_label, currency), transaction in latest_by_account.items():
        age_days = max(0, (today - transaction.transaction_date).days)
        balance = Decimal(transaction.running_balance) if transaction.running_balance is not None else None
        status = "available" if balance is not None and age_days <= 14 else (
            "stale" if balance is not None else "balance_not_supplied"
        )
        if balance is not None:
            known_cash_totals[currency] += balance
            if status == "available":
                cash_totals[currency] += balance
        cash_accounts.append({
            "account_label": account_label,
            "currency": currency,
            "balance": fmt(balance) if balance is not None else None,
            "balance_as_of": transaction.transaction_date.isoformat(),
            "age_days": age_days,
            "status": status,
            "source": "imported_bank_statement_running_balance",
        })

    # Customer invoices contribute only their remaining receivable balances.
    invoices = db.scalars(select(Invoice).where(
        Invoice.business_id == business_id,
        Invoice.status.in_(["sent", "overdue"]),
    )).all()
    invoice_ids = [invoice.id for invoice in invoices]
    paid_by_invoice = defaultdict(lambda: ZERO)
    if invoice_ids:
        payments = db.scalars(select(CustomerInvoicePayment).where(
            CustomerInvoicePayment.business_id == business_id,
            CustomerInvoicePayment.invoice_id.in_(invoice_ids),
        )).all()
        for payment in payments:
            paid_by_invoice[payment.invoice_id] += Decimal(payment.amount)

    ar_by_currency = defaultdict(lambda: ZERO)
    overdue_ar_by_currency = defaultdict(lambda: ZERO)
    ap_by_currency = defaultdict(lambda: ZERO)
    overdue_ap_by_currency = defaultdict(lambda: ZERO)
    unscheduled_ap_by_currency = defaultdict(lambda: ZERO)
    scheduled = defaultdict(lambda: {"inflows": ZERO, "outflows": ZERO, "items": []})

    for invoice in invoices:
        balance = max(ZERO, Decimal(invoice.total) - paid_by_invoice[invoice.id])
        if balance <= ZERO:
            continue
        currency = invoice.currency
        ar_by_currency[currency] += balance
        if invoice.due_date < today:
            overdue_ar_by_currency[currency] += balance
        elif invoice.due_date <= horizon_end:
            scheduled[(invoice.due_date, currency)]["inflows"] += balance
            scheduled[(invoice.due_date, currency)]["items"].append({
                "type": "customer_invoice_due",
                "description": f"Customer invoice {invoice.invoice_number}",
                "amount": fmt(balance),
                "direction": "inflow",
                "timing": "due_date_not_collection_guarantee",
            })

    payables = db.scalars(select(SupplierInvoicePayable).where(
        SupplierInvoicePayable.business_id == business_id,
        SupplierInvoicePayable.status.in_(["open", "partially_paid"]),
    )).all()
    for payable in payables:
        balance = max(ZERO, Decimal(payable.balance_due))
        if balance <= ZERO:
            continue
        currency = payable.currency
        ap_by_currency[currency] += balance
        if payable.due_date is None:
            unscheduled_ap_by_currency[currency] += balance
        elif payable.due_date < today:
            overdue_ap_by_currency[currency] += balance
        elif payable.due_date <= horizon_end:
            scheduled[(payable.due_date, currency)]["outflows"] += balance
            scheduled[(payable.due_date, currency)]["items"].append({
                "type": "supplier_invoice_due",
                "description": "Approved supplier invoice payable",
                "amount": fmt(balance),
                "direction": "outflow",
                "timing": "due_date_not_payment_confirmation",
            })

    # Unpaid manual expenses are kept separate from supplier-invoice payables
    # because the two ledgers may describe the same obligation.
    manual_unpaid_by_currency = defaultdict(lambda: ZERO)
    manual_unscheduled_by_currency = defaultdict(lambda: ZERO)
    manual_expenses = db.scalars(select(FinanceTransaction).where(
        FinanceTransaction.business_id == business_id,
        FinanceTransaction.kind == "expense",
        FinanceTransaction.status == "unpaid",
    )).all()
    for expense in manual_expenses:
        amount = Decimal(expense.amount)
        currency = expense.currency
        manual_unpaid_by_currency[currency] += amount
        if expense.due_on is None:
            manual_unscheduled_by_currency[currency] += amount
        elif today <= expense.due_on <= horizon_end:
            scheduled[(expense.due_on, currency)]["outflows"] += amount
            scheduled[(expense.due_on, currency)]["items"].append({
                "type": "manual_unpaid_expense",
                "description": expense.description,
                "amount": fmt(amount),
                "direction": "outflow",
                "timing": "recorded_due_date",
            })

    currency_set = set(ar_by_currency) | set(ap_by_currency) | set(manual_unpaid_by_currency) | set(known_cash_totals) | {account["currency"] for account in cash_accounts}
    summary = {}
    for currency in sorted(currency_set):
        known_accounts = [a for a in cash_accounts if a["currency"] == currency and a["balance"] is not None]
        fresh_accounts = [a for a in known_accounts if a["status"] == "available"]
        summary[currency] = {
            "bank_cash_balance": fmt(cash_totals[currency]) if fresh_accounts else None,
            "known_statement_balances": fmt(known_cash_totals[currency]) if known_accounts else None,
            "fresh_account_count": len(fresh_accounts),
            "account_count": len([a for a in cash_accounts if a["currency"] == currency]),
            "customer_receivables": fmt(ar_by_currency[currency]),
            "overdue_customer_receivables": fmt(overdue_ar_by_currency[currency]),
            "supplier_payables": fmt(ap_by_currency[currency]),
            "overdue_supplier_payables": fmt(overdue_ap_by_currency[currency]),
            "supplier_payables_without_due_date": fmt(unscheduled_ap_by_currency[currency]),
            "manual_unpaid_expenses": fmt(manual_unpaid_by_currency[currency]),
            "manual_expenses_without_due_date": fmt(manual_unscheduled_by_currency[currency]),
            "known_statement_balance_is_partial": len(fresh_accounts) != len([a for a in cash_accounts if a["currency"] == currency]),
        }

    forecast = []
    for (due_date, currency), values in sorted(scheduled.items(), key=lambda item: (item[0][0], item[0][1])):
        forecast.append({
            "date": due_date.isoformat(),
            "currency": currency,
            "expected_inflows": fmt(values["inflows"]),
            "expected_outflows": fmt(values["outflows"]),
            "net_scheduled_movement": fmt(values["inflows"] - values["outflows"]),
            "items": values["items"],
            "confidence": "scheduled_records_only",
        })

    return {
        "as_of": today.isoformat(),
        "horizon_days": horizon_days,
        "horizon_end": horizon_end.isoformat(),
        "cash_accounts": cash_accounts,
        "by_currency": summary,
        "scheduled_movements": forecast,
        "data_quality": {
            "bank_balance": "statement_evidence_only; no live bank connection",
            "receivables": "issued invoices less recorded customer receipts; collection is not guaranteed",
            "supplier_payables": "approved supplier invoice balances; due dates may be missing",
            "manual_expenses": "unpaid manual expense records; kept separate from supplier invoice payables to avoid silent double counting",
            "forecast": "scheduled due dates only; excludes overdue and undated items from dated projection; no assumed sales, collections or operating costs",
        },
    }
