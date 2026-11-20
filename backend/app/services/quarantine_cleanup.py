from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import DealRoomFile, DiscrepancyEvidence
from app.services.private_storage import delete_object, list_quarantine_objects_older_than

logger = logging.getLogger(__name__)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def cleanup_expired_quarantine(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Remove abandoned quarantine uploads without touching durable business files.

    Pending upload records expire after the configured retention window. Old
    objects without a fresh pending database record are treated as orphans and
    removed as well. Only keys under the quarantine/ prefix are ever deleted.
    """
    current = _utc(now or datetime.now(timezone.utc))
    ttl_hours = max(1, min(int(settings.quarantine_upload_ttl_hours), 168))
    cutoff = current - timedelta(hours=ttl_hours)

    deal_files = db.scalars(select(DealRoomFile).where(DealRoomFile.status == "pending")).all()
    evidence_files = db.scalars(select(DiscrepancyEvidence).where(
        DiscrepancyEvidence.status == "pending"
    )).all()
    pending = [*deal_files, *evidence_files]

    fresh_pending_keys = {
        row.storage_key for row in pending
        if _utc(row.created_at) >= cutoff and row.storage_key.startswith("quarantine/")
    }
    stale_pending = [
        row for row in pending
        if _utc(row.created_at) < cutoff and row.storage_key.startswith("quarantine/")
    ]

    expired_records = 0
    deleted_objects = 0
    delete_failures = 0
    attempted_keys: set[str] = set()

    for row in stale_pending:
        attempted_keys.add(row.storage_key)
        try:
            delete_object(row.storage_key)
        except Exception:
            delete_failures += 1
            logger.exception("Could not delete expired quarantine upload (record_id=%s)", row.id)
            continue
        row.status = "expired"
        expired_records += 1
        deleted_objects += 1

    # Also remove stale quarantine objects whose database row was deleted or
    # whose upload was rejected before its cleanup could complete.
    for key in list_quarantine_objects_older_than(cutoff):
        if key in fresh_pending_keys or key in attempted_keys:
            continue
        try:
            delete_object(key)
            deleted_objects += 1
        except Exception:
            delete_failures += 1
            logger.exception("Could not delete orphaned quarantine object (key=%s)", key)

    if expired_records:
        db.commit()

    return {
        "expired_records": expired_records,
        "deleted_objects": deleted_objects,
        "delete_failures": delete_failures,
    }
