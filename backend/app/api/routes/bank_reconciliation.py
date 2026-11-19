import csv
import hashlib
import io
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import BankStatementImport, BankStatementMatchLink, BankStatementTransaction, FinanceTransaction, Membership, POSTransaction, User

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
             "matched_source_type": r.matched_source_type, "matched_source_id": r.matched_source_id,
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



def _candidate_payload(source_type: str, source_id: str, label: str, amount, source_date, reference_match: bool):
    return {
        "source_type": source_type,
        "source_id": source_id,
        "label": label,
        "amount": money(amount),
        "source_date": source_date.isoformat(),
        "reference_match": reference_match,
        "match_basis": "Exact reference, amount and date window" if reference_match else "Exact amount and date window",
    }


def _suggestions_for_bank_row(record: BankStatementTransaction, membership: Membership, db: Session):
    """Return exact-amount/date candidates only; never auto-match or infer a settlement."""
    if record.currency != "ZAR":
        return []
    local_tz = ZoneInfo("Africa/Johannesburg")
    start_date = record.transaction_date - timedelta(days=3)
    end_date = record.transaction_date + timedelta(days=3)
    bank_reference = (record.reference or "").strip().casefold()
    candidates = []

    finance_rows = db.scalars(select(FinanceTransaction).where(
        FinanceTransaction.business_id == membership.business_id,
        FinanceTransaction.currency == record.currency,
        FinanceTransaction.status == "paid",
        FinanceTransaction.amount == abs(record.amount),
    )).all()
    for item in finance_rows:
        source_date = item.paid_on or item.occurred_on
        if not start_date <= source_date <= end_date:
            continue
        expected_kind = "income" if record.amount > 0 else "expense"
        if item.kind != expected_kind:
            continue
        if db.scalar(select(BankStatementTransaction.id).where(
            BankStatementTransaction.business_id == membership.business_id,
            BankStatementTransaction.matched_source_type == "finance",
            BankStatementTransaction.matched_source_id == item.id,
        )):
            continue
        ref_match = bool(bank_reference and item.reference and bank_reference == item.reference.strip().casefold())
        candidates.append(_candidate_payload("finance", item.id, item.description, item.amount, source_date, ref_match))

    pos_rows = db.scalars(select(POSTransaction).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.currency == record.currency,
        POSTransaction.net_amount == abs(record.amount),
        POSTransaction.transaction_type == ("sale" if record.amount > 0 else "refund"),
    )).all()
    for item in pos_rows:
        occurred_at = item.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        source_date = occurred_at.astimezone(local_tz).date()
        if not start_date <= source_date <= end_date:
            continue
        if db.scalar(select(BankStatementTransaction.id).where(
            BankStatementTransaction.business_id == membership.business_id,
            BankStatementTransaction.matched_source_type == "pos",
            BankStatementTransaction.matched_source_id == item.id,
        )):
            continue
        ref_match = bool(bank_reference and item.external_transaction_id and bank_reference == item.external_transaction_id.strip().casefold())
        label = f"POS {item.transaction_type} · {item.branch_name or 'Branch not supplied'} · {item.till_name or 'Till not supplied'}"
        candidates.append(_candidate_payload("pos", item.id, label, item.net_amount, source_date, ref_match))

    candidates.sort(key=lambda item: (not item["reference_match"], item["source_date"]))
    return candidates[:20]


