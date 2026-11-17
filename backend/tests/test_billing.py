from test_auth import registration_payload


def register_owner(client, email):
    response = client.post("/api/v1/auth/register", json=registration_payload(email))
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_billing_starts_inactive_and_prices_each_registered_pos_terminal(client):
    headers = register_owner(client, "billing-owner@example.com")
    overview = client.get("/api/v1/billing/me", headers=headers)
    assert overview.status_code == 200
    assert overview.json()["subscription_status"] == "not_started"
    assert overview.json()["payment_status"] == "not_configured"
    assert overview.json()["active_pos_terminals"] == 0
    assert overview.json()["estimated_monthly_total"] == "0.00"

    for index in range(1, 4):
        created = client.post("/api/v1/billing/terminals", headers=headers, json={
            "external_terminal_id": f"POS-{index}",
            "display_name": f"Till {index}",
            "branch_name": "Durban",
        })
        assert created.status_code == 201

    overview = client.get("/api/v1/billing/me", headers=headers)
    body = overview.json()
    assert body["active_pos_terminals"] == 3
    assert body["unit_price_per_pos_month"] == "499.00"
    assert body["estimated_monthly_total"] == "1497.00"
    assert body["subscription_status"] == "not_started"
    assert body["payment_status"] == "not_configured"
    assert "no payment has been collected" in body["notice"]


def test_inactive_terminal_is_not_counted_and_duplicate_terminal_is_rejected(client):
    headers = register_owner(client, "billing-terminals@example.com")
    created = client.post("/api/v1/billing/terminals", headers=headers, json={
        "external_terminal_id": "POS-01", "display_name": "Front till"
    })
    assert created.status_code == 201
    duplicate = client.post("/api/v1/billing/terminals", headers=headers, json={
        "external_terminal_id": "POS-01", "display_name": "Duplicate till"
    })
    assert duplicate.status_code == 409

    disabled = client.patch(
        f"/api/v1/billing/terminals/{created.json()['id']}",
        headers=headers,
        json={"status": "inactive"},
    )
    assert disabled.status_code == 200
    overview = client.get("/api/v1/billing/me", headers=headers).json()
    assert overview["active_pos_terminals"] == 0
    assert overview["inactive_pos_terminals"] == 1
    assert overview["estimated_monthly_total"] == "0.00"


def test_billing_terminal_registry_is_tenant_scoped(client):
    owner = register_owner(client, "billing-a@example.com")
    other = register_owner(client, "billing-b@example.com")
    created = client.post("/api/v1/billing/terminals", headers=owner, json={
        "external_terminal_id": "STORE-01", "display_name": "Main till"
    })
    assert created.status_code == 201
    overview = client.get("/api/v1/billing/me", headers=other)
    assert overview.status_code == 200
    assert overview.json()["active_pos_terminals"] == 0
    hidden = client.patch(
        f"/api/v1/billing/terminals/{created.json()['id']}",
        headers=other,
        json={"status": "inactive"},
    )
    assert hidden.status_code == 404


def test_billing_requires_authentication(client):
    assert client.get("/api/v1/billing/me").status_code == 401
