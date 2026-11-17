from test_auth import registration_payload

def auth_headers(client, email="pos-owner@example.com"):
    payload = registration_payload(email)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def create_pos_connection(client, headers):
    return client.post("/api/v1/pos/connections", headers=headers, json={
        "provider_name": "Generic POS", "display_name": "Main till", "integration_method": "webhook"
    })

def test_pos_connection_secret_is_returned_once_and_never_listed(client):
    headers = auth_headers(client)
    created = create_pos_connection(client, headers)
    assert created.status_code == 201
    body = created.json()
    secret = body["webhook_secret"]
    assert len(secret) >= 40
    assert "secret_hash" not in body
    listed = client.get("/api/v1/pos/connections", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "webhook_secret" not in listed.json()[0]
    assert "secret_hash" not in listed.json()[0]

def test_pos_ingestion_is_authenticated_idempotent_and_summarized(client):
    headers = auth_headers(client)
    connection = create_pos_connection(client, headers).json()
    payload = {
        "external_transaction_id": "TILL-0001", "branch_name": "Durban",
        "till_name": "Till 1", "transaction_type": "sale",
        "occurred_at": "2026-11-17T10:00:00+02:00", "currency": "ZAR",
        "gross_amount": "115.00", "discount_amount": "0.00",
        "tax_amount": "15.00", "net_amount": "115.00", "payment_method": "card"
    }
    denied = client.post(f"/api/v1/pos/ingest/{connection['id']}", json=payload)
    assert denied.status_code == 401
    accepted = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=payload)
    assert accepted.status_code == 201
    duplicate = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=payload)
    assert duplicate.status_code == 409
    summary = client.get("/api/v1/pos/summary?days=7", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["sales_total"] == "115.00"
    assert summary.json()["net_sales"] == "115.00"
    assert summary.json()["transaction_count"] == 1

def test_pos_connections_are_isolated_between_businesses(client):
    owner = auth_headers(client, "pos-a@example.com")
    other = auth_headers(client, "pos-b@example.com")
    created = create_pos_connection(client, owner)
    assert created.status_code == 201
    assert client.get("/api/v1/pos/connections", headers=other).json() == []
    assert client.get("/api/v1/pos/transactions", headers=other).json() == []