@router.get("/transactions/{transaction_id}/suggestions")
def bank_match_suggestions(
    transaction_id: str,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    membership = membership_for(user, db)
    record = db.scalar(select(BankStatementTransaction).where(
        BankStatementTransaction.id == transaction_id,
        BankStatementTransaction.business_id == membership.business_id,
    ))
    if not record:
        raise HTTPException(status_code=404, detail="Bank statement transaction not found.")
    if record.reconciliation_status != "unmatched":
        raise HTTPException(status_code=409, detail="Only unmatched bank transactions can request match suggestions.")
    candidates = _suggestions_for_bank_row(record, membership, db)
    return {
        "bank_transaction_id": record.id,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "message": "Suggestions are exact-amount candidates within three calendar days. Review the source record before confirming; bank settlement is not inferred.",
    }


@router.post("/transactions/{transaction_id}/match")
def confirm_bank_match(
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
    if record.reconciliation_status != "unmatched":
        raise HTTPException(status_code=409, detail="This bank transaction has already been reviewed.")
    source_type = payload.get("source_type")
    source_id = str(payload.get("source_id") or "").strip()
    if source_type not in {"finance", "pos"} or not source_id:
        raise HTTPException(status_code=422, detail="Select a valid finance or POS source record.")
    candidates = _suggestions_for_bank_row(record, membership, db)
    selected = next((item for item in candidates if item["source_type"] == source_type and item["source_id"] == source_id), None)
    if not selected:
        raise HTTPException(status_code=422, detail="That record is not an eligible exact-amount/date candidate. Review it manually without linking.")
    # Store single-record links in the same ledger as batch links. The database
    # unique constraint then prevents a POS/finance source being linked by either
    # workflow, including when two requests race.
    db.add(BankStatementMatchLink(
        business_id=membership.business_id,
        bank_transaction_id=record.id,
        source_type=source_type,
        source_id=source_id,
        signed_amount=Decimal(str(record.amount)).quantize(Decimal("0.01")),
        source_date=date.fromisoformat(selected["source_date"]),
        created_by_user_id=user.id,
    ))
    record.matched_source_type = source_type
    record.matched_source_id = source_id
    record.reconciliation_status = "matched"
    record.review_note = f"Confirmed exact candidate: {selected['label']} ({source_type}:{source_id}). {selected['match_basis']}."
    record.reviewed_by_user_id = user.id
    record.reviewed_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That source record is already linked to another bank transaction.") from None
    db.refresh(record)
    return {"id": record.id, "reconciliation_status": record.reconciliation_status,
            "matched_source_type": record.matched_source_type, "matched_source_id": record.matched_source_id,
            "review_note": record.review_note,
            "message": "Exact candidate link recorded. This is a reviewer-confirmed link, not independent proof of bank settlement."}


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


@router.post("/transactions/{transaction_id}/batch-match")
def confirm_pos_settlement_batch(transaction_id: str, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Reviewer-confirmed many-to-one matching of card POS transactions to a bank deposit."""
    membership = membership_for(user, db)
    record = db.scalar(select(BankStatementTransaction).where(BankStatementTransaction.id == transaction_id, BankStatementTransaction.business_id == membership.business_id))
    if not record:
        raise HTTPException(status_code=404, detail="Bank statement transaction not found.")
    if record.reconciliation_status != "unmatched":
        raise HTTPException(status_code=409, detail="Only unmatched bank transactions can receive a settlement batch.")
    if record.currency != "ZAR":
        raise HTTPException(status_code=422, detail="Settlement batches currently support ZAR only.")
    source_ids = payload.get("source_ids")
    if not isinstance(source_ids, list) or not 2 <= len(source_ids) <= 100:
        raise HTTPException(status_code=422, detail="Select between 2 and 100 POS transactions.")
    source_ids = [str(value).strip() for value in source_ids]
    if any(not value for value in source_ids) or len(set(source_ids)) != len(source_ids):
        raise HTTPException(status_code=422, detail="POS transaction IDs must be unique and non-empty.")
    selected = db.scalars(select(POSTransaction).where(POSTransaction.business_id == membership.business_id, POSTransaction.id.in_(source_ids))).all()
    if len(selected) != len(source_ids):
        raise HTTPException(status_code=422, detail="One or more POS transactions do not belong to this business or do not exist.")
    local_tz = ZoneInfo("Africa/Johannesburg")
    start_date, end_date = record.transaction_date - timedelta(days=3), record.transaction_date + timedelta(days=3)
    signed_total = Decimal("0.00")
    links = []
    card_methods = {"card", "credit_card", "debit_card", "visa", "mastercard", "amex"}
    for item in selected:
        if item.currency != record.currency or item.transaction_type not in {"sale", "refund"}:
            raise HTTPException(status_code=422, detail="Every source must be a same-currency POS sale or refund.")
        if str(item.payment_method or "").strip().casefold() not in card_methods:
            raise HTTPException(status_code=422, detail="Only card-payment POS transactions can be included.")
        occurred_at = item.occurred_at
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        source_date = occurred_at.astimezone(local_tz).date()
        if not start_date <= source_date <= end_date:
            raise HTTPException(status_code=422, detail="Every POS transaction must be within three calendar days of the bank date.")
        single = db.scalar(select(BankStatementTransaction.id).where(BankStatementTransaction.business_id == membership.business_id, BankStatementTransaction.matched_source_type == "pos", BankStatementTransaction.matched_source_id == item.id))
        batch = db.scalar(select(BankStatementMatchLink.id).where(BankStatementMatchLink.business_id == membership.business_id, BankStatementMatchLink.source_type == "pos", BankStatementMatchLink.source_id == item.id))
        if single or batch:
            raise HTTPException(status_code=409, detail="A selected POS transaction is already linked to another bank transaction.")
        amount = Decimal(str(item.net_amount)).quantize(Decimal("0.01"))
        signed = amount if item.transaction_type == "sale" else -amount
        signed_total += signed
        links.append(BankStatementMatchLink(business_id=membership.business_id, bank_transaction_id=record.id, source_type="pos", source_id=item.id, signed_amount=signed, source_date=source_date, created_by_user_id=user.id))
    bank_amount = Decimal(str(record.amount)).quantize(Decimal("0.01"))
    if signed_total.quantize(Decimal("0.01")) != bank_amount:
        raise HTTPException(status_code=422, detail=f"Selected POS total ({signed_total:.2f}) does not exactly equal the bank amount ({bank_amount:.2f}). No links were saved.")
    db.add_all(links)
    record.reconciliation_status = "matched"
    record.review_note = f"Reviewer confirmed {len(links)} card POS transactions totalling {signed_total:.2f} {record.currency}. Exact amount only; processor fees and settlement timing were not inferred."
    record.reviewed_by_user_id, record.reviewed_at = user.id, datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A selected POS transaction was linked concurrently. No batch was saved.") from None
    return {"bank_transaction_id": record.id, "reconciliation_status": record.reconciliation_status, "matched_source_count": len(links), "signed_total": f"{signed_total:.2f}", "currency": record.currency, "message": "Reviewer-confirmed exact-total POS batch link recorded. This does not prove processor settlement or account for fees."}


@router.get("/transactions/{transaction_id}/matches")
def list_bank_transaction_matches(transaction_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = membership_for(user, db)
    record = db.scalar(select(BankStatementTransaction).where(BankStatementTransaction.id == transaction_id, BankStatementTransaction.business_id == membership.business_id))
    if not record:
        raise HTTPException(status_code=404, detail="Bank statement transaction not found.")
    links = db.scalars(select(BankStatementMatchLink).where(BankStatementMatchLink.business_id == membership.business_id, BankStatementMatchLink.bank_transaction_id == record.id).order_by(BankStatementMatchLink.source_date, BankStatementMatchLink.created_at)).all()
    total = sum((Decimal(str(row.signed_amount)) for row in links), Decimal("0.00"))
    return {"bank_transaction_id": record.id, "reconciliation_status": record.reconciliation_status, "matched_source_count": len(links), "signed_total": f"{total:.2f}", "currency": record.currency, "matches": [{"source_type": row.source_type, "source_id": row.source_id, "signed_amount": f"{Decimal(str(row.signed_amount)):.2f}", "source_date": row.source_date.isoformat()} for row in links], "note": "Reviewer-confirmed POS source links; not independent processor settlement evidence."}


@router.get("/transactions/{transaction_id}/batch-candidates")
def list_pos_settlement_batch_candidates(transaction_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    membership = membership_for(user, db)
    record = db.scalar(select(BankStatementTransaction).where(BankStatementTransaction.id == transaction_id, BankStatementTransaction.business_id == membership.business_id))
    if not record:
        raise HTTPException(status_code=404, detail="Bank statement transaction not found.")
    if record.reconciliation_status != "unmatched":
        raise HTTPException(status_code=409, detail="Only unmatched bank transactions can load batch candidates.")
    if record.currency != "ZAR":
        return {"bank_transaction_id": record.id, "candidates": [], "message": "Batch candidates currently support ZAR only."}
    start_date, end_date = record.transaction_date - timedelta(days=3), record.transaction_date + timedelta(days=3)
    local_tz = ZoneInfo("Africa/Johannesburg")
    card_methods = {"card", "credit_card", "debit_card", "visa", "mastercard", "amex"}
    rows = db.scalars(select(POSTransaction).where(
        POSTransaction.business_id == membership.business_id,
        POSTransaction.currency == record.currency,
        POSTransaction.transaction_type.in_(["sale", "refund"]),
    ).order_by(POSTransaction.occurred_at.desc()).limit(1000)).all()
    candidates = []
    for item in rows:
        if str(item.payment_method or "").strip().casefold() not in card_methods:
            continue
        occurred_at = item.occurred_at if item.occurred_at.tzinfo else item.occurred_at.replace(tzinfo=timezone.utc)
        source_date = occurred_at.astimezone(local_tz).date()
        if not start_date <= source_date <= end_date:
            continue
        single = db.scalar(select(BankStatementTransaction.id).where(BankStatementTransaction.business_id == membership.business_id, BankStatementTransaction.matched_source_type == "pos", BankStatementTransaction.matched_source_id == item.id))
        batch = db.scalar(select(BankStatementMatchLink.id).where(BankStatementMatchLink.business_id == membership.business_id, BankStatementMatchLink.source_type == "pos", BankStatementMatchLink.source_id == item.id))
        if single or batch:
            continue
        amount = Decimal(str(item.net_amount)).quantize(Decimal("0.01"))
        signed = amount if item.transaction_type == "sale" else -amount
        candidates.append({"source_id": item.id, "transaction_type": item.transaction_type, "source_date": source_date.isoformat(), "branch": item.branch_name, "till": item.till_name, "payment_method": item.payment_method, "amount": f"{amount:.2f}", "signed_amount": f"{signed:.2f}", "currency": item.currency, "external_reference": item.external_transaction_id})
    return {"bank_transaction_id": record.id, "bank_amount": f"{Decimal(str(record.amount)):.2f}", "currency": record.currency, "candidate_count": len(candidates), "candidates": candidates, "message": "Select source transactions whose signed total exactly equals the bank amount. Only same-business card sales/refunds within ±3 calendar days are shown."}
