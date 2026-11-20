from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.models import DealRoomFile, DiscrepancyEvidence
from app.services import quarantine_cleanup


class FakeRows:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, deal_files, evidence):
        self.rows = {
            DealRoomFile: deal_files,
            DiscrepancyEvidence: evidence,
        }
        self.commits = 0

    def scalars(self, statement):
        model = statement.column_descriptions[0]["entity"]
        return FakeRows(self.rows[model])

    def commit(self):
        self.commits += 1


def row(record_id, key, created_at, status="pending"):
    return SimpleNamespace(id=record_id, storage_key=key, created_at=created_at, status=status)


def test_cleanup_expires_old_pending_uploads_and_deletes_old_orphans(monkeypatch):
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    stale = now - timedelta(hours=30)
    fresh = now - timedelta(hours=1)
    old_deal = row("deal-old", "quarantine/deal-rooms/old", stale)
    fresh_deal = row("deal-fresh", "quarantine/deal-rooms/fresh", fresh)
    old_evidence = row("evidence-old", "quarantine/discrepancies/old", stale)
    unsafe_key = row("unsafe", "deal-rooms/durable-file", stale)
    db = FakeSession([old_deal, fresh_deal, unsafe_key], [old_evidence])

    deleted = []

    def delete_object(key):
        if key == old_evidence.storage_key:
            raise RuntimeError("temporary object-store failure")
        deleted.append(key)

    monkeypatch.setattr(quarantine_cleanup.settings, "quarantine_upload_ttl_hours", 24)
    monkeypatch.setattr(quarantine_cleanup, "delete_object", delete_object)
    monkeypatch.setattr(
        quarantine_cleanup,
        "list_quarantine_objects_older_than",
        lambda cutoff: [
            old_deal.storage_key,
            old_evidence.storage_key,
            fresh_deal.storage_key,
            "quarantine/deal-rooms/orphan",
        ],
    )

    result = quarantine_cleanup.cleanup_expired_quarantine(db, now=now)

    assert result == {"expired_records": 1, "deleted_objects": 2, "delete_failures": 1}
    assert old_deal.status == "expired"
    assert old_evidence.status == "pending"
    assert fresh_deal.status == "pending"
    assert unsafe_key.status == "pending"
    assert set(deleted) == {
        old_deal.storage_key,
        "quarantine/deal-rooms/orphan",
    }
    assert db.commits == 1


def test_cleanup_does_not_delete_fresh_uploads_or_durable_objects(monkeypatch):
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    fresh = row("fresh", "quarantine/discrepancies/fresh", now - timedelta(minutes=5))
    db = FakeSession([], [fresh])
    deleted = []
    monkeypatch.setattr(quarantine_cleanup.settings, "quarantine_upload_ttl_hours", 24)
    monkeypatch.setattr(quarantine_cleanup, "delete_object", deleted.append)
    monkeypatch.setattr(
        quarantine_cleanup,
        "list_quarantine_objects_older_than",
        lambda cutoff: [fresh.storage_key],
    )

    result = quarantine_cleanup.cleanup_expired_quarantine(db, now=now)

    assert result == {"expired_records": 0, "deleted_objects": 0, "delete_failures": 0}
    assert deleted == []
    assert fresh.status == "pending"
    assert db.commits == 0


def test_cleanup_clamps_invalid_retention_to_safe_minimum(monkeypatch):
    now = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
    old = row("old", "quarantine/deal-rooms/old", now - timedelta(hours=2))
    db = FakeSession([old], [])
    deleted = []
    monkeypatch.setattr(quarantine_cleanup.settings, "quarantine_upload_ttl_hours", 0)
    monkeypatch.setattr(quarantine_cleanup, "delete_object", deleted.append)
    monkeypatch.setattr(quarantine_cleanup, "list_quarantine_objects_older_than", lambda cutoff: [])

    result = quarantine_cleanup.cleanup_expired_quarantine(db, now=now)

    assert result["expired_records"] == 1
    assert deleted == [old.storage_key]
    assert old.status == "expired"
