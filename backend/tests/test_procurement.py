def register(client, email, name, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": name, "email": email, "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Retail", "country": "ZA"
    })
    assert response.status_code == 201
    return response.json()


def headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def test_supplier_purchase_order_and_goods_receipt_lifecycle(client):
    owner = register(client, "procurement-owner@example.com", "Procurement Owner", "Procurement Store")
    auth = headers(owner)
    supplier = client.post("/api/v1/procurement/suppliers", headers=auth, json={
        "name": "Fresh Produce Supplier", "contact_name": "Accounts Desk",
        "email": "accounts@example.co.za", "phone": "0100000000"
    })
    assert supplier.status_code == 201
    supplier_id = supplier.json()["id"]

    duplicate = client.post("/api/v1/procurement/suppliers", headers=auth, json={
        "name": "fresh produce supplier"
    })
    assert duplicate.status_code == 409

    order = client.post("/api/v1/procurement/purchase-orders", headers=auth, json={
        "supplier_id": supplier_id, "expected_delivery_date": "2026-12-01",
        "lines": [
            {"description": "Apples", "quantity": "10", "unit_price": "12.50", "tax_rate": "15"},
            {"description": "Bananas", "quantity": "5", "unit_price": "8.00", "tax_rate": "15"}
        ]
    })
    assert order.status_code == 201
    data = order.json()
    assert data["status"] == "draft"
    assert data["subtotal"] == "165.00"
    assert data["tax_total"] == "24.75"
    assert data["total"] == "189.75"

    submitted = client.post(f"/api/v1/procurement/purchase-orders/{data['id']}/submit", headers=auth)
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    apple_line = next(line for line in submitted.json()["lines"] if line["description"] == "Apples")
    partial = client.post(f"/api/v1/procurement/purchase-orders/{data['id']}/receive", headers=auth, json={
        "lines": [{"line_id": apple_line["id"], "quantity": "4"}], "note": "First delivery", "idempotency_key": "receipt-apples-first-0001"
    })
    assert partial.status_code == 200
    assert partial.json()["status"] == "partially_received"
    assert next(line for line in partial.json()["lines"] if line["id"] == apple_line["id"])["quantity_outstanding"] == "6.000"

    over_receive = client.post(f"/api/v1/procurement/purchase-orders/{data['id']}/receive", headers=auth, json={
        "lines": [{"line_id": apple_line["id"], "quantity": "7"}], "idempotency_key": "receipt-apples-over-0002"
    })
    assert over_receive.status_code == 422

    bananas = next(line for line in partial.json()["lines"] if line["description"] == "Bananas")
    finish = client.post(f"/api/v1/procurement/purchase-orders/{data['id']}/receive", headers=auth, json={
        "lines": [
            {"line_id": apple_line["id"], "quantity": "6"},
            {"line_id": bananas["id"], "quantity": "5"}
        ], "idempotency_key": "receipt-final-delivery-0003"
    })
    assert finish.status_code == 200
    assert finish.json()["status"] == "received"
    assert finish.json()["received_at"] is not None
    assert [event["event_type"] for event in finish.json()["events"]] == [
        "created", "submitted", "goods_received", "goods_received"
    ]


def test_procurement_records_are_business_scoped(client):
    owner = register(client, "procurement-scope-a@example.com", "Owner A", "Store A")
    other = register(client, "procurement-scope-b@example.com", "Owner B", "Store B")
    own_headers = headers(owner)
    other_headers = headers(other)
    supplier = client.post("/api/v1/procurement/suppliers", headers=own_headers, json={"name": "Private Supplier"})
    assert supplier.status_code == 201

    visible = client.get("/api/v1/procurement/suppliers", headers=own_headers)
    hidden = client.get("/api/v1/procurement/suppliers", headers=other_headers)
    assert len(visible.json()) == 1
    assert hidden.json() == []

    foreign_order = client.post("/api/v1/procurement/purchase-orders", headers=other_headers, json={
        "supplier_id": supplier.json()["id"],
        "lines": [{"description": "Goods", "quantity": "1", "unit_price": "10.00"}]
    })
    assert foreign_order.status_code == 404


def test_draft_purchase_order_can_be_edited_but_submitted_order_cannot(client):
    owner = register(client, "procurement-edit@example.com", "Edit Owner", "Edit Store")
    auth = headers(owner)
    supplier = client.post("/api/v1/procurement/suppliers", headers=auth, json={"name": "Edit Supplier"})
    order = client.post("/api/v1/procurement/purchase-orders", headers=auth, json={
        "supplier_id": supplier.json()["id"],
        "lines": [{"description": "Initial item", "quantity": "2", "unit_price": "5.00"}]
    })
    order_id = order.json()["id"]
    edited = client.patch(f"/api/v1/procurement/purchase-orders/{order_id}", headers=auth, json={
        "notes": "Updated delivery instructions",
        "lines": [{"description": "Replacement item", "quantity": "3", "unit_price": "7.00"}]
    })
    assert edited.status_code == 200
    assert edited.json()["notes"] == "Updated delivery instructions"
    assert edited.json()["lines"][0]["description"] == "Replacement item"
    submitted = client.post(f"/api/v1/procurement/purchase-orders/{order_id}/submit", headers=auth)
    assert submitted.status_code == 200
    locked = client.patch(f"/api/v1/procurement/purchase-orders/{order_id}", headers=auth, json={"notes": "Should not apply"})
    assert locked.status_code == 409


def test_supplier_name_cannot_be_blank_after_trimming(client):
    owner = register(client, "procurement-blank@example.com", "Blank Owner", "Blank Store")
    response = client.post("/api/v1/procurement/suppliers", headers=headers(owner), json={"name": "   "})
    assert response.status_code == 422
