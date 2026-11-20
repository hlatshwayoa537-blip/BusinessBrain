import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.business_context import get_business_membership
from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import (
    Business, BusinessConversation, BusinessInvitation, ConversationMessage,
    DealRoom, DealRoomMessage, Membership, User,
)
from app.schemas import (
    ConversationInviteCreate, ConversationMessageCreate, ConversationMessageResponse,
    ConversationResponse, DealRoomMessageResponse, DealRoomResponse,
    DealRoomStatusUpdate, InvitationDecision, InvitationResponse,
)
from app.security import hash_password, verify_password

router = APIRouter(prefix="/network", tags=["business conversations and deal rooms"])

def current_business(db: Session, user: User) -> Business:
    membership = get_business_membership(user, db)
    if not membership:
        raise HTTPException(status_code=403, detail="No business workspace is linked to this account.")
    business = db.get(Business, membership.business_id)
    if not business:
        raise HTTPException(status_code=403, detail="Business workspace is unavailable.")
    return business

def require_conversation(db: Session, conversation_id: str, business_id: str) -> BusinessConversation:
    conversation = db.get(BusinessConversation, conversation_id)
    if not conversation or business_id not in {conversation.host_business_id, conversation.invited_business_id}:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    if conversation.status != "active":
        raise HTTPException(status_code=409, detail="This conversation is no longer active.")
    return conversation

def invitation_response(db: Session, invite: BusinessInvitation) -> InvitationResponse:
    host = db.get(Business, invite.host_business_id)
    invited = db.get(Business, invite.invited_business_id)
    return InvitationResponse(
        id=invite.id, host_business_id=invite.host_business_id,
        host_business_name=host.name if host else "Unavailable business",
        invited_business_id=invite.invited_business_id,
        invited_business_name=invited.name if invited else "Unavailable business",
        invitation_message=invite.invitation_message, status=invite.status,
        expires_at=invite.expires_at, created_at=invite.created_at,
    )

def conversation_response(db: Session, conversation: BusinessConversation) -> ConversationResponse:
    host = db.get(Business, conversation.host_business_id)
    invited = db.get(Business, conversation.invited_business_id)
    deal = db.scalar(select(DealRoom).where(DealRoom.conversation_id == conversation.id))
    return ConversationResponse(
        id=conversation.id, host_business_id=conversation.host_business_id,
        host_business_name=host.name if host else "Unavailable business",
        invited_business_id=conversation.invited_business_id,
        invited_business_name=invited.name if invited else "Unavailable business",
        status=conversation.status, created_at=conversation.created_at,
        deal_room_id=deal.id if deal else None, deal_room_status=deal.status if deal else None,
    )

