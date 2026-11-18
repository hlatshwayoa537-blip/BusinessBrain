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
