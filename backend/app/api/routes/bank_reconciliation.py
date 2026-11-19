import csv
import hashlib
import io
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import BankStatementImport, BankStatementTransaction, Membership, User

router = APIRouter(prefix="/bank-reconciliation", tags=["bank reconciliation"])
MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000


def membership_for(user: User, db: Session) -> Membership:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    if not membership:
        raise HTTPException(status_code=403, detail="A business workspace is required.")
    if membership.role not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="You do not have permission to view bank reconciliation.")
    return membership


def money(value):
    return f"{Decimal(value or 0):.2f}"


@router.post("/imports", status_code=status.HTTP_201_CREATED)
async def import_statement(
    request: Request,
    filename: str = Query(default="bank-statement.csv", max_length=180),
    account_label: str = Query(min_length=2, max_length=120),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = membership_for(user, db)
    raw = await request.body()
    if not raw or len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413 if len(raw) > MAX_BYTES else 400, detail="CSV must be non-empty and no larger than 5 MB.")
    try:
        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise ValueError("CSV header row is missing.")
        headers = {str(name).strip().lower(): name for name in reader.fieldnames if name}
        date_key = next((headers[k] for k in ("date", "transaction_date", "value_date") if k in headers), None)
        desc_key = next((headers[k] for k in ("description", "details", "narrative") if k in headers), None)
        amount_key = headers.get("amount")
        if not date_key or not desc_key or not amount_key:
            raise ValueError("Required columns: date, description and amount. Optional: reference, transaction_id, balance, currency.")
        ref_key = next((headers[k] for k in ("reference", "reference_number", "ref") if k in headers), None)
        id_key = next((headers[k] for k in ("transaction_id", "external_id", "id") if k in headers), None)
        balance_key = next((headers[k] for k in ("balance", "running_balance") if k in headers), None)
        currency_key = headers.get("currency")
        parsed = []
        for line_number, row in enumerate(reader, start=2):
            if line_number > MAX_ROWS + 1:
                raise ValueError(f"CSV exceeds the {MAX_ROWS:,}-row limit.")
            if not row or not any(str(v or "").strip() for v in row.values()):
                continue
            date_text = str(row.get(date_key) or "").strip()
            try:
                txn_date = datetime.strptime(date_text[:10], "%Y-%m-%d").date() if "-" in date_text[:10] else datetime.strptime(date_text[:10], "%d/%m/%Y").date()
                amount = Decimal(str(row.get(amount_key) or "").replace(",", "").replace("R", "").strip())
                balance_text = str(row.get(balance_key) or "").replace(",", "").replace("R", "").strip() if balance_key else ""
                balance = Decimal(balance_text) if balance_text else None
            except (ValueError, InvalidOperation):
                raise ValueError(f"Invalid date, amount or balance on CSV row {line_number}.")
            description = str(row.get(desc_key) or "").strip()
            if not description or amount == 0 or not amount.is_finite():
                raise ValueError(f"Row {line_number} needs a description and a non-zero valid amount.")
            reference = str(row.get(ref_key) or "").strip()[:120] or None if ref_key else None
            external_id = str(row.get(id_key) or "").strip()[:120] or None if id_key else None
            currency = str(row.get(currency_key) or "ZAR").strip().upper()[:3] if currency_key else "ZAR"
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError(f"Invalid currency on CSV row {line_number}.")
            parsed.append((txn_date, description[:240], reference, external_id, amount.quantize(Decimal("0.01")), balance, currency))
        if not parsed:
            raise ValueError("No valid transaction rows were found.")
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    batch = BankStatementImport(
        business_id=membership.business_id, created_by_user_id=user.id,
        filename=filename.rsplit("/", 1)[-1][:180], account_label=account_label,
        currency="ZAR", row_count=len(parsed), imported_count=0, duplicate_count=0,
    )
    db.add(batch)
    db.flush()
    imported = duplicates = 0
    for txn_date, description, reference, external_id, amount, balance, currency in parsed:
        identity = external_id or "|".join((txn_date.isoformat(), description.casefold(), reference or "", str(amount), currency))
        fingerprint = hashlib.sha256((account_label.casefold() + "|" + identity).encode("utf-8")).hexdigest()
        exists = db.scalar(select(BankStatementTransaction.id).where(
            BankStatementTransaction.business_id == membership.business_id,
            BankStatementTransaction.fingerprint == fingerprint,
        ))
        if exists:
            duplicates += 1
            continue
        db.add(BankStatementTransaction(
            business_id=membership.business_id, import_id=batch.id, transaction_date=txn_date,
            description=description, reference=reference, external_id=external_id, amount=amount,
            currency=currency, running_balance=balance, fingerprint=fingerprint,
        ))
        imported += 1
    batch.imported_count = imported
    batch.duplicate_count = duplicates
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A duplicate statement row was imported concurrently. Please retry; existing records were preserved.") from None
    return {"import_id": batch.id, "filename": batch.filename, "account_label": batch.account_label,
            "rows_read": batch.row_count, "imported": imported, "duplicates_skipped": duplicates,
            "message": "Statement imported as bank evidence only. No POS sale, expense or income records were changed."}


