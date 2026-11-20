from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routes import deal_files
from app.models import Business, DealRoomFile


class FakeDB:
    def __init__(self, item):
        self.item = item
        self.commits = 0

    def get(self, model, _identity):
        if model is DealRoomFile:
            return self.item
        if model is Business:
            return SimpleNamespace(name="Test Business")
        return None

    def commit(self):
        self.commits += 1

    def refresh(self, _item):
        return None


def make_item():
    return SimpleNamespace(
        id="file-1",
        deal_room_id="room-1",
        uploader_business_id="business-1",
        uploader_user_id="user-1",
        original_filename="invoice.pdf",
        content_type="application/pdf",
        size_bytes=24,
        storage_key="quarantine/deal-rooms/room-1/file-1",
        status="pending",
        scanned_at=None,
        created_at=datetime.now(timezone.utc),
    )


def prepare_route(monkeypatch, item):
    business = SimpleNamespace(id="business-1")
    user = SimpleNamespace(id="user-1")
    db = FakeDB(item)
    monkeypatch.setattr(deal_files, "_business", lambda _db, _user: business)
    monkeypatch.setattr(deal_files, "_room", lambda _db, _room_id, _business_id: SimpleNamespace(id="room-1"))
    return db, user


def test_deal_room_upload_validates_content_before_scanning_and_verifies_promoted_object(monkeypatch):
    item = make_item()
    db, user = prepare_route(monkeypatch, item)
    calls = []
    monkeypatch.setattr(deal_files, "object_head", lambda _key: {"ContentLength": 24, "ContentType": "application/pdf"})
    monkeypatch.setattr(deal_files, "validate_object_content", lambda key, extension: calls.append(("validate", key, extension)))
    monkeypatch.setattr(deal_files, "scan_object_with_clamav", lambda key: calls.append(("scan", key)))
    monkeypatch.setattr(deal_files, "promote_clean_object", lambda source, target: calls.append(("promote", source, target)))

    result = deal_files.complete_upload("file-1", current_user=user, db=db)

    assert calls[0] == ("validate", "quarantine/deal-rooms/room-1/file-1", ".pdf")
    assert calls[1] == ("scan", "quarantine/deal-rooms/room-1/file-1")
    assert calls[2][0] == "promote"
    assert result.status == "clean"
    assert item.storage_key == "deal-rooms/room-1/file-1"


def test_deal_room_upload_rejects_invalid_content_and_deletes_quarantine(monkeypatch):
    item = make_item()
    db, user = prepare_route(monkeypatch, item)
    deleted = []
    monkeypatch.setattr(deal_files, "object_head", lambda _key: {"ContentLength": 24, "ContentType": "application/pdf"})
    monkeypatch.setattr(deal_files, "validate_object_content", lambda *_args: (_ for _ in ()).throw(HTTPException(status_code=422, detail="invalid file")))
    monkeypatch.setattr(deal_files, "scan_object_with_clamav", lambda _key: pytest.fail("Scanner must not run on invalid file content"))
    monkeypatch.setattr(deal_files, "delete_object", lambda key: deleted.append(key))

    with pytest.raises(HTTPException) as error:
        deal_files.complete_upload("file-1", current_user=user, db=db)

    assert error.value.status_code == 422
    assert item.status == "rejected"
    assert deleted == ["quarantine/deal-rooms/room-1/file-1"]
    assert db.commits == 1


def test_deal_room_upload_rejects_promoted_object_metadata_mismatch(monkeypatch):
    item = make_item()
    db, user = prepare_route(monkeypatch, item)
    deleted = []
    heads = iter([
        {"ContentLength": 24, "ContentType": "application/pdf"},
        {"ContentLength": 23, "ContentType": "application/pdf"},
    ])
    monkeypatch.setattr(deal_files, "object_head", lambda _key: next(heads))
    monkeypatch.setattr(deal_files, "validate_object_content", lambda *_args: None)
    monkeypatch.setattr(deal_files, "scan_object_with_clamav", lambda _key: None)
    monkeypatch.setattr(deal_files, "promote_clean_object", lambda *_args: None)
    monkeypatch.setattr(deal_files, "delete_object", lambda key: deleted.append(key))

    with pytest.raises(HTTPException) as error:
        deal_files.complete_upload("file-1", current_user=user, db=db)

    assert error.value.status_code == 503
    assert item.status == "rejected"
    assert deleted == ["deal-rooms/room-1/file-1"]
    assert db.commits == 1
