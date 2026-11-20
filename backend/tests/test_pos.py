from test_auth import registration_payload

def auth_headers(client, email="pos-owner@example.com"):
    payload = registration_payload(email)
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

def create_pos_connection(client, headers):
    return client.post("/api/v1/pos/connections", headers=headers, json={
        "provider_name": "Generic POS", "display_name": "Main till", "integration_method": "webhook"
    })

def test_pos_connection_secret_is_returned_once_and_never_listed(client):
    headers = auth_headers(client)
    created = create_pos_connection(client, headers)
    assert created.status_code == 201
    body = created.json()
    secret = body["webhook_secret"]
    assert len(secret) >= 40
    assert "secret_hash" not in body
    listed = client.get("/api/v1/pos/connections", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "webhook_secret" not in listed.json()[0]
    assert "secret_hash" not in listed.json()[0]

def test_pos_ingestion_is_authenticated_idempotent_and_summarized(client):
    headers = auth_headers(client)
    connection = create_pos_connection(client, headers).json()
    payload = {
        "external_transaction_id": "TILL-0001", "branch_name": "Durban",
        "till_name": "Till 1", "transaction_type": "sale",
        "occurred_at": "2026-11-17T10:00:00+02:00", "currency": "ZAR",
        "gross_amount": "115.00", "discount_amount": "0.00",
        "tax_amount": "15.00", "net_amount": "115.00", "payment_method": "card"
    }
    denied = client.post(f"/api/v1/pos/ingest/{connection['id']}", json=payload)
    assert denied.status_code == 401
    accepted = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=payload)
    assert accepted.status_code == 201
    duplicate = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=payload)
    assert duplicate.status_code == 409
    summary = client.get("/api/v1/pos/summary?days=7", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["sales_total"] == "115.00"
    assert summary.json()["net_sales"] == "115.00"
    assert summary.json()["transaction_count"] == 1

def test_pos_connections_are_isolated_between_businesses(client):
    owner = auth_headers(client, "pos-a@example.com")
    other = auth_headers(client, "pos-b@example.com")
    created = create_pos_connection(client, owner)
    assert created.status_code == 201
    assert client.get("/api/v1/pos/connections", headers=other).json() == []
    assert client.get("/api/v1/pos/transactions", headers=other).json() == []


def test_pos_analytics_report_daily_branch_and_till_performance(client):
    from datetime import datetime, timezone
    headers = auth_headers(client, "pos-analytics@example.com")
    connection = create_pos_connection(client, headers).json()
    secret = connection["webhook_secret"]
    timestamp = datetime.now(timezone.utc).isoformat()
    base = {
        "branch_name": "Durban Central", "till_name": "Till 03",
        "occurred_at": timestamp, "currency": "ZAR", "gross_amount": "115.00",
        "discount_amount": "0.00", "tax_amount": "15.00", "net_amount": "115.00",
        "payment_method": "card"
    }
    sale = {**base, "external_transaction_id": "ANALYTICS-SALE", "transaction_type": "sale"}
    refund = {**base, "external_transaction_id": "ANALYTICS-REFUND", "transaction_type": "refund", "gross_amount": "11.50", "tax_amount": "1.50", "net_amount": "11.50"}
    for payload in (sale, refund):
        response = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": secret}, json=payload)
        assert response.status_code == 201
    daily = client.get("/api/v1/pos/analytics/daily?days=30", headers=headers)
    assert daily.status_code == 200
    assert daily.json()["items"][0]["sales"] == "115.00"
    assert daily.json()["items"][0]["refunds"] == "11.50"
    assert daily.json()["items"][0]["net_sales"] == "103.50"
    branches = client.get("/api/v1/pos/analytics/branches?days=30", headers=headers)
    assert branches.status_code == 200
    assert branches.json()["items"][0]["branch"] == "Durban Central"
    tills = client.get("/api/v1/pos/analytics/tills?days=30", headers=headers)
    assert tills.status_code == 200
    assert tills.json()["items"][0]["till"] == "Till 03"
    assert tills.json()["items"][0]["net_sales"] == "103.50"


def test_csv_import_maps_columns_and_skips_duplicate_transactions(client):
    headers = auth_headers(client, "pos-csv@example.com")
    connection = create_pos_connection(client, headers).json()
    csv_text = (
        "Receipt,Date,Total,Branch,Till,Method\n"
        "CSV-100,2026-11-17T10:00:00+02:00,125.50,Durban,02,card\n"
        "CSV-100,2026-11-17T10:00:00+02:00,125.50,Durban,02,card\n"
    )
    mapping = {
        "external_transaction_id": "Receipt", "occurred_at": "Date",
        "gross_amount": "Total", "net_amount": "Total",
        "branch_name": "Branch", "till_name": "Till", "payment_method": "Method",
    }
    response = client.post(
        f"/api/v1/pos/connections/{connection['id']}/import-csv",
        headers=headers, json={"csv_text": csv_text, "mapping": mapping},
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 1
    assert response.json()["duplicates"] == 1
    transactions = client.get("/api/v1/pos/transactions", headers=headers)
    assert len(transactions.json()) == 1
    assert transactions.json()[0]["branch_name"] == "Durban"


def test_csv_import_rejects_invalid_rows(client):
    headers = auth_headers(client, "pos-csv-invalid@example.com")
    connection = create_pos_connection(client, headers).json()
    response = client.post(
        f"/api/v1/pos/connections/{connection['id']}/import-csv",
        headers=headers,
        json={"csv_text": "ID,Date,Gross,Net\nBAD,not-a-date,abc,xyz\n",
              "mapping": {"external_transaction_id":"ID","occurred_at":"Date","gross_amount":"Gross","net_amount":"Net"}},
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 0
    assert len(response.json()["rejected"]) == 1


def test_item_level_pos_sales_deduct_mapped_stock_once_and_refunds_do_not_restock(client):
    headers = auth_headers(client, "pos-item-lines@example.com")
    item = client.post("/api/v1/inventory/items", headers=headers, json={
        "name": "Coffee 500g", "sku": "COF-500", "unit": "pack"
    })
    assert item.status_code == 201
    item_id = item.json()["id"]
    opening = client.post(f"/api/v1/inventory/items/{item_id}/adjustments", headers=headers, json={
        "quantity_delta": "10", "location": "Durban Branch", "reason": "Verified opening stock count"
    })
    assert opening.status_code == 201

    connection = create_pos_connection(client, headers).json()
    secret = connection["webhook_secret"]
    sale = {
        "external_transaction_id": "ITEM-SALE-001",
        "branch_name": "Durban Branch", "till_name": "Till 1",
        "transaction_type": "sale", "occurred_at": "2026-11-18T10:00:00+02:00",
        "currency": "ZAR", "gross_amount": "85.00", "net_amount": "85.00",
        "items": [
            {"sku": "COF-500", "description": "Coffee 500g", "quantity": "3", "unit_price": "25.00"},
            {"sku": "UNKNOWN-1", "description": "Unmapped item", "quantity": "2", "unit_price": "5.00"}
        ]
    }
    accepted = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": secret}, json=sale)
    assert accepted.status_code == 201
    assert len(accepted.json()["items"]) == 2
    assert accepted.json()["items"][0]["inventory_item_id"] == item_id
    assert accepted.json()["items"][1]["inventory_item_id"] is None

    duplicate = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": secret}, json=sale)
    assert duplicate.status_code == 409
    stock = client.get("/api/v1/inventory/items", headers=headers)
    assert stock.json()[0]["stock_total"] == "7.000"
    assert stock.json()[0]["stock_by_location"] == {"Durban Branch": "7.000"}

    refund = {
        **sale, "external_transaction_id": "ITEM-REFUND-001", "transaction_type": "refund",
        "gross_amount": "25.00", "net_amount": "25.00",
        "items": [{"sku": "COF-500", "description": "Coffee 500g refund", "quantity": "1", "unit_price": "25.00"}]
    }
    refunded = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": secret}, json=refund)
    assert refunded.status_code == 201
    stock_after_refund = client.get("/api/v1/inventory/items", headers=headers)
    assert stock_after_refund.json()[0]["stock_total"] == "7.000"

    movements = client.get("/api/v1/inventory/movements", headers=headers)
    pos_movements = [row for row in movements.json() if row["source_type"] == "pos_transaction"]
    assert len(pos_movements) == 1
    assert pos_movements[0]["movement_type"] == "pos_sale"
    assert pos_movements[0]["quantity_delta"] == "-3.000"


def test_linked_pos_refund_uses_provider_external_references_and_restocking(client):
    headers = auth_headers(client, "pos-external-refund@example.com")
    item = client.post("/api/v1/inventory/items", headers=headers, json={
        "name": "Tea 1kg", "sku": "TEA-1KG", "unit": "bag"
    }).json()
    item_id = item["id"]
    client.post(f"/api/v1/inventory/items/{item_id}/adjustments", headers=headers, json={
        "quantity_delta": "10", "location": "Durban", "reason": "Opening count"
    })
    connection = create_pos_connection(client, headers).json()
    secret = connection["webhook_secret"]
    sale = {
        "external_transaction_id": "TILL-RECEIPT-9001",
        "branch_name": "Durban", "transaction_type": "sale",
        "occurred_at": "2026-11-18T10:00:00+02:00", "currency": "ZAR",
        "gross_amount": "100.00", "net_amount": "100.00",
        "items": [{
            "external_line_id": "TILL-LINE-1", "sku": "TEA-1KG",
            "description": "Tea 1kg", "quantity": "2", "unit_price": "50.00",
        }],
    }
    accepted_sale = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": secret}, json=sale)
    assert accepted_sale.status_code == 201
    assert accepted_sale.json()["items"][0]["external_line_id"] == "TILL-LINE-1"

    refund = {
        "external_transaction_id": "TILL-REFUND-9001",
        "original_external_transaction_id": "TILL-RECEIPT-9001",
        "branch_name": "Durban", "transaction_type": "refund",
        "occurred_at": "2026-11-19T10:00:00+02:00", "currency": "ZAR",
        "gross_amount": "50.00", "net_amount": "50.00",
        "items": [{
            "original_line_external_id": "TILL-LINE-1", "sku": "TEA-1KG",
            "description": "Tea refund", "quantity": "1", "unit_price": "50.00", "restock": True,
        }],
    }
    accepted_refund = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": secret}, json=refund)
    assert accepted_refund.status_code == 201
    assert accepted_refund.json()["items"][0]["original_line_id"] == accepted_sale.json()["items"][0]["id"]
    stock = client.get("/api/v1/inventory/items", headers=headers)
    assert stock.json()[0]["stock_total"] == "9.000"


def test_linked_refunds_cannot_over_refund_unmapped_pos_line(client):
    headers = auth_headers(client, "pos-over-refund@example.com")
    connection = create_pos_connection(client, headers).json()
    secret = connection["webhook_secret"]
    sale = {
        "external_transaction_id": "EXT-SALE-UNMAPPED",
        "transaction_type": "sale", "occurred_at": "2026-11-18T10:00:00+02:00",
        "currency": "ZAR", "gross_amount": "100.00", "net_amount": "100.00",
        "items": [{"description": "Untracked service", "quantity": "2", "unit_price": "50.00", "external_line_id": "SERVICE-LINE-1"}],
    }
    assert client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": secret}, json=sale).status_code == 201
    first_refund = {
        "external_transaction_id": "EXT-REFUND-1",
        "original_external_transaction_id": "EXT-SALE-UNMAPPED",
        "transaction_type": "refund", "occurred_at": "2026-11-19T10:00:00+02:00",
        "currency": "ZAR", "gross_amount": "50.00", "net_amount": "50.00",
        "items": [{"description": "Service refund", "quantity": "1", "unit_price": "50.00", "original_line_number": 1}],
    }
    accepted = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": secret}, json=first_refund)
    assert accepted.status_code == 201
    excess_refund = {
        **first_refund, "external_transaction_id": "EXT-REFUND-2",
        "items": [{"description": "Excess service refund", "quantity": "2", "unit_price": "50.00", "original_line_number": 1}],
    }
    rejected = client.post(f"/api/v1/pos/ingest/{connection['id']}", headers={"X-Vexion-Secret": secret}, json=excess_refund)
    assert rejected.status_code == 422



def test_pos_ingest_rejects_timezone_naive_timestamps(client):
    headers = auth_headers(client, "pos-naive-time@example.com")
    connection = create_pos_connection(client, headers).json()
    payload = {
        "external_transaction_id": "NAIVE-TIME-001",
        "transaction_type": "sale",
        "occurred_at": "2026-11-18T10:00:00",
        "currency": "ZAR",
        "gross_amount": "100.00",
        "net_amount": "100.00",
    }
    response = client.post(
        f"/api/v1/pos/ingest/{connection['id']}",
        headers={"X-Vexion-Secret": connection["webhook_secret"]},
        json=payload,
    )
    assert response.status_code == 422


def test_pos_daily_analytics_groups_transactions_by_south_african_local_date(client):
    headers = auth_headers(client, "pos-local-date@example.com")
    connection = create_pos_connection(client, headers).json()
    secret = connection["webhook_secret"]
    base = {
        "transaction_type": "sale",
        "currency": "ZAR",
        "gross_amount": "10.00",
        "net_amount": "10.00",
    }
    for transaction_id, timestamp in [
        ("LOCAL-DAY-1", "2026-11-18T21:30:00Z"),  # 23:30 in South Africa
        ("LOCAL-DAY-2", "2026-11-18T22:30:00Z"),  # 00:30 on the next local day
    ]:
        response = client.post(
            f"/api/v1/pos/ingest/{connection['id']}",
            headers={"X-Vexion-Secret": secret},
            json={**base, "external_transaction_id": transaction_id, "occurred_at": timestamp},
        )
        assert response.status_code == 201

    report = client.get("/api/v1/pos/analytics/daily?days=365", headers=headers)
    assert report.status_code == 200
    items = {item["date"]: item for item in report.json()["items"]}
    assert items["2026-11-18"]["sales"] == "10.00"
    assert items["2026-11-19"]["sales"] == "10.00"


def test_pos_csv_import_rejects_timezone_naive_rows(client):
    headers = auth_headers(client, "pos-csv-naive-time@example.com")
    connection = create_pos_connection(client, headers).json()
    csv_text = "ID,Date,Gross,Net\nNAIVE-CSV,2026-11-18T10:00:00,100.00,100.00\n"
    response = client.post(
        f"/api/v1/pos/connections/{connection['id']}/import-csv",
        headers=headers,
        json={
            "csv_text": csv_text,
            "mapping": {
                "external_transaction_id": "ID",
                "occurred_at": "Date",
                "gross_amount": "Gross",
                "net_amount": "Net",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["imported"] == 0
    assert len(response.json()["rejected"]) == 1
    assert "timezone offset" in response.json()["rejected"][0]["reason"]
