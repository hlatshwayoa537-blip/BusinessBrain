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
