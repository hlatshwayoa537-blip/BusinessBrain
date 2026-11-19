from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


TZ = ZoneInfo("Africa/Johannesburg")


def register(client, email, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": "Forecast Owner", "email": email,
        "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Retail", "country": "ZA"
    })
    assert response.status_code == 201
    return response.json()


def auth_headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def create_pos_connection(client, headers):
    response = client.post("/api/v1/pos/connections", headers=headers, json={
        "provider_name": "Generic POS", "display_name": "Forecast till", "integration_method": "webhook"
    })
    assert response.status_code == 201
    return response.json()


def test_forecast_requires_sufficient_history_and_does_not_invent_zero_days(client):
    owner = register(client, "forecast-empty@example.com", "Forecast Empty")
    response = client.get("/api/v1/business-intelligence/sales-forecast", headers=auth_headers(owner))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "insufficient_history"
    assert data["forecast"] == []
    assert data["projected_7_day_net_sales"] is None
    assert data["observed_days"] == 0
    assert data["history"] == []


def test_forecast_uses_observed_weekday_pos_averages(client):
    owner = register(client, "forecast-history@example.com", "Forecast History")
    headers = auth_headers(owner)
    connection = create_pos_connection(client, headers)
    today = datetime.now(TZ).date()

    # Populate 56 complete historical days, ending yesterday. Each weekday has
    # eight observed samples. Mondays also contain a refund to verify netting.
    for offset in range(56, 0, -1):
        local_day = today - timedelta(days=offset)
        occurred_at = datetime.combine(local_day, time(hour=12), tzinfo=TZ)
        sale = {
            "external_transaction_id": f"FORECAST-SALE-{local_day.isoformat()}",
            "branch_name": "Main", "till_name": "Till 1",
            "transaction_type": "sale", "occurred_at": occurred_at.isoformat(),
            "currency": "ZAR", "gross_amount": "100.00", "discount_amount": "0.00",
            "tax_amount": "0.00", "net_amount": "100.00", "payment_method": "cash",
        }
        response = client.post(
            f"/api/v1/pos/ingest/{connection['id']}",
            headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=sale,
        )
        assert response.status_code == 201
        if local_day.weekday() == 0:
            refund = {
                **sale,
                "external_transaction_id": f"FORECAST-REFUND-{local_day.isoformat()}",
                "transaction_type": "refund",
                "gross_amount": "20.00",
                "net_amount": "20.00",
            }
            response = client.post(
                f"/api/v1/pos/ingest/{connection['id']}",
                headers={"X-Vexion-Secret": connection["webhook_secret"]}, json=refund,
            )
            assert response.status_code == 201

    response = client.get("/api/v1/business-intelligence/sales-forecast", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["observed_days"] == 56
    assert len(data["history"]) == 56
    assert len(data["forecast"]) == 7
    assert data["forecast"][0]["date"] == today.isoformat()
    assert data["weekday_sample_counts"]["monday"] == 8
    assert data["forecast"][0]["projected_sales"] == "100.00"
    if today.weekday() == 0:
        assert data["forecast"][0]["projected_refunds"] == "20.00"
        assert data["forecast"][0]["projected_net_sales"] == "80.00"
    assert data["readiness"]["ready"] is True
    assert "feed completeness" in " ".join(data["limitations"]).lower()


def test_forecast_is_authenticated_and_tenant_scoped(client):
    owner = register(client, "forecast-scope@example.com", "Forecast Scope")
    other = register(client, "forecast-other@example.com", "Forecast Other")
    assert client.get("/api/v1/business-intelligence/sales-forecast").status_code == 401
    response = client.get("/api/v1/business-intelligence/sales-forecast", headers=auth_headers(other))
    assert response.status_code == 200
    assert response.json()["observed_days"] == 0
    assert response.json()["forecast"] == []
