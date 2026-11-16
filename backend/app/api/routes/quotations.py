import json
import secrets
from datetime import datetime, time, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import Business, BusinessConversation, DealRoom, DealRoomQuotation, Membership, User
from app.schemas_quotes import QuotationCreate, QuotationDecision, QuotationResponse

router = APIRouter(prefix="/network", tags=["deal room quotations"])
CENT = Decimal("0.01")

def _business(db: Session, user: User) -> Business:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    business = db.get(Business, membership.business_id) if membership else None
    if not business:
        raise HTTPException(status_code=403, detail="No business workspace is linked to this account.")
    return business

def _room_for_member(db: Session, room_id: str, business_id: str):
    room = db.get(DealRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Deal Room not found.")
    conversation = db.get(BusinessConversation, room.conversation_id)
    if not conversation or conversation.status != "active" or business_id not in {conversation.host_business_id, conversation.invited_business_id}:
        raise HTTPException(status_code=404, detail="Deal Room not found.")
    recipient_id = conversation.invited_business_id if business_id == conversation.host_business_id else conversation.host_business_id
    return room, recipient_id

def _response(db: Session, quote: DealRoomQuotation) -> QuotationResponse:
    issuer = db.get(Business, quote.issuer_business_id)
    return QuotationResponse(
        id=quote.id, deal_room_id=quote.deal_room_id, issuer_business_id=quote.issuer_business_id,
        issuer_business_name=issuer.name if issuer else "Business", reference=quote.reference,
        title=quote.title, currency=quote.currency, line_items=json.loads(quote.line_items_json),
        subtotal=quote.subtotal, tax_total=quote.tax_total, total=quote.total, notes=quote.notes,
        valid_until=quote.valid_until.date() if quote.valid_until else None, status=quote.status,
        response_note=quote.response_note, responded_at=quote.responded_at, created_at=quote.created_at,
    )

@router.post("/deal-rooms/{room_id}/quotations", response_model=QuotationResponse, status_code=status.HTTP_201_CREATED)
def create_quotation(room_id: str, payload: QuotationCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = _business(db, current_user)
    room, _ = _room_for_member(db, room_id, business.id)
    lines, subtotal, tax_total = [], Decimal("0"), Decimal("0")
    for line in payload.line_items:
        amount = (line.quantity * line.unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
        tax = (amount * line.tax_rate / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
        subtotal += amount
        tax_total += tax
        lines.append({"description": line.description, "quantity": str(line.quantity), "unit_price": str(line.unit_price), "tax_rate": str(line.tax_rate), "line_subtotal": str(amount), "line_tax": str(tax), "line_total": str(amount + tax)})
    now = datetime.now(timezone.utc)
    valid_until = datetime.combine(payload.valid_until, time.max, tzinfo=timezone.utc) if payload.valid_until else None
    if valid_until and valid_until <= now:
        raise HTTPException(status_code=422, detail="Quotation validity date must be in the future.")
    quote = DealRoomQuotation(deal_room_id=room.id, issuer_business_id=business.id, issuer_user_id=current_user.id, reference="BBQ-" + secrets.token_hex(5).upper(), title=payload.title, currency=payload.currency, line_items_json=json.dumps(lines), subtotal=subtotal, tax_total=tax_total, total=subtotal + tax_total, notes=payload.notes, valid_until=valid_until, status="sent")
    db.add(quote)
    db.commit()
    db.refresh(quote)
    return _response(db, quote)

@router.get("/deal-rooms/{room_id}/quotations", response_model=list[QuotationResponse])
def list_quotations(room_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = _business(db, current_user)
    _room_for_member(db, room_id, business.id)
    quotes = db.scalars(select(DealRoomQuotation).where(DealRoomQuotation.deal_room_id == room_id).order_by(DealRoomQuotation.created_at.desc()).limit(100)).all()
    return [_response(db, quote) for quote in quotes]

@router.post("/quotations/{quotation_id}/decision", response_model=QuotationResponse)
def decide_quotation(quotation_id: str, payload: QuotationDecision, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = _business(db, current_user)
    quote = db.get(DealRoomQuotation, quotation_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found.")
    _, recipient_id = _room_for_member(db, quote.deal_room_id, business.id)
    if business.id != recipient_id:
        raise HTTPException(status_code=403, detail="Only the receiving business can accept or decline this quotation.")
    if quote.status != "sent":
        raise HTTPException(status_code=409, detail="This quotation has already been responded to or withdrawn.")
    if quote.valid_until:
        expiry = quote.valid_until if quote.valid_until.tzinfo else quote.valid_until.replace(tzinfo=timezone.utc)
        if expiry < datetime.now(timezone.utc):
            quote.status = "expired"
            db.commit()
            raise HTTPException(status_code=410, detail="This quotation has expired.")
    quote.status, quote.response_note = payload.decision, payload.note
    quote.response_by_user_id, quote.responded_at = current_user.id, datetime.now(timezone.utc)
    db.commit()
    db.refresh(quote)
    return _response(db, quote)

@router.post("/quotations/{quotation_id}/withdraw", response_model=QuotationResponse)
def withdraw_quotation(quotation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = _business(db, current_user)
    quote = db.get(DealRoomQuotation, quotation_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quotation not found.")
    _room_for_member(db, quote.deal_room_id, business.id)
    if quote.issuer_business_id != business.id:
        raise HTTPException(status_code=403, detail="Only the issuing business can withdraw this quotation.")
    if quote.status != "sent":
        raise HTTPException(status_code=409, detail="Only an unanswered quotation can be withdrawn.")
    quote.status = "withdrawn"
    db.commit()
    db.refresh(quote)
    return _response(db, quote)
