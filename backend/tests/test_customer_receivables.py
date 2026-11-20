def register(client, email, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": "Receivables Owner", "email": email, "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Services", "country": "ZA"
    })
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def make_invoice(client, auth, status="sent"):
    created = client.post("/api/v1/invoices", headers=auth, json={
        "customer_name": "Customer One", "customer_email": "customer@example.com",
        "issue_date": "2026-11-01", "due_date": "2026-11-10", "currency": "ZAR",
        "lines": [{"description": "Monthly service", "quantity": "1", "unit_price": "100.00", "tax_rate": "15"}]
    })
    assert created.status_code == 201, created.text
    invoice = created.json()
    if status == "draft":
        return invoice
    sent = client.patch(f"/api/v1/invoices/{invoice['id']}/status", headers=auth, json={"status": status})
    assert sent.status_code == 200
    return sent.json()


def test_customer_receivable_partial_and_full_receipts(client):
    auth = register(client, "customer-receipts@example.com", "Receipts Store")
    invoice = make_invoice(client, auth)
    url = f"/api/v1/receivables/invoices/{invoice['id']}/receipts"
    payload = {"amount": "50.00", "payment_date": "2026-11-19", "payment_method": "eft", "reference": "BANK-001", "idempotency_key": "customer-receipt-001"}
    first = client.post(url, headers=auth, json=payload)
    assert first.status_code == 201, first.text
    assert first.json()["receivable"]["amount_received"] == "50.00"
    assert first.json()["receivable"]["balance_due"] == "65.00"
    replay = client.post(url, headers=auth, json=payload)
    assert replay.status_code == 201 and replay.json()["replayed"] is True
    assert replay.json()["receivable"]["amount_received"] == "50.00"
    conflict = client.post(url, headers=auth, json={**payload, "amount": "51.00"})
    assert conflict.status_code == 409
    final = client.post(url, headers=auth, json={"amount": "65.00", "payment_date": "2026-11-20", "idempotency_key": "customer-receipt-002"})
    assert final.status_code == 201, final.text
    assert final.json()["receivable"]["balance_due"] == "0.00"
    assert final.json()["receivable"]["status"] == "paid"
    summary = client.get("/api/v1/receivables/summary", headers=auth).json()
    assert summary["open_invoice_count"] == 0
    assert summary["outstanding_by_currency"] == {}


def test_customer_receivables_are_tenant_scoped_and_reject_overpayment(client):
    owner = register(client, "customer-receivables-owner@example.com", "Receivables Owner")
    other = register(client, "customer-receivables-other@example.com", "Receivables Other")
    invoice = make_invoice(client, owner)
    url = f"/api/v1/receivables/invoices/{invoice['id']}/receipts"
    assert client.post(url, headers=other, json={"amount":"1.00","payment_date":"2026-11-20","idempotency_key":"foreign-receipt-001"}).status_code == 404
    over = client.post(url, headers=owner, json={"amount":"115.01","payment_date":"2026-11-20","idempotency_key":"over-receipt-001"})
    assert over.status_code == 409
    assert client.get("/api/v1/receivables/summary", headers=other).json()["invoices"] == []


def test_draft_invoice_cannot_receive_customer_payment(client):
    auth = register(client, "customer-receivables-draft@example.com", "Draft Receivables")
    invoice = make_invoice(client, auth, status="draft")
    response = client.post(f"/api/v1/receivables/invoices/{invoice['id']}/receipts", headers=auth, json={
        "amount":"10.00","payment_date":"2026-11-20","idempotency_key":"draft-receipt-001"
    })
    assert response.status_code == 409
