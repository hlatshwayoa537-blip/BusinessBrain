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


def test_bank_match_suggestions_can_link_exact_pos_sale(client):
    owner = register(client, "bank-pos-match@example.com", "POS Match Owner", "POS Match Shop")
    headers = auth_headers(owner)
    connection = client.post("/api/v1/pos/connections", headers=headers, json={
        "provider_name": "Generic POS", "display_name": "Main till", "integration_method": "webhook"
    }).json()
    sale = {
        "external_transaction_id": "POS-SETTLE-100",
        "branch_name": "Bergville", "till_name": "Till 1",
        "transaction_type": "sale", "occurred_at": "2026-11-19T10:00:00+02:00",
        "currency": "ZAR", "gross_amount": "100.00", "discount_amount": "0.00",
        "tax_amount": "13.04", "net_amount": "100.00", "payment_method": "card",
    }
    ingested = client.post(
        f"/api/v1/pos/ingest/{connection['id']}",
        headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=sale,
    )
    assert ingested.status_code == 201
    imported = client.post(
        "/api/v1/bank-reconciliation/imports?account_label=Operating%20Account",
        headers={**headers, "Content-Type": "text/csv"},
        content="date,description,amount,reference\n2026-11-19,Card settlement,100.00,POS-SETTLE-100\n",
    )
    assert imported.status_code == 201
    row = client.get("/api/v1/bank-reconciliation/transactions?reconciliation_status=unmatched", headers=headers).json()[0]
    suggestions = client.get(f"/api/v1/bank-reconciliation/transactions/{row['id']}/suggestions", headers=headers).json()
    pos_candidates = [item for item in suggestions["candidates"] if item["source_type"] == "pos"]
    assert len(pos_candidates) == 1
    assert pos_candidates[0]["reference_match"] is True
    confirmed = client.post(
        f"/api/v1/bank-reconciliation/transactions/{row['id']}/match",
        headers=headers, json={"source_type": "pos", "source_id": pos_candidates[0]["source_id"]},
    )
    assert confirmed.status_code == 200
    shared_ledger = client.get(f"/api/v1/bank-reconciliation/transactions/{row['id']}/matches", headers=headers)
    assert shared_ledger.status_code == 200
    assert shared_ledger.json()["matched_source_count"] == 1
    assert shared_ledger.json()["matches"][0]["source_id"] == pos_candidates[0]["source_id"]
    history = client.get("/api/v1/bank-reconciliation/transactions", headers=headers).json()
    assert history[0]["matched_source_type"] == "pos"
    assert history[0]["matched_source_id"] == pos_candidates[0]["source_id"]


