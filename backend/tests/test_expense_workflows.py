def register(client, email):
    response = client.post("/api/v1/auth/register", json={
        "full_name": "Expense Owner",
        "email": email,
        "password": "A-strong-test-password-123",
        "business_name": "Expense Shop",
        "industry": "Retail",
        "country": "ZA",
    })
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_expense_due_date_and_mark_paid_workflow(client):
    auth = register(client, "expense-workflow-new@example.com")
    created = client.post("/api/v1/finance/transactions", headers=auth, json={
        "kind": "expense",
        "category": "Utilities",
        "description": "Electricity account",
        "amount": "850.00",
        "status": "unpaid",
        "occurred_on": "2026-11-10",
        "payee_name": "Local Electricity Provider",
        "due_on": "2026-11-20",
        "payment_method": "eft",
        "tax_amount": "110.87",
        "reference": "ELEC-2026-11",
    })
    assert created.status_code == 201
    record = created.json()
    assert record["payee_name"] == "Local Electricity Provider"
    assert record["due_on"] == "2026-11-20"
    assert record["paid_on"] is None
    assert record["payment_method"] == "eft"
    assert record["tax_amount"] == "110.87"

    paid = client.patch(
        f"/api/v1/finance/transactions/{record['id']}",
        headers=auth,
        json={"status": "paid", "paid_on": "2026-11-19"},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"
    assert paid.json()["paid_on"] == "2026-11-19"

    reopened = client.patch(
        f"/api/v1/finance/transactions/{record['id']}",
        headers=auth,
        json={"status": "unpaid"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "unpaid"
    assert reopened.json()["paid_on"] is None


def test_expense_details_cannot_be_attached_to_manual_income(client):
    auth = register(client, "expense-only-fields-new@example.com")
    response = client.post("/api/v1/finance/transactions", headers=auth, json={
        "kind": "income",
        "category": "Other income",
        "description": "Consulting",
        "amount": "100.00",
        "status": "paid",
        "occurred_on": "2026-11-19",
        "payee_name": "A supplier",
    })
    assert response.status_code == 422
