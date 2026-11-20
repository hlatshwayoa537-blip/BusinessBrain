import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.business_context import get_business_membership
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import Discrepancy, DiscrepancyEvent, DailyBusinessClose, Membership, User

router = APIRouter(prefix="/discrepancies", tags=["discrepancy management"])
MANAGERS = {"owner", "admin", "manager"}
MEMBERS = MANAGERS | {"staff", "employee", "hr"}


class DiscrepancyCreate(BaseModel):
    daily_close_id: str | None = None
    title: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=5, max_length=4000)
    category: str = Field(default="reconciliation", pattern=r"^(reconciliation|pos_data|cash|card|expense|other)$")
    priority: str = Field(default="normal", pattern=r"^(low|normal|high|urgent)$")
    amount: Decimal | None = Field(default=None, max_digits=14, decimal_places=2)
    currency: str = Field(default="ZAR", pattern=r"^[A-Za-z]{3}$")
    assigned_to_user_id: str | None = None


class DiscrepancyUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(open|investigating|resolved)$")
    assigned_to_user_id: str | None = None
    resolution_note: str | None = Field(default=None, max_length=4000)


class DiscrepancyNote(BaseModel):
    note: str = Field(min_length=2, max_length=4000)


def membership_for(user: User, db: Session) -> Membership:
    membership = get_business_membership(user, db)
    if not membership or membership.role not in MEMBERS:
        raise HTTPException(status_code=403, detail="A business workspace with discrepancy access is required.")
    return membership


def add_event(db: Session, item: Discrepancy, user: User, event_type: str, details: dict | None = None) -> None:
    db.add(DiscrepancyEvent(
        id=str(uuid.uuid4()), discrepancy_id=item.id, business_id=item.business_id,
        actor_user_id=user.id, event_type=event_type,
        details_json=json.dumps(details or {}, sort_keys=True),
    ))


def serialize(item: Discrepancy) -> dict:
    return {
        "id": item.id, "daily_close_id": item.daily_close_id,
        "title": item.title, "description": item.description, "category": item.category,
        "priority": item.priority, "status": item.status,
        "amount": f"{Decimal(item.amount):.2f}" if item.amount is not None else None,
        "currency": item.currency, "assigned_to_user_id": item.assigned_to_user_id,
        "created_by_user_id": item.created_by_user_id,
        "resolution_note": item.resolution_note, "resolved_by_user_id": item.resolved_by_user_id,
        "resolved_at": item.resolved_at, "created_at": item.created_at, "updated_at": item.updated_at,
    }


def scoped_item(discrepancy_id: str, business_id: str, db: Session) -> Discrepancy:
    item = db.scalar(select(Discrepancy).where(
        Discrepancy.id == discrepancy_id, Discrepancy.business_id == business_id,
    ))
    if not item:
        raise HTTPException(status_code=404, detail="Discrepancy not found.")
    return item


