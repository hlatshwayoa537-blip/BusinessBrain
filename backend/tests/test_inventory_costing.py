def register(client, email, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": "Costing Owner", "email": email,
        "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Retail", "country": "ZA"
    })
    assert response.status_code == 201
    return response.json()


def headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def prepare_receipt(client, auth_headers, sku="COST-01", quantity="10", unit_price="45.00"):
    supplier = client.post("/api/v1/procurement/suppliers", headers=auth_headers, json={"name": "Cost Supplier"})
    assert supplier.status_code == 201
    item = client.post("/api/v1/inventory/items", headers=auth_headers, json={
        "name": "Costed Product", "sku": sku, "unit": "each"
    })
    assert item.status_code == 201
    order = client.post("/api/v1/procurement/purchase-orders", headers=auth_headers, json={
        "supplier_id": supplier.json()["id"],
        "lines": [{
            "description": "Costed Product", "product_id": item.json()["id"],
            "quantity": quantity, "unit_price": unit_price, "tax_rate": "15"
        }]
    })
    assert order.status_code == 201
    order_id = order.json()["id"]
    line_id = order.json()["lines"][0]["id"]
    assert client.post(f"/api/v1/procurement/purchase-orders/{order_id}/submit", headers=auth_headers).status_code == 200
    received = client.post(f"/api/v1/procurement/purchase-orders/{order_id}/receive", headers=auth_headers, json={
        "lines": [{"line_id": line_id, "quantity": quantity}],
        "location": "Main", "note": "Costed delivery", "idempotency_key": "costing-receipt-00001"
    })
    assert received.status_code == 200
    return item.json()


def ingest_sale(client, auth_headers, sku, transaction_id="COST-SALE-1"):
    connection = client.post("/api/v1/pos/connections", headers=auth_headers, json={
        "provider_name": "Generic POS", "display_name": "Main till", "integration_method": "webhook"
    })
    assert connection.status_code == 201
    payload = {
        "external_transaction_id": transaction_id,
        "branch_name": "Main", "till_name": "Till 1",
        "transaction_type": "sale", "occurred_at": "2026-11-18T10:00:00+02:00",
        "currency": "ZAR", "gross_amount": "230.00", "discount_amount": "0.00",
        "tax_amount": "30.00", "net_amount": "230.00", "payment_method": "card",
        "items": [{"sku": sku, "description": "Costed Product", "quantity": "2", "unit_price": "100.00"}]
    }
    response = client.post(f"/api/v1/pos/ingest/{connection.json()['id']}", headers={
        "X-Vexion-Secret": connection.json()["webhook_secret"]
    }, json=payload)
    assert response.status_code == 201
    return response


def test_purchase_receipt_cost_flows_into_pos_cogs_and_profitability(client):
    owner = register(client, "cogs-complete@example.com", "COGS Complete Store")
    auth_headers = headers(owner)
    prepare_receipt(client, auth_headers)
    ingest_sale(client, auth_headers, "COST-01")

    movements = client.get("/api/v1/inventory/movements", headers=auth_headers)
    assert movements.status_code == 200
    pos_movement = next(row for row in movements.json() if row["movement_type"] == "pos_sale")
    assert pos_movement["unit_cost"] == "45.0000"

    profitability = client.get(
        "/api/v1/inventory/profitability?start_date=2026-11-01&end_date=2026-11-30",
        headers=auth_headers,
    )
    assert profitability.status_code == 200
    data = profitability.json()
    assert data["cost_status"] == "complete"
    assert data["cost_of_goods_sold"] == "90.00"
    assert data["products"][0]["gross_profit_before_transaction_discounts"] == "110.00"

    pnl = client.get("/api/v1/financial-reports/profit-loss?year=2026&month=11", headers=auth_headers)
    assert pnl.status_code == 200
    assert pnl.json()["cost_of_goods_sold"] == "90.00"
    assert pnl.json()["gross_profit"] == "140.00"
    assert pnl.json()["net_result"] == "140.00"


