import json
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.business_context import get_business_membership
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import (
    BankStatementMatchLink,
    DailyBusinessCloseAudit,
    DiscrepancyEvent,
    DiscrepancyEvidence,
    Membership,
    PurchaseOrderEvent,
    SupplierInvoiceEvent,
    User,
)

router = APIRouter(prefix="/activity", tags=["business activity"])


def _details(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _event(
    *,
    event_id: str,
    source: str,
    entity_type: str,
    entity_id: str,
    actor_id: str,
    action: str,
    occurred_at: datetime,
    details: dict | None = None,
) -> dict:
    return {
        "id": f"{source}:{event_id}",
        "source": source,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "actor_user_id": actor_id,
        "action": action,
        "occurred_at": occurred_at.isoformat() if occurred_at else None,
        "details": details or {},
    }


@router.get("")
def list_business_activity(
    from_date: date | None = Query(default=None),
    to_date: date | None = Query(default=None),
    actor_user_id: str | None = Query(default=None, min_length=1, max_length=36),
    source: str | None = Query(default=None, pattern=r"^(daily_close|discrepancy|evidence|purchase_order|supplier_invoice|bank_match)$"),
    action: str | None = Query(default=None, min_length=1, max_length=64),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership: Membership = get_business_membership(user, db)
    if membership.role.lower() not in {"owner", "admin", "manager"}:
        raise HTTPException(status_code=403, detail="Only business owners and managers can view the activity audit.")

    if from_date and to_date and from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must be on or before to_date.")

    business_id = membership.business_id
    start_at = datetime.combine(from_date, time.min, tzinfo=timezone.utc) if from_date else None
    end_at = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=timezone.utc) if to_date else None
    events: list[dict] = []

    def in_range(timestamp: datetime) -> bool:
        # SQLite may return naive datetimes in tests; production timestamps are UTC.
        comparable = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        if start_at and comparable < start_at:
            return False
        if end_at and comparable >= end_at:
            return False
        return True

    daily_rows = db.scalars(select(DailyBusinessCloseAudit).where(
        DailyBusinessCloseAudit.business_id == business_id
    ).order_by(DailyBusinessCloseAudit.created_at.desc()).limit(1000)).all()
    for row in daily_rows:
        if in_range(row.created_at):
            events.append(_event(
                event_id=row.id, source="daily_close", entity_type="daily_close",
                entity_id=row.close_id, actor_id=row.actor_user_id, action=row.action,
                occurred_at=row.created_at, details=_details(row.details_json),
            ))

    discrepancy_rows = db.scalars(select(DiscrepancyEvent).where(
        DiscrepancyEvent.business_id == business_id
    ).order_by(DiscrepancyEvent.created_at.desc()).limit(1000)).all()
    for row in discrepancy_rows:
        if in_range(row.created_at):
            events.append(_event(
                event_id=row.id, source="discrepancy", entity_type="discrepancy",
                entity_id=row.discrepancy_id, actor_id=row.actor_user_id, action=row.event_type,
                occurred_at=row.created_at, details=_details(row.details_json),
            ))

    evidence_rows = db.scalars(select(DiscrepancyEvidence).where(
        DiscrepancyEvidence.business_id == business_id
    ).order_by(DiscrepancyEvidence.created_at.desc()).limit(1000)).all()
    for row in evidence_rows:
        if in_range(row.created_at):
            events.append(_event(
                event_id=row.id, source="evidence", entity_type="discrepancy",
                entity_id=row.discrepancy_id, actor_id=row.uploader_user_id,
                action="evidence_uploaded", occurred_at=row.created_at,
                details={"filename": row.original_filename, "content_type": row.content_type, "status": row.status},
            ))

    purchase_rows = db.scalars(select(PurchaseOrderEvent).where(
        PurchaseOrderEvent.business_id == business_id
    ).order_by(PurchaseOrderEvent.created_at.desc()).limit(1000)).all()
    for row in purchase_rows:
        if in_range(row.created_at):
            events.append(_event(
                event_id=row.id, source="purchase_order", entity_type="purchase_order",
                entity_id=row.purchase_order_id, actor_id=row.actor_user_id, action=row.event_type,
                occurred_at=row.created_at, details=_details(row.details_json),
            ))

    invoice_rows = db.scalars(select(SupplierInvoiceEvent).where(
        SupplierInvoiceEvent.business_id == business_id
    ).order_by(SupplierInvoiceEvent.created_at.desc()).limit(1000)).all()
    for row in invoice_rows:
        if in_range(row.created_at):
            events.append(_event(
                event_id=row.id, source="supplier_invoice", entity_type="supplier_invoice",
                entity_id=row.invoice_id, actor_id=row.actor_user_id, action=row.event_type,
                occurred_at=row.created_at, details=_details(row.details_json),
            ))

    bank_rows = db.scalars(select(BankStatementMatchLink).where(
        BankStatementMatchLink.business_id == business_id
    ).order_by(BankStatementMatchLink.created_at.desc()).limit(1000)).all()
    for row in bank_rows:
        if in_range(row.created_at):
            events.append(_event(
                event_id=row.id, source="bank_match", entity_type=row.source_type,
                entity_id=row.source_id, actor_id=row.created_by_user_id,
                action="bank_transaction_matched", occurred_at=row.created_at,
                details={"signed_amount": f"{row.signed_amount:.2f}", "source_date": row.source_date.isoformat()},
            ))

    if actor_user_id:
        events = [event for event in events if event["actor_user_id"] == actor_user_id]
    if source:
        events = [event for event in events if event["source"] == source]
    if action:
        events = [event for event in events if event["action"] == action]

    events.sort(key=lambda item: item["occurred_at"] or "", reverse=True)
    total = len(events)
    page = events[offset:offset + limit]
    actor_ids = {event["actor_user_id"] for event in page}
    actors = db.scalars(select(User).where(User.id.in_(actor_ids))).all() if actor_ids else []
    actor_names = {actor.id: actor.full_name for actor in actors}
    for event in page:
        event["actor_name"] = actor_names.get(event["actor_user_id"], "Former user")

    return {
        "items": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "sources_included": [
            "daily_close", "discrepancy", "evidence",
            "purchase_order", "supplier_invoice", "bank_match",
        ],
        "coverage_note": "This feed aggregates existing audit records for the listed workflows. It does not imply that every change across VEXION is currently audited.",
    }