@router.get("")
def list_discrepancies(
    status_filter: str | None = Query(default=None, alias="status", pattern=r"^(open|investigating|resolved)$"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    statement = select(Discrepancy).where(Discrepancy.business_id == membership.business_id)
    if status_filter:
        statement = statement.where(Discrepancy.status == status_filter)
    rows = db.scalars(statement.order_by(Discrepancy.updated_at.desc()).limit(200)).all()
    return [serialize(item) for item in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_discrepancy(
    payload: DiscrepancyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    if payload.daily_close_id:
        close = db.scalar(select(DailyBusinessClose).where(
            DailyBusinessClose.id == payload.daily_close_id,
            DailyBusinessClose.business_id == membership.business_id,
        ))
        if not close:
            raise HTTPException(status_code=404, detail="Linked daily close not found.")
        if close.currency != payload.currency.upper():
            raise HTTPException(status_code=422, detail="Discrepancy currency must match the linked daily close.")
    if payload.assigned_to_user_id:
        assigned = db.scalar(select(Membership).where(
            Membership.user_id == payload.assigned_to_user_id,
            Membership.business_id == membership.business_id,
        ))
        if not assigned:
            raise HTTPException(status_code=422, detail="Assignee must be an active member of this business.")
        if membership.role not in MANAGERS:
            raise HTTPException(status_code=403, detail="Only an owner, administrator or manager can assign discrepancies.")
    item = Discrepancy(
        id=str(uuid.uuid4()), business_id=membership.business_id,
        daily_close_id=payload.daily_close_id, created_by_user_id=user.id,
        assigned_to_user_id=payload.assigned_to_user_id,
        title=payload.title.strip(), description=payload.description.strip(),
        category=payload.category, priority=payload.priority, status="open",
        amount=payload.amount, currency=payload.currency.upper(),
    )
    db.add(item)
    add_event(db, item, user, "created", {"status": "open", "priority": item.priority, "assigned_to_user_id": item.assigned_to_user_id})
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.get("/{discrepancy_id}")
def get_discrepancy(
    discrepancy_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    item = scoped_item(discrepancy_id, membership.business_id, db)
    events = db.scalars(select(DiscrepancyEvent).where(
        DiscrepancyEvent.discrepancy_id == item.id,
        DiscrepancyEvent.business_id == membership.business_id,
    ).order_by(DiscrepancyEvent.created_at.asc())).all()
    return {
        **serialize(item),
        "events": [{
            "id": event.id, "actor_user_id": event.actor_user_id,
            "event_type": event.event_type,
            "details": json.loads(event.details_json or "{}"),
            "created_at": event.created_at,
        } for event in events],
    }


@router.patch("/{discrepancy_id}")
def update_discrepancy(
    discrepancy_id: str, payload: DiscrepancyUpdate,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    item = scoped_item(discrepancy_id, membership.business_id, db)
    is_manager = membership.role in MANAGERS
    if payload.assigned_to_user_id is not None:
        if not is_manager:
            raise HTTPException(status_code=403, detail="Only an owner, administrator or manager can assign discrepancies.")
        assigned = db.scalar(select(Membership).where(
            Membership.user_id == payload.assigned_to_user_id,
            Membership.business_id == membership.business_id,
        ))
        if not assigned:
            raise HTTPException(status_code=422, detail="Assignee must be an active member of this business.")
        old_assignee = item.assigned_to_user_id
        item.assigned_to_user_id = payload.assigned_to_user_id
        add_event(db, item, user, "assigned", {"from_user_id": old_assignee, "to_user_id": item.assigned_to_user_id})
    elif payload.assigned_to_user_id is None and "assigned_to_user_id" in payload.model_fields_set:
        if not is_manager:
            raise HTTPException(status_code=403, detail="Only an owner, administrator or manager can unassign discrepancies.")
        old_assignee = item.assigned_to_user_id
        item.assigned_to_user_id = None
        add_event(db, item, user, "unassigned", {"from_user_id": old_assignee})

    if payload.status is not None:
        if not is_manager and item.assigned_to_user_id != user.id:
            raise HTTPException(status_code=403, detail="Only a manager or the assigned team member can update this discrepancy.")
        if item.status == "resolved" and payload.status != "resolved" and not is_manager:
            raise HTTPException(status_code=403, detail="Only a manager can reopen a resolved discrepancy.")
        if payload.status == "resolved":
            note = (payload.resolution_note or item.resolution_note or "").strip()
            if len(note) < 3:
                raise HTTPException(status_code=422, detail="Add a resolution note before marking this discrepancy resolved.")
            item.resolution_note = note
            item.resolved_by_user_id = user.id
            item.resolved_at = datetime.now(timezone.utc)
        elif item.status == "resolved":
            item.resolution_note = None
            item.resolved_by_user_id = None
            item.resolved_at = None
        previous = item.status
        item.status = payload.status
        if previous != item.status:
            add_event(db, item, user, "status_changed", {"from": previous, "to": item.status})
    elif payload.resolution_note is not None:
        if not is_manager and item.assigned_to_user_id != user.id:
            raise HTTPException(status_code=403, detail="Only a manager or the assigned team member can update this discrepancy.")
        item.resolution_note = payload.resolution_note.strip()
        add_event(db, item, user, "resolution_note_updated", {"note": item.resolution_note})

    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.post("/{discrepancy_id}/notes", status_code=status.HTTP_201_CREATED)
def add_discrepancy_note(
    discrepancy_id: str, payload: DiscrepancyNote,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    item = scoped_item(discrepancy_id, membership.business_id, db)
    add_event(db, item, user, "note_added", {"note": payload.note.strip()})
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Investigation note recorded."}