def test_pos_settlement_batch_requires_exact_total_and_returns_traceability(client):
    owner = register(client, "bank-batch-owner@example.com", "Batch Owner", "Batch Shop")
    headers = auth_headers(owner)
    connection = client.post("/api/v1/pos/connections", headers=headers, json={
        "provider_name": "Generic POS", "display_name": "Main till", "integration_method": "webhook"
    }).json()
    source_ids = []
    for external_id, amount in [("BATCH-1", "60.00"), ("BATCH-2", "40.00")]:
        payload = {
            "external_transaction_id": external_id, "branch_name": "Bergville", "till_name": "Till 1",
            "transaction_type": "sale", "occurred_at": "2026-11-18T10:00:00+02:00",
            "currency": "ZAR", "gross_amount": amount, "discount_amount": "0.00",
            "tax_amount": "0.00", "net_amount": amount, "payment_method": "card",
        }
        ingested = client.post(
            f"/api/v1/pos/ingest/{connection['id']}",
            headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=payload,
        )
        assert ingested.status_code == 201
        source_ids.append(ingested.json()["id"])
    imported = client.post(
        "/api/v1/bank-reconciliation/imports?account_label=Operating%20Account",
        headers={**headers, "Content-Type": "text/csv"},
        content="date,description,amount,reference\n2026-11-19,Card settlement,100.00,SET-BATCH-1\n",
    )
    assert imported.status_code == 201
    bank_row = client.get(
        "/api/v1/bank-reconciliation/transactions?reconciliation_status=unmatched", headers=headers
    ).json()[0]
    wrong_total = client.post(
        f"/api/v1/bank-reconciliation/transactions/{bank_row['id']}/batch-match",
        headers=headers, json={"source_ids": source_ids[:1]},
    )
    assert wrong_total.status_code == 422
    confirmed = client.post(
        f"/api/v1/bank-reconciliation/transactions/{bank_row['id']}/batch-match",
        headers=headers, json={"source_ids": source_ids},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["matched_source_count"] == 2
    assert confirmed.json()["signed_total"] == "100.00"
    matches = client.get(
        f"/api/v1/bank-reconciliation/transactions/{bank_row['id']}/matches", headers=headers
    )
    assert matches.status_code == 200
    assert {item["source_id"] for item in matches.json()["matches"]} == set(source_ids)


def test_pos_settlement_batch_cannot_reuse_source_or_cross_business(client):
    owner = register(client, "bank-batch-scope-owner@example.com", "Batch Owner", "Batch Owner Shop")
    other = register(client, "bank-batch-scope-other@example.com", "Other Owner", "Batch Other Shop")
    headers = auth_headers(owner)
    connection = client.post("/api/v1/pos/connections", headers=headers, json={
        "provider_name": "Generic POS", "display_name": "Main till", "integration_method": "webhook"
    }).json()
    source_ids = []
    for index in range(2):
        payload = {
            "external_transaction_id": f"SCOPE-{index}", "branch_name": "Branch", "till_name": "Till 1",
            "transaction_type": "sale", "occurred_at": "2026-11-18T10:00:00+02:00",
            "currency": "ZAR", "gross_amount": "50.00", "discount_amount": "0.00",
            "tax_amount": "0.00", "net_amount": "50.00", "payment_method": "card",
        }
        response = client.post(
            f"/api/v1/pos/ingest/{connection['id']}",
            headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=payload,
        )
        assert response.status_code == 201
        source_ids.append(response.json()["id"])
    for reference in ["BATCH-A", "BATCH-B"]:
        imported = client.post(
            "/api/v1/bank-reconciliation/imports?account_label=Operating%20Account",
            headers={**headers, "Content-Type": "text/csv"},
            content=f"date,description,amount,reference\n2026-11-19,Card settlement,100.00,{reference}\n",
        )
        assert imported.status_code == 201
    rows = client.get("/api/v1/bank-reconciliation/transactions?reconciliation_status=unmatched", headers=headers).json()
    assert len(rows) == 2
    first = client.post(
        f"/api/v1/bank-reconciliation/transactions/{rows[0]['id']}/batch-match",
        headers=headers, json={"source_ids": source_ids},
    )
    assert first.status_code == 200
    reused = client.post(
        f"/api/v1/bank-reconciliation/transactions/{rows[1]['id']}/batch-match",
        headers=headers, json={"source_ids": source_ids},
    )
    assert reused.status_code == 409
    denied = client.get(
        f"/api/v1/bank-reconciliation/transactions/{rows[0]['id']}/matches",
        headers=auth_headers(other),
    )
    assert denied.status_code == 404


def test_supplier_payment_exact_bank_match_and_duplicate_protection(client):
    owner = register(client, "bank-supplier-payment@example.com", "Supplier Bank Match Owner", "Supplier Bank Match Shop")
    headers = auth_headers(owner)
    supplier = client.post("/api/v1/procurement/suppliers", headers=headers, json={"name": "Verified Supplier"}).json()
    order = client.post("/api/v1/procurement/purchase-orders", headers=headers, json={
        "supplier_id": supplier["id"],
        "lines": [{"description": "Stock", "quantity": "10", "unit_price": "10.00", "tax_rate": "15"}],
    }).json()
    submitted = client.post(f"/api/v1/procurement/purchase-orders/{order['id']}/submit", headers=headers).json()
    line_id = submitted["lines"][0]["id"]
    received = client.post(f"/api/v1/procurement/purchase-orders/{order['id']}/receive", headers=headers, json={
        "lines": [{"line_id": line_id, "quantity": "10"}], "idempotency_key": "bank-payable-receipt-001",
    })
    assert received.status_code == 200
    invoice = client.post("/api/v1/supplier-invoices", headers=headers, json={
        "supplier_id": supplier["id"], "purchase_order_id": order["id"],
        "supplier_reference": "SUP-BANK-001", "invoice_date": "2026-11-19",
        "due_date": "2026-12-19", "currency": "ZAR",
        "stated_subtotal": "100.00", "stated_tax_total": "15.00", "stated_total": "115.00",
        "lines": [{"description": "Stock", "quantity": "10", "unit_price": "10.00",
                   "tax_rate": "15", "purchase_order_line_id": line_id}],
    }).json()
    approved = client.post(f"/api/v1/supplier-invoices/{invoice['id']}/approve", headers=headers, json={})
    assert approved.status_code == 200
    payment = client.post(f"/api/v1/supplier-invoices/{invoice['id']}/payments", headers=headers, json={
        "amount": "115.00", "payment_date": "2026-11-20", "payment_method": "eft",
        "reference": "EFT-SUP-001", "idempotency_key": "bank-supplier-payment-001",
    })
    assert payment.status_code == 201
    imported = client.post(
        "/api/v1/bank-reconciliation/imports?account_label=Operating%20Account",
        headers={**headers, "Content-Type": "text/csv"},
        content="date,description,amount,reference\n2026-11-20,Supplier EFT,-115.00,EFT-SUP-001\n",
    )
    assert imported.status_code == 201
    row = client.get("/api/v1/bank-reconciliation/transactions?reconciliation_status=unmatched", headers=headers).json()[0]
    suggestions = client.get(f"/api/v1/bank-reconciliation/transactions/{row['id']}/suggestions", headers=headers)
    assert suggestions.status_code == 200
    candidate = next(item for item in suggestions.json()["candidates"] if item["source_type"] == "supplier_payment")
    assert candidate["source_id"] == payment.json()["payment"]["id"]
    assert candidate["reference_match"] is True
    confirmed = client.post(f"/api/v1/bank-reconciliation/transactions/{row['id']}/match", headers=headers, json={
        "source_type": "supplier_payment", "source_id": candidate["source_id"],
    })
    assert confirmed.status_code == 200
    assert confirmed.json()["matched_source_type"] == "supplier_payment"
    replay_row = client.post(
        "/api/v1/bank-reconciliation/imports?account_label=Second%20Account",
        headers={**headers, "Content-Type": "text/csv"},
        content="date,description,amount,reference\n2026-11-20,Same supplier EFT,-115.00,EFT-SUP-001\n",
    )
    assert replay_row.status_code == 201
    second_row = client.get("/api/v1/bank-reconciliation/transactions?reconciliation_status=unmatched", headers=headers).json()[0]
    second_suggestions = client.get(f"/api/v1/bank-reconciliation/transactions/{second_row['id']}/suggestions", headers=headers).json()
    assert all(item["source_type"] != "supplier_payment" for item in second_suggestions["candidates"])



def test_bank_row_can_create_exact_paid_finance_entry_and_link_atomically(client):
    owner = register(client, "bank-create-ledger@example.com", "Ledger Owner", "Ledger Shop")
    headers = auth_headers(owner)
    imported = client.post(
        "/api/v1/bank-reconciliation/imports?account_label=Operating%20Account",
        headers={**headers, "Content-Type": "text/csv"},
        content="date,description,amount,reference\\n2026-11-19,Monthly electricity,-850.00,ELEC-LEDGER-1\\n",
    )
    assert imported.status_code == 201
    row = client.get("/api/v1/bank-reconciliation/transactions?reconciliation_status=unmatched", headers=headers).json()[0]
    created = client.post(
        f"/api/v1/bank-reconciliation/transactions/{row['id']}/create-finance-record",
        headers=headers,
        json={"kind": "expense", "category": "Utilities", "description": "Monthly electricity"},
    )
    assert created.status_code == 201
    result = created.json()
    assert result["finance_record"]["amount"] == "850.00"
    assert result["finance_record"]["kind"] == "expense"
    assert result["finance_record"]["status"] == "paid"
    assert result["finance_record"]["paid_on"] == "2026-11-19"
    assert result["reconciliation_status"] == "matched"
    finance_rows = client.get("/api/v1/finance/transactions", headers=headers).json()
    assert len(finance_rows) == 1
    assert finance_rows[0]["id"] == result["finance_record"]["id"]
    matches = client.get(f"/api/v1/bank-reconciliation/transactions/{row['id']}/matches", headers=headers).json()
    assert matches["matched_source_count"] == 1
    assert matches["matches"][0]["source_type"] == "finance"
    replay = client.post(
        f"/api/v1/bank-reconciliation/transactions/{row['id']}/create-finance-record",
        headers=headers,
        json={"kind": "expense", "category": "Utilities", "description": "Duplicate attempt"},
    )
    assert replay.status_code == 409
    assert len(client.get("/api/v1/finance/transactions", headers=headers).json()) == 1


def test_bank_row_finance_creation_enforces_direction_currency_and_business_scope(client):
    owner = register(client, "bank-create-scope@example.com", "Ledger Owner", "Ledger Shop")
    other = register(client, "bank-create-other@example.com", "Other Owner", "Other Ledger Shop")
    headers = auth_headers(owner)
    imported = client.post(
        "/api/v1/bank-reconciliation/imports?account_label=Operating%20Account",
        headers={**headers, "Content-Type": "text/csv"},
        content="date,description,amount\\n2026-11-19,Customer deposit,250.00\\n",
    )
    assert imported.status_code == 201
    row = client.get("/api/v1/bank-reconciliation/transactions?reconciliation_status=unmatched", headers=headers).json()[0]
    wrong_kind = client.post(
        f"/api/v1/bank-reconciliation/transactions/{row['id']}/create-finance-record",
        headers=headers, json={"kind": "expense", "category": "Other", "description": "Wrong direction"},
    )
    assert wrong_kind.status_code == 422
    denied = client.post(
        f"/api/v1/bank-reconciliation/transactions/{row['id']}/create-finance-record",
        headers=auth_headers(other), json={"kind": "income", "category": "Sales", "description": "Foreign attempt"},
    )
    assert denied.status_code == 404
    created = client.post(
        f"/api/v1/bank-reconciliation/transactions/{row['id']}/create-finance-record",
        headers=headers, json={"kind": "income", "category": "Sales", "description": "Customer deposit"},
    )
    assert created.status_code == 201
    assert created.json()["finance_record"]["amount"] == "250.00"
    assert created.json()["finance_record"]["kind"] == "income"
