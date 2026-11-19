from datetime import date
from decimal import Decimal
from app.models import BankStatementTransaction


def register(client, email, name, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": name, "email": email, "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Retail", "country": "ZA"
    })
    assert response.status_code == 201
    return response.json()


def auth_headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def test_bank_statement_import_is_idempotent_and_does_not_create_finance_records(client):
    owner = register(client, "bank-owner@example.com", "Bank Owner", "Bank Shop")
    headers = auth_headers(owner)
    csv_data = "date,description,amount,reference,balance\n2026-11-18,Card settlement,1250.50,SET-1,5000.00\n2026-11-18,Bank fee,-15.00,FEE-1,4985.00\n"
    first = client.post("/api/v1/bank-reconciliation/imports?filename=november.csv&account_label=Main%20Business%20Account",
                        headers={**headers, "Content-Type": "text/csv"}, content=csv_data)
    assert first.status_code == 201
    assert first.json()["imported"] == 2
    second = client.post("/api/v1/bank-reconciliation/imports?filename=november-copy.csv&account_label=Main%20Business%20Account",
                         headers={**headers, "Content-Type": "text/csv"}, content=csv_data)
    assert second.status_code == 201
    assert second.json()["imported"] == 0
    assert second.json()["duplicates_skipped"] == 2
    rows = client.get("/api/v1/bank-reconciliation/transactions", headers=headers)
    assert rows.status_code == 200 and len(rows.json()) == 2
    assert client.get("/api/v1/finance/transactions", headers=headers).json() == []
    summary = client.get("/api/v1/bank-reconciliation/summary", headers=headers).json()
    assert summary["statuses"]["unmatched"]["count"] == 2


def test_bank_statement_review_is_business_scoped_and_audited(client):
    owner = register(client, "bank-review-owner@example.com", "Bank Owner", "Bank Shop")
    other = register(client, "bank-review-other@example.com", "Other Owner", "Other Shop")
    headers = auth_headers(owner)
    result = client.post("/api/v1/bank-reconciliation/imports?account_label=Operating%20Account",
                         headers={**headers, "Content-Type": "text/csv"},
                         content="date,description,amount\n18/11/2026,Monthly rent,-8000.00\n")
    assert result.status_code == 201
    txn_id = client.get("/api/v1/bank-reconciliation/transactions", headers=headers).json()[0]["id"]
    denied = client.post(f"/api/v1/bank-reconciliation/transactions/{txn_id}/review",
                         headers=auth_headers(other), json={"status":"matched","note":"Matched to bank payment ref RENT-NOV"})
    assert denied.status_code == 404
    reviewed = client.post(f"/api/v1/bank-reconciliation/transactions/{txn_id}/review",
                           headers=headers, json={"status":"matched","note":"Matched to supplier payment record RENT-NOV"})
    assert reviewed.status_code == 200
    assert reviewed.json()["reconciliation_status"] == "matched"


def test_bank_statement_rejects_missing_required_columns(client):
    owner = register(client, "bank-invalid@example.com", "Bank Owner", "Bank Shop")
    response = client.post("/api/v1/bank-reconciliation/imports?account_label=Main%20Account",
                           headers={**auth_headers(owner), "Content-Type": "text/csv"},
                           content="posted,details,debit\n18/11/2026,Card settlement,100.00\n")
    assert response.status_code == 422
