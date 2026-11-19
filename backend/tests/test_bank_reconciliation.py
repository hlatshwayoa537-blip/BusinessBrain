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


def test_bank_match_suggestions_require_exact_amount_and_date_and_confirm_expense_link(client):
    owner = register(client, "bank-match-owner@example.com", "Bank Match Owner", "Match Shop")
    headers = auth_headers(owner)
    expense = client.post("/api/v1/finance/transactions", headers=headers, json={
        "kind": "expense", "category": "Utilities", "description": "Electricity payment",
        "amount": "850.00", "status": "paid", "occurred_on": "2026-11-18",
        "paid_on": "2026-11-18", "reference": "ELEC-18",
    })
    assert expense.status_code == 201
    imported = client.post(
        "/api/v1/bank-reconciliation/imports?account_label=Operating%20Account",
        headers={**headers, "Content-Type": "text/csv"},
        content="date,description,amount,reference,transaction_id\n2026-11-19,Electricity debit,-850.00,ELEC-18,BANK-1\n",
    )
    assert imported.status_code == 201
    row = client.get("/api/v1/bank-reconciliation/transactions?reconciliation_status=unmatched", headers=headers).json()[0]
    suggestions = client.get(f"/api/v1/bank-reconciliation/transactions/{row['id']}/suggestions", headers=headers)
    assert suggestions.status_code == 200
    candidates = suggestions.json()["candidates"]
    assert len(candidates) == 1
    assert candidates[0]["source_type"] == "finance"
    assert candidates[0]["source_id"] == expense.json()["id"]
    assert candidates[0]["reference_match"] is True

    confirmed = client.post(
        f"/api/v1/bank-reconciliation/transactions/{row['id']}/match",
        headers=headers,
        json={"source_type": "finance", "source_id": expense.json()["id"]},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["matched_source_type"] == "finance"
    assert confirmed.json()["matched_source_id"] == expense.json()["id"]
    assert client.get(f"/api/v1/bank-reconciliation/transactions/{row['id']}/suggestions", headers=headers).status_code == 409


def test_bank_match_confirmation_rejects_non_candidate_and_tenant_leak(client):
    owner = register(client, "bank-match-scope-owner@example.com", "Bank Owner", "Owner Shop")
    other = register(client, "bank-match-scope-other@example.com", "Other Owner", "Other Shop")
    headers = auth_headers(owner)
    client.post(
        "/api/v1/bank-reconciliation/imports?account_label=Operating%20Account",
        headers={**headers, "Content-Type": "text/csv"},
        content="date,description,amount,transaction_id\n2026-11-19,Unrelated debit,-100.00,BANK-2\n",
    )
    row = client.get("/api/v1/bank-reconciliation/transactions", headers=headers).json()[0]
    foreign = client.post("/api/v1/finance/transactions", headers=auth_headers(other), json={
        "kind": "expense", "category": "Utilities", "description": "Foreign expense",
        "amount": "100.00", "status": "paid", "occurred_on": "2026-11-19",
    }).json()
    denied = client.post(
        f"/api/v1/bank-reconciliation/transactions/{row['id']}/match",
        headers=headers, json={"source_type": "finance", "source_id": foreign["id"]},
    )
    assert denied.status_code == 422
    assert client.get(f"/api/v1/bank-reconciliation/transactions/{row['id']}/suggestions", headers=auth_headers(other)).status_code == 404
