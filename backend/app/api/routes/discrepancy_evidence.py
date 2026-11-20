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
from app.api.routes.discrepancies import add_event, membership_for, scoped_item
from app.db import get_db
from app.models import DiscrepancyEvidence, User
from app.services.private_storage import (
    delete_object, object_head, presigned_download, presigned_upload,
    promote_clean_object, scan_object_with_clamav, validate_object_content,
)

router = APIRouter(prefix="/discrepancies", tags=["discrepancy evidence"])
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


class EvidenceUploadRequest(BaseModel):
    filename: Annotated[str, Field(min_length=1, max_length=180)]
    content_type: Annotated[str, Field(min_length=3, max_length=120)]
    size_bytes: int = Field(gt=0, le=MAX_FILE_BYTES)


def evidence_payload(item: DiscrepancyEvidence) -> dict:
    return {
        "id": item.id, "discrepancy_id": item.discrepancy_id,
        "original_filename": item.original_filename, "content_type": item.content_type,
        "size_bytes": item.size_bytes, "status": item.status,
        "uploader_user_id": item.uploader_user_id, "created_at": item.created_at,
        "scanned_at": item.scanned_at,
    }


@router.post("/{discrepancy_id}/evidence/upload-url", status_code=status.HTTP_201_CREATED)
def create_evidence_upload(
    discrepancy_id: str, payload: EvidenceUploadRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    item = scoped_item(discrepancy_id, membership.business_id, db)
    filename = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(payload.filename.replace("\\", "/")).name).strip(" .")
    extension = Path(filename).suffix.lower()
    if not filename or filename in {".", ".."} or extension not in ALLOWED_TYPES or payload.content_type not in ALLOWED_TYPES[extension]:
        raise HTTPException(status_code=415, detail="Unsupported file type. Use PDF, DOCX, XLSX, PPTX, TXT, CSV, PNG or JPG.")
    evidence_id = str(uuid.uuid4())
    key = f"quarantine/discrepancies/{membership.business_id}/{discrepancy_id}/{evidence_id}"
    upload = presigned_upload(key, payload.content_type, MAX_FILE_BYTES)
    evidence = DiscrepancyEvidence(
        id=evidence_id, discrepancy_id=item.id, business_id=membership.business_id,
        uploader_user_id=user.id, original_filename=filename, content_type=payload.content_type,
        size_bytes=payload.size_bytes, storage_key=key, status="pending",
    )
    db.add(evidence)
    add_event(db, item, user, "evidence_upload_started", {
        "evidence_id": evidence_id, "filename": filename, "size_bytes": payload.size_bytes,
    })
    db.commit()
    return {"evidence_id": evidence_id, "upload_url": upload["url"], "method": "POST",
            "fields": upload["fields"], "expires_in": 300}


@router.post("/evidence/{evidence_id}/complete")
def complete_evidence_upload(
    evidence_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    evidence = db.scalar(select(DiscrepancyEvidence).where(
        DiscrepancyEvidence.id == evidence_id,
        DiscrepancyEvidence.business_id == membership.business_id,
    ))
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    item = scoped_item(evidence.discrepancy_id, membership.business_id, db)
    if evidence.uploader_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only the uploader can complete this upload.")
    if evidence.status == "clean":
        return evidence_payload(evidence)
    if evidence.status != "pending":
        raise HTTPException(status_code=409, detail="This upload cannot be completed.")
    head = object_head(evidence.storage_key)
    if int(head.get("ContentLength", 0)) != evidence.size_bytes or head.get("ContentType") != evidence.content_type:
        evidence.status = "rejected"
        add_event(db, item, user, "evidence_rejected", {"evidence_id": evidence.id, "reason": "metadata_mismatch"})
        db.commit()
        try:
            delete_object(evidence.storage_key)
        except Exception:
            pass
        raise HTTPException(status_code=422, detail="Uploaded file size or content type does not match the request.")
    try:
        validate_object_content(evidence.storage_key, Path(evidence.original_filename).suffix.lower())
        scan_object_with_clamav(evidence.storage_key)
    except HTTPException as exc:
        if exc.status_code in {413, 422}:
            evidence.status = "rejected"
            add_event(db, item, user, "evidence_rejected", {
                "evidence_id": evidence.id,
                "reason": "file_too_large" if exc.status_code == 413 else "evidence_validation_or_scan_failed",
            })
            db.commit()
            try:
                delete_object(evidence.storage_key)
            except Exception:
                pass
        raise
    final_key = f"discrepancies/{membership.business_id}/{item.id}/{evidence.id}"
    promote_clean_object(evidence.storage_key, final_key)
    promoted = object_head(final_key)
    if int(promoted.get("ContentLength", 0)) != evidence.size_bytes or promoted.get("ContentType") != evidence.content_type:
        raise HTTPException(status_code=503, detail="The scanned evidence could not be verified in private storage. It has not been made available.")
    evidence.storage_key = final_key
    evidence.status = "clean"
    evidence.scanned_at = datetime.now(timezone.utc)
    add_event(db, item, user, "evidence_attached", {
        "evidence_id": evidence.id, "filename": evidence.original_filename,
        "size_bytes": evidence.size_bytes, "content_type": evidence.content_type,
    })
    db.commit()
    db.refresh(evidence)
    return evidence_payload(evidence)


@router.get("/{discrepancy_id}/evidence")
def list_case_evidence(
    discrepancy_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    scoped_item(discrepancy_id, membership.business_id, db)
    rows = db.scalars(select(DiscrepancyEvidence).where(
        DiscrepancyEvidence.discrepancy_id == discrepancy_id,
        DiscrepancyEvidence.business_id == membership.business_id,
        DiscrepancyEvidence.status == "clean",
    ).order_by(DiscrepancyEvidence.created_at.desc()).limit(100)).all()
    return [evidence_payload(row) for row in rows]


@router.post("/evidence/{evidence_id}/download-url")
def create_evidence_download(
    evidence_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    evidence = db.scalar(select(DiscrepancyEvidence).where(
        DiscrepancyEvidence.id == evidence_id,
        DiscrepancyEvidence.business_id == membership.business_id,
        DiscrepancyEvidence.status == "clean",
    ))
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    scoped_item(evidence.discrepancy_id, membership.business_id, db)
    return {"download_url": presigned_download(
        evidence.storage_key, evidence.original_filename, evidence.content_type,
    ), "expires_in": 60}


@router.delete("/evidence/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_case_evidence(
    evidence_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    membership = membership_for(user, db)
    evidence = db.scalar(select(DiscrepancyEvidence).where(
        DiscrepancyEvidence.id == evidence_id,
        DiscrepancyEvidence.business_id == membership.business_id,
    ))
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    item = scoped_item(evidence.discrepancy_id, membership.business_id, db)
    if membership.role not in {"owner", "admin", "manager"} and evidence.uploader_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only a manager or the uploader can remove this evidence.")
    if evidence.status != "removed":
        try:
            delete_object(evidence.storage_key)
        except HTTPException:
            raise
        evidence.status = "removed"
        add_event(db, item, user, "evidence_removed", {
            "evidence_id": evidence.id, "filename": evidence.original_filename,
        })
        db.commit()
