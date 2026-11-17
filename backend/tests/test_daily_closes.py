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


def manual_payload():
    return {
        "business_date": "2026-11-17", "branch_name": "Main branch",
        "expected_cash": "1000.00", "expected_card": "500.00", "expected_other": "0.00",
        "actual_cash": "980.00", "actual_card": "500.00", "actual_other": "0.00",
        "expenses_total": "120.00", "notes": "Cash counted by closing supervisor"
    }


def test_manual_daily_close_submit_review_and_audit(client):
    owner = register(client, "daily-close-owner@example.com", "Close Owner", "Close Store")
    saved = client.post("/api/v1/daily-closes", headers=headers(owner), json=manual_payload())
    assert saved.status_code == 201
    close = saved.json()
    assert close["source_type"] == "manual"
    assert close["expected_total"] == "1500.00"
    assert close["actual_total"] == "1480.00"
    assert close["variance_cash"] == "-20.00"
    assert close["variance_total"] == "-20.00"
    assert close["status"] == "draft"

    submitted = client.post(f"/api/v1/daily-closes/{close['id']}/submit", headers=headers(owner))
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    reviewed = client.post(f"/api/v1/daily-closes/{close['id']}/review", headers=headers(owner), json={
        "decision": "requires_attention", "note": "Please recount the cash drawer."
    })
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "requires_attention"
    assert reviewed.json()["review_note"] == "Please recount the cash drawer."

    events = client.get(f"/api/v1/daily-closes/{close['id']}/audit", headers=headers(owner))
    assert events.status_code == 200
    assert [event["action"] for event in events.json()] == ["created", "submitted", "requires_attention"]


def test_daily_close_uses_pos_payment_totals_when_transactions_exist(client):
    owner = register(client, "daily-close-pos@example.com", "POS Owner", "POS Store")
    connection = client.post("/api/v1/pos/connections", headers=headers(owner), json={
        "provider_name": "Test POS", "display_name": "Main till", "integration_method": "webhook"
    })
    assert connection.status_code == 201
    secret = connection.json()["webhook_secret"]
    transaction = client.post(
        f"/api/v1/pos/ingest/{connection.json()['id']}",
        headers={"X-Vexion-Secret": secret},
        json={
            "external_transaction_id": "SALE-001", "branch_name": "Main branch", "till_name": "Till 1",
            "transaction_type": "sale", "occurred_at": "2026-11-17T10:00:00+02:00",
            "currency": "ZAR", "gross_amount": "1000.00", "discount_amount": "0.00",
            "tax_amount": "0.00", "net_amount": "1000.00", "payment_method": "cash"
        },
    )
    assert transaction.status_code == 201
    payload = {
        "business_date": "2026-11-17", "branch_name": "Main branch",
        "actual_cash": "990.00", "actual_card": "0.00", "actual_other": "0.00"
    }
    saved = client.post("/api/v1/daily-closes", headers=headers(owner), json=payload)
    assert saved.status_code == 201
    assert saved.json()["source_type"] == "pos"
    assert saved.json()["pos_transaction_count"] == 1
    assert saved.json()["expected_cash"] == "1000.00"
    assert saved.json()["variance_cash"] == "-10.00"


def test_daily_close_requires_manual_expected_totals_when_no_pos_data(client):
    owner = register(client, "daily-close-missing@example.com", "Close Owner", "Close Store")
    response = client.post("/api/v1/daily-closes", headers=headers(owner), json={
        "business_date": "2026-11-17", "branch_name": "Main branch",
        "actual_cash": "100.00", "actual_card": "0.00", "actual_other": "0.00"
    })
    assert response.status_code == 422


def test_daily_close_is_business_scoped(client):
    owner = register(client, "daily-close-scope-a@example.com", "Close Owner", "Store A")
    other = register(client, "daily-close-scope-b@example.com", "Other Owner", "Store B")
    saved = client.post("/api/v1/daily-closes", headers=headers(owner), json=manual_payload()).json()
    response = client.get(f"/api/v1/daily-closes/{saved['id']}/audit", headers=headers(other))
    assert response.status_code == 404