@router.post("/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
def create_invitation(payload: ConversationInviteCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    host = current_business(db, current_user)
    invited = db.get(Business, payload.invited_business_id)
    if not invited or not invited.directory_listed:
        raise HTTPException(status_code=404, detail="The selected business is not available in the Business Network.")
    if invited.id == host.id:
        raise HTTPException(status_code=400, detail="You cannot invite your own business.")
    existing = db.scalar(select(BusinessInvitation).where(
        BusinessInvitation.host_business_id == host.id,
        BusinessInvitation.invited_business_id == invited.id,
        BusinessInvitation.status == "pending",
    ))
    if existing:
        raise HTTPException(status_code=409, detail="A pending invitation already exists for this business.")
    invite = BusinessInvitation(
        host_business_id=host.id, invited_business_id=invited.id,
        invited_by_user_id=current_user.id, invitation_message=payload.invitation_message,
        access_password_hash=hash_password(payload.access_password),
        status="pending", expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invitation_response(db, invite)

@router.get("/invitations", response_model=list[InvitationResponse])
def list_invitations(direction: str = Query(default="incoming", pattern="^(incoming|outgoing|all)$"), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = current_business(db, current_user)
    statement = select(BusinessInvitation)
    if direction == "incoming":
        statement = statement.where(BusinessInvitation.invited_business_id == business.id)
    elif direction == "outgoing":
        statement = statement.where(BusinessInvitation.host_business_id == business.id)
    else:
        statement = statement.where(or_(BusinessInvitation.host_business_id == business.id, BusinessInvitation.invited_business_id == business.id))
    invites = db.scalars(statement.order_by(BusinessInvitation.created_at.desc()).limit(100)).all()
    return [invitation_response(db, item) for item in invites]

@router.post("/invitations/{invitation_id}/accept", response_model=ConversationResponse)
def accept_invitation(invitation_id: str, payload: InvitationDecision, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = current_business(db, current_user)
    invite = db.get(BusinessInvitation, invitation_id)
    if not invite or invite.invited_business_id != business.id:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    if invite.status != "pending":
        raise HTTPException(status_code=409, detail="This invitation has already been processed.")
    expires = invite.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        invite.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="This invitation has expired.")
    if not verify_password(payload.access_password, invite.access_password_hash):
        raise HTTPException(status_code=403, detail="The conversation password is incorrect.")
    invite.status = "accepted"
    conversation = BusinessConversation(host_business_id=invite.host_business_id, invited_business_id=invite.invited_business_id, invitation_id=invite.id, status="active")
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation_response(db, conversation)

@router.post("/invitations/{invitation_id}/reject", response_model=InvitationResponse)
def reject_invitation(invitation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = current_business(db, current_user)
    invite = db.get(BusinessInvitation, invitation_id)
    if not invite or invite.invited_business_id != business.id:
        raise HTTPException(status_code=404, detail="Invitation not found.")
    if invite.status != "pending":
        raise HTTPException(status_code=409, detail="This invitation has already been processed.")
    invite.status = "rejected"
    db.commit()
    db.refresh(invite)
    return invitation_response(db, invite)

@router.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = current_business(db, current_user)
    items = db.scalars(select(BusinessConversation).where(
        or_(BusinessConversation.host_business_id == business.id, BusinessConversation.invited_business_id == business.id),
        BusinessConversation.status == "active",
    ).order_by(BusinessConversation.created_at.desc()).limit(100)).all()
    return [conversation_response(db, item) for item in items]

@router.get("/conversations/{conversation_id}/messages", response_model=list[ConversationMessageResponse])
def list_conversation_messages(conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = current_business(db, current_user)
    require_conversation(db, conversation_id, business.id)
    items = db.scalars(select(ConversationMessage).where(ConversationMessage.conversation_id == conversation_id).order_by(ConversationMessage.created_at.asc()).limit(500)).all()
    result = []
    for item in items:
        sender_business, sender_user = db.get(Business, item.sender_business_id), db.get(User, item.sender_user_id)
        result.append(ConversationMessageResponse(id=item.id, sender_business_id=item.sender_business_id, sender_business_name=sender_business.name if sender_business else "Business", sender_user_name=sender_user.full_name if sender_user else "Member", body=item.body, created_at=item.created_at))
    return result

@router.post("/conversations/{conversation_id}/messages", response_model=ConversationMessageResponse, status_code=status.HTTP_201_CREATED)
def send_conversation_message(conversation_id: str, payload: ConversationMessageCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = current_business(db, current_user)
    require_conversation(db, conversation_id, business.id)
    item = ConversationMessage(conversation_id=conversation_id, sender_business_id=business.id, sender_user_id=current_user.id, body=payload.body)
    db.add(item)
    db.commit()
    db.refresh(item)
    return ConversationMessageResponse(id=item.id, sender_business_id=business.id, sender_business_name=business.name, sender_user_name=current_user.full_name, body=item.body, created_at=item.created_at)

@router.post("/conversations/{conversation_id}/deal-room", response_model=DealRoomResponse, status_code=status.HTTP_201_CREATED)
def create_deal_room(conversation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = current_business(db, current_user)
    require_conversation(db, conversation_id, business.id)
    room = db.scalar(select(DealRoom).where(DealRoom.conversation_id == conversation_id))
    if room:
        return DealRoomResponse(id=room.id, conversation_id=room.conversation_id, status=room.status, created_at=room.created_at, updated_at=room.updated_at)
    room = DealRoom(conversation_id=conversation_id, created_by_user_id=current_user.id, status="discussion")
    db.add(room)
    db.commit()
    db.refresh(room)
    return DealRoomResponse(id=room.id, conversation_id=room.conversation_id, status=room.status, created_at=room.created_at, updated_at=room.updated_at)

def get_deal_room(db: Session, room_id: str, business_id: str) -> tuple[DealRoom, BusinessConversation]:
    room = db.get(DealRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Deal Room not found.")
    conversation = require_conversation(db, room.conversation_id, business_id)
    return room, conversation

@router.patch("/deal-rooms/{room_id}", response_model=DealRoomResponse)
def update_deal_room_status(room_id: str, payload: DealRoomStatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = current_business(db, current_user)
    room, _ = get_deal_room(db, room_id, business.id)
    room.status = payload.status
    db.commit()
    db.refresh(room)
    return DealRoomResponse(id=room.id, conversation_id=room.conversation_id, status=room.status, created_at=room.created_at, updated_at=room.updated_at)

@router.get("/deal-rooms/{room_id}/messages", response_model=list[DealRoomMessageResponse])
def list_deal_room_messages(room_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = current_business(db, current_user)
    room, _ = get_deal_room(db, room_id, business.id)
    items = db.scalars(select(DealRoomMessage).where(DealRoomMessage.deal_room_id == room.id).order_by(DealRoomMessage.created_at.asc()).limit(500)).all()
    result = []
    for item in items:
        sender_business, sender_user = db.get(Business, item.sender_business_id), db.get(User, item.sender_user_id)
        result.append(DealRoomMessageResponse(id=item.id, sender_business_id=item.sender_business_id, sender_business_name=sender_business.name if sender_business else "Business", sender_user_name=sender_user.full_name if sender_user else "Member", body=item.body, created_at=item.created_at))
    return result

@router.post("/deal-rooms/{room_id}/messages", response_model=DealRoomMessageResponse, status_code=status.HTTP_201_CREATED)
def send_deal_room_message(room_id: str, payload: ConversationMessageCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = current_business(db, current_user)
    room, _ = get_deal_room(db, room_id, business.id)
    item = DealRoomMessage(deal_room_id=room.id, sender_business_id=business.id, sender_user_id=current_user.id, body=payload.body)
    db.add(item)
    db.commit()
    db.refresh(item)
    return DealRoomMessageResponse(id=item.id, sender_business_id=business.id, sender_business_name=business.name, sender_user_name=current_user.full_name, body=item.body, created_at=item.created_at)
