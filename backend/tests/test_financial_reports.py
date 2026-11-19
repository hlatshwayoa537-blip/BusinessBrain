def register(client, email, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": "Report Owner", "email": email,
        "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Retail", "country": "ZA"
    })
    assert response.status_code == 201
    return response.json()


def auth_headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def test_profit_loss_and_cash_flow_use_paid_records_and_pos_ledger(client):
    owner = register(client, "reports-owner@example.com", "Reports Trading")
    headers = auth_headers(owner)
    connection = client.post("/api/v1/pos/connections", headers=headers, json={
        "provider_name": "Generic POS", "display_name": "Main till", "integration_method": "webhook"
    }).json()
    pos_payload = {
        "external_transaction_id": "REPORT-SALE-1",
        "branch_name": "Durban", "till_name": "Till 1",
        "transaction_type": "sale", "occurred_at": "2026-11-18T10:00:00+02:00",
        "currency": "ZAR", "gross_amount": "230.00", "discount_amount": "0.00",
        "tax_amount": "30.00", "net_amount": "230.00", "payment_method": "card",
    }
    ingested = client.post(
        f"/api/v1/pos/ingest/{connection['id']}",
        headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=pos_payload,
    )
    assert ingested.status_code == 201

    for kind, amount, status_value, category in [
        ("income", "70.00", "paid", "Services"),
        ("income", "500.00", "unpaid", "Services"),
        ("expense", "40.00", "paid", "Utilities"),
        ("expense", "90.00", "unpaid", "Rent"),
    ]:
        response = client.post("/api/v1/finance/transactions", headers=headers, json={
            "kind": kind, "category": category, "description": f"Report {category}",
            "amount": amount, "status": status_value, "occurred_on": "2026-11-18",
        })
        assert response.status_code == 201

    pnl = client.get("/api/v1/financial-reports/profit-loss?year=2026&month=11", headers=headers)
    assert pnl.status_code == 200
    data = pnl.json()
    assert data["revenue"]["total"] == "300.00"
    assert data["expenses"]["total"] == "40.00"
    assert data["net_result"] is None
    assert data["net_result_before_cogs"] == "260.00"
    assert data["gross_profit_status"] == "incomplete"
    assert data["not_included"]["unpaid_manual_income"] == "500.00"
    assert data["not_included"]["unpaid_manual_expenses"] == "90.00"

    cash = client.get("/api/v1/financial-reports/cash-flow?year=2026&month=11", headers=headers)
    assert cash.status_code == 200
    cash_data = cash.json()
    assert cash_data["recorded_operating_flows"]["net_recorded_flow"] == "260.00"
    assert cash_data["bank_reconciliation"]["status"] == "not_connected"
    assert cash_data["bank_reconciliation"]["balance"] is None


def test_vat_report_does_not_invent_input_vat_or_payable(client):
    owner = register(client, "reports-vat@example.com", "VAT Reports")
    response = client.get("/api/v1/financial-reports/vat?year=2026", headers=auth_headers(owner))
    assert response.status_code == 200
    data = response.json()
    assert data["output_vat_on_issued_invoices"] == "0.00"
    assert data["input_vat"] is None
    assert data["input_vat_status"] == "not_tracked"
    assert data["estimated_vat_payable"] is None


def test_financial_reports_are_tenant_scoped_and_require_auth(client):
    owner = register(client, "reports-scope@example.com", "Reports Scope")
    other = register(client, "reports-other@example.com", "Other Reports")
    assert client.get("/api/v1/financial-reports/profit-loss?year=2026").status_code == 401
    headers = auth_headers(other)
    report = client.get("/api/v1/financial-reports/profit-loss?year=2026", headers=headers)
    assert report.status_code == 200
    assert report.json()["revenue"]["total"] == "0.00"
    assert report.json()["source_counts"]["pos_transactions"] == 0
