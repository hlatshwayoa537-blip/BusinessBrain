from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import discrepancy_evidence


class FakeDB:
    def __init__(self, evidence):
        self.evidence = evidence
        self.commits = 0

    def scalar(self, _statement):
        return self.evidence

    def commit(self):
        self.commits += 1

    def refresh(self, _item):
        return None


def test_discrepancy_evidence_rejects_and_deletes_promoted_object_metadata_mismatch(monkeypatch):
    evidence = SimpleNamespace(
        id="evidence-1",
        discrepancy_id="case-1",
        business_id="business-1",
        uploader_user_id="user-1",
        original_filename="receipt.pdf",
        content_type="application/pdf",
        size_bytes=100,
        storage_key="quarantine/discrepancies/business-1/case-1/evidence-1",
        status="pending",
        scanned_at=None,
    )
    db = FakeDB(evidence)
    user = SimpleNamespace(id="user-1")
    events = []
    deleted = []
    heads = iter([
        {"ContentLength": 100, "ContentType": "application/pdf"},
        {"ContentLength": 99, "ContentType": "application/pdf"},
    ])
    monkeypatch.setattr(discrepancy_evidence, "membership_for", lambda _user, _db: SimpleNamespace(business_id="business-1", role="manager"))
    monkeypatch.setattr(discrepancy_evidence, "scoped_item", lambda *_args: SimpleNamespace(id="case-1"))
    monkeypatch.setattr(discrepancy_evidence, "add_event", lambda _db, _item, _user, event_type, details: events.append((event_type, details)))
    monkeypatch.setattr(discrepancy_evidence, "object_head", lambda _key: next(heads))
    monkeypatch.setattr(discrepancy_evidence, "validate_object_content", lambda *_args: None)
    monkeypatch.setattr(discrepancy_evidence, "scan_object_with_clamav", lambda _key: None)
    monkeypatch.setattr(discrepancy_evidence, "promote_clean_object", lambda *_args: None)
    monkeypatch.setattr(discrepancy_evidence, "delete_object", lambda key: deleted.append(key))

    with pytest.raises(HTTPException) as error:
        discrepancy_evidence.complete_evidence_upload("evidence-1", db=db, user=user)

    assert error.value.status_code == 503
    assert evidence.status == "rejected"
    assert deleted == ["discrepancies/business-1/case-1/evidence-1"]
    assert db.commits == 1
    assert events[-1][0] == "evidence_rejected"
    assert events[-1][1]["reason"] == "promoted_metadata_mismatch"


def test_rejected_evidence_object_delete_failure_is_logged(monkeypatch, caplog):
    def fail_delete(_key):
        raise RuntimeError("storage unavailable")

    monkeypatch.setattr(discrepancy_evidence, "delete_object", fail_delete)
    with caplog.at_level("ERROR", logger=discrepancy_evidence.__name__):
        discrepancy_evidence._delete_rejected_object("quarantine/key", "evidence-2")

    assert "Could not delete rejected evidence object" in caplog.text
    assert "evidence-2" in caplog.text
