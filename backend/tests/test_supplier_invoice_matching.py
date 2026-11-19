def register(client, email, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": "Invoice Owner", "email": email, "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Retail", "country": "ZA"
    })
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def received_order(client, auth, supplier_name="Fresh Supplier"):
    supplier = client.post("/api/v1/procurement/suppliers", headers=auth, json={"name": supplier_name})
    assert supplier.status_code == 201
    order = client.post("/api/v1/procurement/purchase-orders", headers=auth, json={
        "supplier_id": supplier.json()["id"],
        "lines": [{"description": "Cooking oil", "quantity": "10", "unit_price": "10.00", "tax_rate": "15"}]
    })
    assert order.status_code == 201
    order_id = order.json()["id"]
    submitted = client.post(f"/api/v1/procurement/purchase-orders/{order_id}/submit", headers=auth)
    assert submitted.status_code == 200
    line_id = submitted.json()["lines"][0]["id"]
    received = client.post(f"/api/v1/procurement/purchase-orders/{order_id}/receive", headers=auth, json={
        "lines": [{"line_id": line_id, "quantity": "10"}],
        "idempotency_key": "receipt-cooking-oil-0001"
    })
    assert received.status_code == 200
    return supplier.json()["id"], order_id, line_id


def invoice_payload(supplier_id, order_id, line_id, reference="SUP-100"):
    return {
        "supplier_id": supplier_id, "purchase_order_id": order_id,
        "supplier_reference": reference, "invoice_date": "2026-11-19",
        "due_date": "2026-12-19", "currency": "ZAR",
        "stated_subtotal": "100.00", "stated_tax_total": "15.00", "stated_total": "115.00",
        "lines": [{
            "description": "Cooking oil", "quantity": "10", "unit_price": "10.00",
            "tax_rate": "15", "purchase_order_line_id": line_id
        }]
    }


def test_supplier_invoice_matches_po_and_goods_received_then_approves(client):
    auth = register(client, "supplier-invoice-match@example.com", "Invoice Match Store")
    supplier_id, order_id, line_id = received_order(client, auth)
    created = client.post("/api/v1/supplier-invoices", headers=auth, json=invoice_payload(supplier_id, order_id, line_id))
    assert created.status_code == 201, created.text
    invoice = created.json()
    assert invoice["status"] == "needs_review"
    assert invoice["match_results"]["status"] == "matched"
    assert invoice["match_results"]["flags"] == []
    assert invoice["match_results"]["automatically_posted_to_expenses_or_inventory"] is False
    approved = client.post(f"/api/v1/supplier-invoices/{invoice['id']}/approve", headers=auth, json={})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert [event["event_type"] for event in approved.json()["events"]] == ["created_and_matched", "approved"]


def test_supplier_invoice_flags_price_quantity_and_duplicate_reference(client):
    auth = register(client, "supplier-invoice-flags@example.com", "Invoice Flags Store")
    supplier_id, order_id, line_id = received_order(client, auth)
    bad = invoice_payload(supplier_id, order_id, line_id, "INV-202")
    bad["lines"][0].update({"quantity": "11", "unit_price": "12.00"})
    bad.update({"stated_subtotal": "132.00", "stated_tax_total": "19.80", "stated_total": "151.80"})
    created = client.post("/api/v1/supplier-invoices", headers=auth, json=bad)
    assert created.status_code == 201, created.text
    codes = {flag["code"] for flag in created.json()["match_results"]["flags"]}
    assert "unit_price_variance" in codes
    assert "billed_quantity_exceeds_received" in codes
    blocked = client.post(f"/api/v1/supplier-invoices/{created.json()['id']}/approve", headers=auth, json={})
    assert blocked.status_code == 409
    override = client.post(f"/api/v1/supplier-invoices/{created.json()['id']}/approve", headers=auth, json={
        "override_reason": "Manager checked supplier confirmation and approved."
    })
    assert override.status_code == 200
    assert override.json()["status"] == "approved"
    duplicate = client.post("/api/v1/supplier-invoices", headers=auth, json={
        **invoice_payload(supplier_id, order_id, line_id, "inv 202")
    })
    assert duplicate.status_code == 409


def test_supplier_invoices_are_tenant_isolated(client):
    owner = register(client, "supplier-invoice-a@example.com", "Supplier Invoice A")
    other = register(client, "supplier-invoice-b@example.com", "Supplier Invoice B")
    supplier_id, order_id, line_id = received_order(client, owner)
    invoice = client.post("/api/v1/supplier-invoices", headers=owner, json=invoice_payload(supplier_id, order_id, line_id))
    assert invoice.status_code == 201
    assert client.get("/api/v1/supplier-invoices", headers=other).json() == []
    assert client.get(f"/api/v1/supplier-invoices/{invoice.json()['id']}", headers=other).status_code == 404


def test_supplier_invoice_cannot_allocate_same_po_line_twice(client):
    auth = register(client, "supplier-invoice-repeat-line@example.com", "Repeated Line Store")
    supplier_id, order_id, line_id = received_order(client, auth)
    payload = invoice_payload(supplier_id, order_id, line_id, "INV-REPEAT")
    payload["lines"].append(dict(payload["lines"][0]))
    response = client.post("/api/v1/supplier-invoices", headers=auth, json=payload)
    assert response.status_code == 422
