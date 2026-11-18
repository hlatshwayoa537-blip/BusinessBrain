from datetime import date
from decimal import Decimal
from app.models import FinanceTransaction, Membership, User

def register(client, email, name, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": name, "email": email, "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Retail", "country": "ZA"
    })
    assert response.status_code == 201
    return response.json()

def headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}

def test_finance_create_list_and_summary_are_business_scoped(client):
    owner = register(client, "finance-owner@example.com", "Finance Owner", "Owner Trading")
    other = register(client, "other-owner@example.com", "Other Owner", "Other Trading")
    created = client.post("/api/v1/finance/transactions", headers=headers(owner), json={
        "kind": "income", "category": "Sales", "description": "Daily shop sales",
        "amount": "1250.50", "status": "paid", "occurred_on": "2026-11-17"
    })
    assert created.status_code == 201
    assert created.json()["amount"] == "1250.50"
    expense = client.post("/api/v1/finance/transactions", headers=headers(owner), json={
        "kind": "expense", "category": "Rent", "description": "November rent",
        "amount": "500.00", "status": "paid", "occurred_on": "2026-11-01"
    })
    assert expense.status_code == 201
    unpaid = client.post("/api/v1/finance/transactions", headers=headers(owner), json={
        "kind": "income", "category": "Services", "description": "Invoice outstanding",
        "amount": "300.00", "status": "unpaid", "occurred_on": "2026-11-12"
    })
    assert unpaid.status_code == 201
    summary = client.get("/api/v1/finance/summary?year=2026", headers=headers(owner))
    assert summary.status_code == 200
    assert summary.json()["income_total"] == "1250.50"
    assert summary.json()["expense_total"] == "500.00"
    assert summary.json()["net_total"] == "750.50"
    assert summary.json()["outstanding_income"] == "300.00"
    assert summary.json()["transaction_count"] == 3
    assert client.get("/api/v1/finance/transactions", headers=headers(other)).json() == []

def test_finance_rejects_zero_or_negative_amounts(client):
    owner = register(client, "finance-validation@example.com", "Finance Owner", "Finance Co")
    response = client.post("/api/v1/finance/transactions", headers=headers(owner), json={
        "kind": "expense", "category": "Supplies", "description": "Invalid amount",
        "amount": "0", "occurred_on": "2026-11-17"
    })
    assert response.status_code == 422

def test_finance_requires_authentication(client):
    response = client.get("/api/v1/finance/summary")
    assert response.status_code == 401

def test_finance_delete_only_deletes_own_business_record(client):
    owner = register(client, "finance-delete@example.com", "Finance Owner", "Finance Co")
    other = register(client, "finance-other@example.com", "Other Owner", "Other Co")
    record = client.post("/api/v1/finance/transactions", headers=headers(owner), json={
        "kind": "expense", "category": "Utilities", "description": "Electricity",
        "amount": "450.00", "occurred_on": "2026-11-17"
    }).json()
    denied = client.delete("/api/v1/finance/transactions/" + record["id"], headers=headers(other))
    assert denied.status_code == 404
    deleted = client.delete("/api/v1/finance/transactions/" + record["id"], headers=headers(owner))
    assert deleted.status_code == 204


def test_finance_summary_includes_pos_sales_and_refunds_without_double_counting(client):
    owner = register(client, "finance-pos@example.com", "POS Finance Owner", "POS Finance Co")
    auth = headers(owner)
    connection = client.post("/api/v1/pos/connections", headers=auth, json={
        "provider_name": "Generic POS", "display_name": "Main till", "integration_method": "webhook"
    }).json()
    secret = connection["webhook_secret"]
    base = {
        "branch_name": "Bergville", "till_name": "Till 1",
        "occurred_at": "2026-11-17T10:00:00+02:00", "currency": "ZAR",
        "gross_amount": "115.00", "discount_amount": "0.00",
        "tax_amount": "15.00", "net_amount": "115.00", "payment_method": "card"
    }
    sale = {**base, "external_transaction_id": "FIN-POS-SALE", "transaction_type": "sale"}
    refund = {**base, "external_transaction_id": "FIN-POS-REFUND", "transaction_type": "refund",
              "gross_amount": "15.00", "tax_amount": "1.96", "net_amount": "15.00"}
    for payload in (sale, refund):
        response = client.post(
            f"/api/v1/pos/ingest/{connection['id']}",
            headers={"X-Vexion-Secret": secret}, json=payload
        )
        assert response.status_code == 201

    # Manual income is explicitly other income, not a duplicate of POS sales.
    manual_income = client.post("/api/v1/finance/transactions", headers=auth, json={
        "kind": "income", "category": "Other income", "description": "Non-POS service",
        "amount": "50.00", "status": "paid", "occurred_on": "2026-11-17"
    })
    assert manual_income.status_code == 201
    client.post("/api/v1/finance/transactions", headers=auth, json={
        "kind": "expense", "category": "Rent", "description": "Shop rent",
        "amount": "20.00", "status": "paid", "occurred_on": "2026-11-17"
    })

    summary = client.get("/api/v1/finance/summary?year=2026", headers=auth)
    assert summary.status_code == 200
    data = summary.json()
    assert data["pos_sales_total"] == "115.00"
    assert data["pos_refunds_total"] == "15.00"
    assert data["pos_net_income_total"] == "100.00"
    assert data["manual_income_total"] == "50.00"
    assert data["income_total"] == "150.00"
    assert data["expense_total"] == "20.00"
    assert data["net_total"] == "130.00"
    assert data["pos_transaction_count"] == 2
    assert data["months"][10]["income"] == "150.00"


def test_finance_pos_reporting_uses_south_african_business_calendar(client):
    owner = register(client, "finance-pos-calendar@example.com", "POS Calendar Owner", "POS Calendar Co")
    auth = headers(owner)
    connection = client.post("/api/v1/pos/connections", headers=auth, json={
        "provider_name": "Generic POS", "display_name": "Main till", "integration_method": "webhook"
    }).json()
    # 00:30 on 1 January in South Africa is still 31 December in UTC.
    payload = {
        "external_transaction_id": "FIN-POS-SA-YEAR-BOUNDARY",
        "branch_name": "Bergville", "till_name": "Till 1",
        "transaction_type": "sale", "occurred_at": "2026-01-01T00:30:00+02:00",
        "currency": "ZAR", "gross_amount": "200.00", "discount_amount": "0.00",
        "tax_amount": "26.09", "net_amount": "200.00", "payment_method": "card",
    }
    response = client.post(
        f"/api/v1/pos/ingest/{connection['id']}",
        headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=payload,
    )
    assert response.status_code == 201
    summary = client.get("/api/v1/finance/summary?year=2026", headers=auth)
    assert summary.status_code == 200
    data = summary.json()
    assert data["pos_sales_total"] == "200.00"
    assert data["pos_transaction_count"] == 1
    assert data["months"][0]["income"] == "200.00"
