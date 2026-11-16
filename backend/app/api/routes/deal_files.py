import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.auth import get_current_user
from app.db import get_db
from app.models import Business, BusinessConversation, DealRoom, DealRoomFile, Membership, User
from app.services.private_storage import delete_object, object_head, presigned_download, presigned_upload, promote_clean_object, scan_object_with_clamav

router = APIRouter(prefix="/network", tags=["deal room documents"])
MAX_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
    ".pptx": {"application/vnd.openxmlformats-officedocument.presentationml.presentation"},
    ".txt": {"text/plain"},
    ".csv": {"text/csv", "application/vnd.ms-excel"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
}

class UploadRequest(BaseModel):
    filename: Annotated[str, Field(min_length=1, max_length=180)]
    content_type: Annotated[str, Field(min_length=3, max_length=120)]
    size_bytes: int = Field(gt=0, le=MAX_FILE_BYTES)

class FileResponse(BaseModel):
    id: str
    deal_room_id: str
    uploader_business_id: str
    uploader_business_name: str
    original_filename: str
    content_type: str
    size_bytes: int
    status: str
    created_at: datetime

def _business(db: Session, user: User) -> Business:
    membership = db.scalar(select(Membership).where(Membership.user_id == user.id).order_by(Membership.created_at))
    business = db.get(Business, membership.business_id) if membership else None
    if not business:
        raise HTTPException(status_code=403, detail="No business workspace is linked to this account.")
    return business

def _room(db: Session, room_id: str, business_id: str) -> DealRoom:
    room = db.get(DealRoom, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Deal Room not found.")
    conversation = db.get(BusinessConversation, room.conversation_id)
    if not conversation or conversation.status != "active" or business_id not in {conversation.host_business_id, conversation.invited_business_id}:
        raise HTTPException(status_code=404, detail="Deal Room not found.")
    return room

def _file_response(db: Session, item: DealRoomFile) -> FileResponse:
    business = db.get(Business, item.uploader_business_id)
    return FileResponse(id=item.id, deal_room_id=item.deal_room_id, uploader_business_id=item.uploader_business_id, uploader_business_name=business.name if business else "Business", original_filename=item.original_filename, content_type=item.content_type, size_bytes=int(item.size_bytes), status=item.status, created_at=item.created_at)

@router.post("/deal-rooms/{room_id}/files/upload-url", status_code=status.HTTP_201_CREATED)
def create_upload_url(room_id: str, payload: UploadRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = _business(db, current_user)
    room = _room(db, room_id, business.id)
    filename = Path(payload.filename.replace("\\", "/")).name
    extension = Path(filename).suffix.lower()
    if not filename or filename in {".", ".."} or extension not in ALLOWED_TYPES or payload.content_type not in ALLOWED_TYPES[extension]:
        raise HTTPException(status_code=415, detail="File type is not supported. Upload PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG or JPG files.")
    file_id = str(uuid.uuid4())
    key = f"quarantine/deal-rooms/{room.id}/{file_id}"
    url = presigned_upload(key, payload.content_type)
    item = DealRoomFile(id=file_id, deal_room_id=room.id, uploader_business_id=business.id, uploader_user_id=current_user.id, original_filename=filename, content_type=payload.content_type, size_bytes=payload.size_bytes, storage_key=key, status="pending")
    db.add(item)
    db.commit()
    return {"file_id": file_id, "upload_url": url, "method": "PUT", "headers": {"Content-Type": payload.content_type}, "expires_in": 300}

@router.post("/files/{file_id}/complete", response_model=FileResponse)
def complete_upload(file_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = _business(db, current_user)
    item = db.get(DealRoomFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="File not found.")
    _room(db, item.deal_room_id, business.id)
    if item.status == "clean":
        return _file_response(db, item)
    if item.status != "pending":
        raise HTTPException(status_code=409, detail="This upload cannot be completed.")
    head = object_head(item.storage_key)
    if int(head.get("ContentLength", 0)) != int(item.size_bytes) or head.get("ContentType") != item.content_type:
        item.status = "rejected"
        db.commit()
        try: delete_object(item.storage_key)
        except Exception: pass
        raise HTTPException(status_code=422, detail="Uploaded file size or content type does not match the upload request.")
    try:
        scan_object_with_clamav(item.storage_key)
    except HTTPException as exc:
        if exc.status_code == 422:
            item.status = "rejected"
            db.commit()
            try: delete_object(item.storage_key)
            except Exception: pass
        raise
    final_key = f"deal-rooms/{item.deal_room_id}/{item.id}"
    promote_clean_object(item.storage_key, final_key)
    item.storage_key = final_key
    item.status = "clean"
    item.scanned_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _file_response(db, item)

@router.get("/deal-rooms/{room_id}/files", response_model=list[FileResponse])
def list_files(room_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = _business(db, current_user)
    _room(db, room_id, business.id)
    items = db.scalars(select(DealRoomFile).where(DealRoomFile.deal_room_id == room_id, DealRoomFile.status == "clean").order_by(DealRoomFile.created_at.desc()).limit(100)).all()
    return [_file_response(db, item) for item in items]

@router.post("/files/{file_id}/download-url")
def create_download_url(file_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = _business(db, current_user)
    item = db.get(DealRoomFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="File not found.")
    _room(db, item.deal_room_id, business.id)
    if item.status != "clean":
        raise HTTPException(status_code=404, detail="File is not available.")
    return {"download_url": presigned_download(item.storage_key, item.original_filename, item.content_type), "expires_in": 60}

@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(file_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    business = _business(db, current_user)
    item = db.get(DealRoomFile, file_id)
    if not item:
        raise HTTPException(status_code=404, detail="File not found.")
    _room(db, item.deal_room_id, business.id)
    if item.uploader_business_id != business.id:
        raise HTTPException(status_code=403, detail="Only the uploading business can delete this document.")
    try:
        delete_object(item.storage_key)
    except HTTPException:
        raise
    db.delete(item)
    db.commit()