def test_missing_purchase_cost_is_never_reported_as_zero_cogs(client):
    owner = register(client, "cogs-missing@example.com", "COGS Missing Store")
    auth_headers = headers(owner)
    client.post("/api/v1/inventory/items", headers=auth_headers, json={
        "name": "Uncosted Product", "sku": "UNCOSTED-01", "unit": "each"
    })
    ingest_sale(client, auth_headers, "UNCOSTED-01", "UNCOSTED-SALE-1")

    profitability = client.get(
        "/api/v1/inventory/profitability?start_date=2026-11-01&end_date=2026-11-30",
        headers=auth_headers,
    )
    assert profitability.status_code == 200
    assert profitability.json()["cost_status"] == "incomplete"
    assert profitability.json()["cost_of_goods_sold"] is None
    assert profitability.json()["products"][0]["cost_of_goods_sold"] is None

    pnl = client.get("/api/v1/financial-reports/profit-loss?year=2026&month=11", headers=auth_headers)
    assert pnl.status_code == 200
    assert pnl.json()["cost_of_goods_sold"] is None
    assert pnl.json()["gross_profit"] is None
    assert pnl.json()["net_result"] is None

def test_unknown_opening_stock_prevents_false_cogs_even_after_receipts(client):
    owner = register(client, "cogs-opening@example.com", "Opening Stock Store")
    auth_headers = headers(owner)
    prepare_receipt(client, auth_headers, sku="OPENING-01")
    item = client.get("/api/v1/inventory/items", headers=auth_headers).json()[0]
    adjustment = client.post(f"/api/v1/inventory/items/{item['id']}/adjustments", headers=auth_headers, json={
        "quantity_delta": "5", "location": "Main", "reason": "Opening count with no valuation"
    })
    assert adjustment.status_code == 201
    ingest_sale(client, auth_headers, "OPENING-01", "OPENING-UNCOSTED-SALE")

    profitability = client.get(
        "/api/v1/inventory/profitability?start_date=2026-11-01&end_date=2026-11-30",
        headers=auth_headers,
    )
    assert profitability.status_code == 200
    assert profitability.json()["cost_status"] == "incomplete"
    assert profitability.json()["cost_of_goods_sold"] is None



def test_pos_refund_keeps_cogs_incomplete_until_return_cost_is_reversed(client):
    owner = register(client, "cogs-refund@example.com", "Refund Cost Store")
    auth_headers = headers(owner)
    prepare_receipt(client, auth_headers, sku="REFUND-01")
    ingest_sale(client, auth_headers, "REFUND-01", "REFUND-SALE-1")

    connection = client.post("/api/v1/pos/connections", headers=auth_headers, json={
        "provider_name": "Generic POS", "display_name": "Refund till", "integration_method": "webhook"
    })
    assert connection.status_code == 201
    refund = client.post(f"/api/v1/pos/ingest/{connection.json()['id']}", headers={
        "X-Vexion-Secret": connection.json()["webhook_secret"]
    }, json={
        "external_transaction_id": "REFUND-1", "branch_name": "Main", "till_name": "Till 1",
        "transaction_type": "refund", "occurred_at": "2026-11-18T11:00:00+02:00",
        "currency": "ZAR", "gross_amount": "100.00", "discount_amount": "0.00",
        "tax_amount": "13.04", "net_amount": "100.00", "payment_method": "card",
        "items": [{"sku": "REFUND-01", "description": "Costed Product", "quantity": "1", "unit_price": "100.00"}]
    })
    assert refund.status_code == 201

    profitability = client.get(
        "/api/v1/inventory/profitability?start_date=2026-11-01&end_date=2026-11-30",
        headers=auth_headers,
    )
    assert profitability.status_code == 200
    assert profitability.json()["refund_transaction_count"] == 1
    assert profitability.json()["cost_status"] == "incomplete"
    assert profitability.json()["cost_of_goods_sold"] is None
