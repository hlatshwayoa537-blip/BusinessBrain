def register(client, email, name, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": name, "email": email, "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Retail", "country": "ZA"
    })
    assert response.status_code == 201
    return response.json()


def auth_headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def test_inventory_stock_is_derived_from_recorded_movements(client):
    owner = register(client, "inventory-owner@example.com", "Inventory Owner", "Inventory Store")
    headers = auth_headers(owner)
    created = client.post("/api/v1/inventory/items", headers=headers, json={
        "name": "Cooking Oil 2L", "sku": "OIL-2L", "unit": "bottle", "reorder_level": "5"
    })
    assert created.status_code == 201
    item = created.json()
    assert item["stock_total"] == "0.000"
    assert item["stock_by_location"] == {}

    opening = client.post(f"/api/v1/inventory/items/{item['id']}/adjustments", headers=headers, json={
        "quantity_delta": "12", "location": "Main Store", "reason": "Physical opening stock count"
    })
    assert opening.status_code == 201
    assert opening.json()["stock_after"] == "12.000"

    rejected = client.post(f"/api/v1/inventory/items/{item['id']}/adjustments", headers=headers, json={
        "quantity_delta": "-13", "location": "Main Store", "reason": "Attempt to over-adjust"
    })
    assert rejected.status_code == 422

    stock = client.get("/api/v1/inventory/items", headers=headers)
    assert stock.status_code == 200
    assert stock.json()[0]["stock_total"] == "12.000"
    assert stock.json()[0]["stock_by_location"] == {"Main Store": "12.000"}
    movements = client.get("/api/v1/inventory/movements", headers=headers)
    assert movements.status_code == 200
    assert len(movements.json()) == 1
    assert movements.json()[0]["source_type"] == "manual_adjustment"


def test_purchase_order_goods_receipt_posts_only_linked_items_to_stock(client):
    owner = register(client, "inventory-receipt@example.com", "Receipt Owner", "Receipt Store")
    headers = auth_headers(owner)
    supplier = client.post("/api/v1/procurement/suppliers", headers=headers, json={"name": "Stock Supplier"})
    assert supplier.status_code == 201
    item = client.post("/api/v1/inventory/items", headers=headers, json={
        "name": "Coffee 500g", "sku": "COF-500", "unit": "pack"
    })
    assert item.status_code == 201

    order = client.post("/api/v1/procurement/purchase-orders", headers=headers, json={
        "supplier_id": supplier.json()["id"],
        "lines": [{
            "description": "Coffee 500g", "product_id": item.json()["id"],
            "quantity": "10", "unit_price": "45.00", "tax_rate": "15"
        }]
    })
    assert order.status_code == 201
    order_id = order.json()["id"]
    line_id = order.json()["lines"][0]["id"]
    assert order.json()["lines"][0]["product_id"] == item.json()["id"]

    submitted = client.post(f"/api/v1/procurement/purchase-orders/{order_id}/submit", headers=headers)
    assert submitted.status_code == 200
    received = client.post(f"/api/v1/procurement/purchase-orders/{order_id}/receive", headers=headers, json={
        "lines": [{"line_id": line_id, "quantity": "4"}],
        "location": "Durban Branch", "note": "First delivery", "idempotency_key": "inventory-receipt-first-0001"
    })
    assert received.status_code == 200
    assert received.json()["status"] == "partially_received"
    retried = client.post(f"/api/v1/procurement/purchase-orders/{order_id}/receive", headers=headers, json={
        "lines": [{"line_id": line_id, "quantity": "4"}],
        "location": "Durban Branch", "note": "First delivery", "idempotency_key": "inventory-receipt-first-0001"
    })
    assert retried.status_code == 200

    stock = client.get("/api/v1/inventory/items", headers=headers)
    assert stock.json()[0]["stock_total"] == "4.000"
    assert stock.json()[0]["stock_by_location"] == {"Durban Branch": "4.000"}

    movements = client.get("/api/v1/inventory/movements", headers=headers)
    assert len(movements.json()) == 1
    assert movements.json()[0]["movement_type"] == "purchase_receipt"
    assert movements.json()[0]["source_type"] == "purchase_order"


def test_inventory_catalogue_is_business_scoped_and_sku_unique(client):
    first = register(client, "inventory-scope-a@example.com", "Owner A", "Store A")
    second = register(client, "inventory-scope-b@example.com", "Owner B", "Store B")
    first_headers = auth_headers(first)
    second_headers = auth_headers(second)
    item = client.post("/api/v1/inventory/items", headers=first_headers, json={
        "name": "Private Item", "sku": "PRIVATE-01"
    })
    assert item.status_code == 201
    duplicate = client.post("/api/v1/inventory/items", headers=first_headers, json={
        "name": "Another Item", "sku": "private-01"
    })
    assert duplicate.status_code == 409
    assert client.get("/api/v1/inventory/items", headers=second_headers).json() == []
    foreign_adjustment = client.post(
        f"/api/v1/inventory/items/{item.json()['id']}/adjustments",
        headers=second_headers,
        json={"quantity_delta": "5", "location": "Main", "reason": "Should not cross tenant"},
    )
    assert foreign_adjustment.status_code == 404
