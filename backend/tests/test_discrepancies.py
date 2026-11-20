from app.models import Membership, User


def register(client, email, name, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": name, "email": email, "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Retail", "country": "ZA"
    })
    assert response.status_code == 201
    return response.json()


def headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def manual_close_payload():
    return {
        "business_date": "2026-11-18", "branch_name": "Main branch",
        "expected_cash": "500.00", "expected_card": "250.00", "expected_other": "0.00",
        "actual_cash": "485.00", "actual_card": "250.00", "actual_other": "0.00",
    }


def test_discrepancy_lifecycle_records_audit_history(client):
    owner = register(client, "discrepancy-owner@example.com", "Case Owner", "Case Store")
    auth = headers(owner)
    close = client.post("/api/v1/daily-closes", headers=auth, json=manual_close_payload())
    assert close.status_code == 201

    created = client.post("/api/v1/discrepancies", headers=auth, json={
        "daily_close_id": close.json()["id"],
        "title": "Cash count differs from expected",
        "description": "The counted cash is R15 below the manually recorded expected amount.",
        "category": "cash", "priority": "high", "amount": "-15.00",
    })
    assert created.status_code == 201
    case = created.json()
    assert case["status"] == "open"
    assert case["amount"] == "-15.00"
    assert case["daily_close_id"] == close.json()["id"]

    note = client.post(f"/api/v1/discrepancies/{case['id']}/notes", headers=auth, json={
        "note": "Recount requested from the closing supervisor."
    })
    assert note.status_code == 201

    investigating = client.patch(f"/api/v1/discrepancies/{case['id']}", headers=auth, json={
        "status": "investigating"
    })
    assert investigating.status_code == 200
    assert investigating.json()["status"] == "investigating"

    missing_resolution = client.patch(f"/api/v1/discrepancies/{case['id']}", headers=auth, json={
        "status": "resolved"
    })
    assert missing_resolution.status_code == 422

    resolved = client.patch(f"/api/v1/discrepancies/{case['id']}", headers=auth, json={
        "status": "resolved", "resolution_note": "Recount completed; the till report was corrected."
    })
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None

    detail = client.get(f"/api/v1/discrepancies/{case['id']}", headers=auth)
    assert detail.status_code == 200
    events = detail.json()["events"]
    assert [event["event_type"] for event in events] == [
        "created", "note_added", "status_changed", "status_changed"
    ]
    assert events[1]["details"]["note"] == "Recount requested from the closing supervisor."


def test_discrepancy_records_are_business_scoped(client):
    owner = register(client, "discrepancy-scope-a@example.com", "Owner A", "Store A")
    other = register(client, "discrepancy-scope-b@example.com", "Owner B", "Store B")
    created = client.post("/api/v1/discrepancies", headers=headers(owner), json={
        "title": "Unmatched card settlement",
        "description": "The card settlement report does not match the closing record.",
        "category": "card", "priority": "normal", "currency": "ZAR",
    })
    assert created.status_code == 201
    response = client.get(
        f"/api/v1/discrepancies/{created.json()['id']}", headers=headers(other)
    )
    assert response.status_code == 404


def test_discrepancy_rejects_daily_close_from_another_business(client):
    owner = register(client, "discrepancy-close-a@example.com", "Owner A", "Store A")
    other = register(client, "discrepancy-close-b@example.com", "Owner B", "Store B")
    close = client.post("/api/v1/daily-closes", headers=headers(other), json=manual_close_payload())
    assert close.status_code == 201
    response = client.post("/api/v1/discrepancies", headers=headers(owner), json={
        "daily_close_id": close.json()["id"],
        "title": "Cross-business link test",
        "description": "This case must not be linked to another business close.",
    })
    assert response.status_code == 404



