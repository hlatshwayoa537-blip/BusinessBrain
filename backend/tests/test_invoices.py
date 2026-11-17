from test_auth import registration_payload

def owner_headers(client, email="invoice-owner@example.com"):
    response = client.post("/api/v1/auth/register", json=registration_payload(email))
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def test_invoice_totals_and_status_workflow(client):
    headers = owner_headers(client)
    created = client.post("/api/v1/invoices", headers=headers, json={
        "customer_name": "Example Customer", "customer_email": "customer@example.com",
        "issue_date": "2026-11-17", "due_date": "2026-12-01", "currency": "ZAR",
        "lines": [
            {"description": "Retail analytics subscription", "quantity": "2", "unit_price": "1000.00", "tax_rate": "15"},
            {"description": "Setup service", "quantity": "1", "unit_price": "500.00", "tax_rate": "0"}
        ]
    })
    assert created.status_code == 201, created.text
    invoice = created.json()
    assert invoice["invoice_number"].startswith("VX-2026-")
    assert invoice["subtotal"] == "2500.00"
    assert invoice["tax_total"] == "300.00"
    assert invoice["total"] == "2800.00"
    assert invoice["status"] == "draft"
    assert len(invoice["lines"]) == 2
    sent = client.patch(f"/api/v1/invoices/{invoice['id']}/status", headers=headers, json={"status":"sent"})
    assert sent.status_code == 200 and sent.json()["status"] == "sent"
    paid = client.patch(f"/api/v1/invoices/{invoice['id']}/status", headers=headers, json={"status":"paid"})
    assert paid.status_code == 200 and paid.json()["paid_at"] is not None

def test_invoice_data_is_tenant_isolated(client):
    owner = owner_headers(client, "invoice-a@example.com")
    other = owner_headers(client, "invoice-b@example.com")
    created = client.post("/api/v1/invoices", headers=owner, json={
        "customer_name":"Private Customer","issue_date":"2026-11-17","due_date":"2026-11-20",
        "lines":[{"description":"Private service","quantity":"1","unit_price":"100","tax_rate":"15"}]
    }).json()
    assert client.get("/api/v1/invoices", headers=other).json() == []
    assert client.get(f"/api/v1/invoices/{created['id']}", headers=other).status_code == 404

def test_invoice_rejects_due_date_before_issue_date(client):
    headers = owner_headers(client)
    response = client.post("/api/v1/invoices", headers=headers, json={
        "customer_name":"Example Customer","issue_date":"2026-12-01","due_date":"2026-11-30",
        "lines":[{"description":"Service","quantity":"1","unit_price":"100","tax_rate":"15"}]
    })
    assert response.status_code == 422
