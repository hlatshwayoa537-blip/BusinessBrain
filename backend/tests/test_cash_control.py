def register(client, email, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": "Cash Control Owner", "email": email, "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Services", "country": "ZA"
    })
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_cash_control_reports_missing_bank_balance_without_inventing_zero(client):
    auth = register(client, "cash-control-empty@example.com", "Cash Control Empty")
    response = client.get("/api/v1/cash-control/overview", headers=auth)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["cash_accounts"] == []
    assert data["by_currency"] == {}
    assert data["scheduled_movements"] == []
    assert "no live bank connection" in data["data_quality"]["bank_balance"]


def test_cash_control_uses_latest_statement_running_balance_and_flags_stale(client):
    auth = register(client, "cash-control-bank@example.com", "Cash Control Bank")
    csv_data = (
        "date,description,amount,reference,balance,currency\n"
        "2026-11-18,Opening transfer,1000.00,REF-1,1000.00,ZAR\n"
        "2026-11-19,Card settlement,500.00,REF-2,1500.00,ZAR\n"
    )
    imported = client.post(
        "/api/v1/bank-reconciliation/imports?account_label=Main%20Business%20Account&filename=statement.csv",
        headers={**auth, "Content-Type": "text/csv"}, content=csv_data,
    )
    assert imported.status_code == 201, imported.text
    data = client.get("/api/v1/cash-control/overview", headers=auth).json()
    assert len(data["cash_accounts"]) == 1
    account = data["cash_accounts"][0]
    assert account["balance"] == "1500.00"
    assert account["status"] == "available"
    assert data["by_currency"]["ZAR"]["bank_cash_balance"] == "1500.00"


def test_cash_control_does_not_reuse_old_balance_when_latest_row_has_no_balance(client):
    auth = register(client, "cash-control-no-balance@example.com", "Cash Control No Balance")
    csv_data = (
        "date,description,amount,reference,balance,currency\n"
        "2026-11-18,Opening transfer,1000.00,REF-1,1000.00,ZAR\n"
        "2026-11-19,Card settlement,500.00,REF-2,,ZAR\n"
    )
    imported = client.post(
        "/api/v1/bank-reconciliation/imports?account_label=Main%20Business%20Account&filename=statement.csv",
        headers={**auth, "Content-Type": "text/csv"}, content=csv_data,
    )
    assert imported.status_code == 201, imported.text
    data = client.get("/api/v1/cash-control/overview", headers=auth).json()
    account = data["cash_accounts"][0]
    assert account["balance"] is None
    assert account["status"] == "balance_not_supplied"
    assert data["by_currency"]["ZAR"]["bank_cash_balance"] is None


def test_cash_control_is_tenant_scoped(client):
    owner = register(client, "cash-control-scope-owner@example.com", "Cash Control Owner")
    other = register(client, "cash-control-scope-other@example.com", "Cash Control Other")
    response = client.get("/api/v1/cash-control/overview", headers=other)
    assert response.status_code == 200
    assert response.json()["cash_accounts"] == []
    assert response.json()["by_currency"] == {}