def test_discrepancy_evidence_upload_is_scanned_audited_and_download_scoped(client, monkeypatch):
    from app.api.routes import discrepancy_evidence as evidence_routes

    owner = register(client, "evidence-owner@example.com", "Evidence Owner", "Evidence Store")
    other = register(client, "evidence-other@example.com", "Other Owner", "Other Store")
    auth = headers(owner)
    created = client.post("/api/v1/discrepancies", headers=auth, json={
        "title": "Receipt required", "description": "Attach the supporting receipt for review.",
    })
    assert created.status_code == 201
    case_id = created.json()["id"]

    monkeypatch.setattr(evidence_routes, "presigned_upload", lambda *args: {
        "url": "https://private-storage.invalid", "fields": {"key": "quarantine/test"},
    })
    monkeypatch.setattr(evidence_routes, "object_head", lambda key: {
        "ContentLength": 1234, "ContentType": "application/pdf",
    })
    monkeypatch.setattr(evidence_routes, "validate_object_content", lambda key, extension: None)
    monkeypatch.setattr(evidence_routes, "scan_object_with_clamav", lambda key: None)
    monkeypatch.setattr(evidence_routes, "promote_clean_object", lambda source, target: None)
    monkeypatch.setattr(evidence_routes, "presigned_download", lambda *args: "https://private-storage.invalid/download")

    ticket = client.post(f"/api/v1/discrepancies/{case_id}/evidence/upload-url", headers=auth, json={
        "filename": "receipt.pdf", "content_type": "application/pdf", "size_bytes": 1234,
    })
    assert ticket.status_code == 201
    evidence_id = ticket.json()["evidence_id"]

    completed = client.post(f"/api/v1/discrepancies/evidence/{evidence_id}/complete", headers=auth)
    assert completed.status_code == 200
    assert completed.json()["status"] == "clean"

    listing = client.get(f"/api/v1/discrepancies/{case_id}/evidence", headers=auth)
    assert listing.status_code == 200
    assert len(listing.json()) == 1
    assert listing.json()[0]["original_filename"] == "receipt.pdf"

    detail = client.get(f"/api/v1/discrepancies/{case_id}", headers=auth)
    assert [event["event_type"] for event in detail.json()["events"]][-2:] == [
        "evidence_upload_started", "evidence_attached"
    ]

    download = client.post(f"/api/v1/discrepancies/evidence/{evidence_id}/download-url", headers=auth)
    assert download.status_code == 200
    assert download.json()["download_url"].endswith("/download")

    other_headers = headers(other)
    forbidden = client.post(
        f"/api/v1/discrepancies/evidence/{evidence_id}/download-url", headers=other_headers
    )
    assert forbidden.status_code == 404


def test_discrepancy_evidence_rejects_unsupported_file_type(client):
    owner = register(client, "evidence-type@example.com", "Evidence Type", "Evidence Type Store")
    auth = headers(owner)
    created = client.post("/api/v1/discrepancies", headers=auth, json={
        "title": "Unsupported file", "description": "Check upload validation.",
    })
    response = client.post(
        f"/api/v1/discrepancies/{created.json()['id']}/evidence/upload-url",
        headers=auth,
        json={"filename": "script.exe", "content_type": "application/octet-stream", "size_bytes": 100},
    )
    assert response.status_code == 415


def test_private_evidence_content_validation_checks_file_signature(monkeypatch):
    import io
    import pytest
    from fastapi import HTTPException
    from app.services import private_storage

    class FakeS3:
        def __init__(self, payload):
            self.payload = payload
        def get_object(self, **kwargs):
            return {"Body": io.BytesIO(self.payload)}

    monkeypatch.setattr(private_storage, "s3_client", lambda: FakeS3(b"%PDF-1.7\nvalid header\n%%EOF"))
    private_storage.validate_object_content("quarantine/test", ".pdf")

    monkeypatch.setattr(private_storage, "s3_client", lambda: FakeS3(b"<html>not a pdf</html>"))
    with pytest.raises(HTTPException) as error:
        private_storage.validate_object_content("quarantine/test", ".pdf")
    assert error.value.status_code == 422