@router.get("/imports")
def list_imports(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = membership_for(user, db)
    rows = db.scalars(select(BankStatementImport).where(
        BankStatementImport.business_id == membership.business_id
    ).order_by(BankStatementImport.created_at.desc()).limit(100)).all()
    return [{"id": r.id, "filename": r.filename, "account_label": r.account_label,
             "currency": r.currency, "row_count": r.row_count, "imported_count": r.imported_count,
             "duplicate_count": r.duplicate_count, "created_at": r.created_at} for r in rows]


@router.get("/transactions")
def list_bank_transactions(
    reconciliation_status: str | None = Query(default=None, pattern="^(unmatched|matched|ignored)$"),
    limit: int = Query(default=100, ge=1, le=500),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    membership = membership_for(user, db)
    statement = select(BankStatementTransaction).where(BankStatementTransaction.business_id == membership.business_id)
    if reconciliation_status:
        statement = statement.where(BankStatementTransaction.reconciliation_status == reconciliation_status)
    rows = db.scalars(statement.order_by(BankStatementTransaction.transaction_date.desc(), BankStatementTransaction.created_at.desc()).limit(limit)).all()
    return [{"id": r.id, "transaction_date": r.transaction_date, "description": r.description,
             "reference": r.reference, "amount": money(r.amount), "currency": r.currency,
             "running_balance": money(r.running_balance) if r.running_balance is not None else None,
             "reconciliation_status": r.reconciliation_status, "review_note": r.review_note,
             "import_id": r.import_id} for r in rows]


@router.get("/summary")
def bank_reconciliation_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = membership_for(user, db)
    rows = db.execute(select(BankStatementTransaction.reconciliation_status, func.count(BankStatementTransaction.id),
                             func.sum(BankStatementTransaction.amount)).where(
        BankStatementTransaction.business_id == membership.business_id
    ).group_by(BankStatementTransaction.reconciliation_status)).all()
    totals = {key: {"count": count, "net_amount": money(amount)} for key, count, amount in rows}
    return {"currency": "mixed", "statuses": totals,
            "note": "Bank statement balances are not VEXION cash balances. Transactions remain unmatched until a reviewer confirms their treatment."}


@router.post("/transactions/{transaction_id}/review")
def review_bank_transaction(
    transaction_id: str,
    payload: dict,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    membership = membership_for(user, db)
    record = db.scalar(select(BankStatementTransaction).where(
        BankStatementTransaction.id == transaction_id,
        BankStatementTransaction.business_id == membership.business_id,
    ))
    if not record:
        raise HTTPException(status_code=404, detail="Bank statement transaction not found.")
    status_value = payload.get("status")
    note = str(payload.get("note") or "").strip()
    if status_value not in {"matched", "ignored", "unmatched"}:
        raise HTTPException(status_code=422, detail="Status must be matched, ignored or unmatched.")
    if status_value == "matched" and len(note) < 3:
        raise HTTPException(status_code=422, detail="A review note explaining the match is required.")
    if len(note) > 500:
        raise HTTPException(status_code=422, detail="Review note must be 500 characters or fewer.")
    record.reconciliation_status = status_value
    record.review_note = note or None
    record.reviewed_by_user_id = user.id
    record.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)
    return {"id": record.id, "reconciliation_status": record.reconciliation_status,
            "review_note": record.review_note, "reviewed_at": record.reviewed_at,
            "message": "Review recorded. This action does not alter POS or finance ledger entries."}
