from test_auth import registration_payload


def register_owner(client, email):
    response = client.post("/api/v1/auth/register", json=registration_payload(email))
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_billing_starts_inactive_and_prices_each_registered_pos_terminal(client):
    headers = register_owner(client, "billing-owner@example.com")
    overview = client.get("/api/v1/billing/me", headers=headers)
    assert overview.status_code == 200
    assert overview.json()["subscription_status"] == "not_started"
    assert overview.json()["payment_status"] == "not_configured"
    assert overview.json()["active_pos_terminals"] == 0
    assert overview.json()["estimated_monthly_total"] == "0.00"

    for index in range(1, 4):
        created = client.post("/api/v1/billing/terminals", headers=headers, json={
            "external_terminal_id": f"POS-{index}",
            "display_name": f"Till {index}",
            "branch_name": "Durban",
        })
        assert created.status_code == 201

    overview = client.get("/api/v1/billing/me", headers=headers)
    body = overview.json()
    assert body["active_pos_terminals"] == 3
    assert body["unit_price_per_pos_month"] == "499.00"
    assert body["estimated_monthly_total"] == "1497.00"
    assert body["subscription_status"] == "not_started"
    assert body["payment_status"] == "not_configured"
    assert "no payment has been collected" in body["notice"]


def test_inactive_terminal_is_not_counted_and_duplicate_terminal_is_rejected(client):
    headers = register_owner(client, "billing-terminals@example.com")
    created = client.post("/api/v1/billing/terminals", headers=headers, json={
        "external_terminal_id": "POS-01", "display_name": "Front till"
    })
    assert created.status_code == 201
    duplicate = client.post("/api/v1/billing/terminals", headers=headers, json={
        "external_terminal_id": "POS-01", "display_name": "Duplicate till"
    })
    assert duplicate.status_code == 409

    disabled = client.patch(
        f"/api/v1/billing/terminals/{created.json()['id']}",
        headers=headers,
        json={"status": "inactive"},
    )
    assert disabled.status_code == 200
    overview = client.get("/api/v1/billing/me", headers=headers).json()
    assert overview["active_pos_terminals"] == 0
    assert overview["inactive_pos_terminals"] == 1
    assert overview["estimated_monthly_total"] == "0.00"


def test_billing_terminal_registry_is_tenant_scoped(client):
    owner = register_owner(client, "billing-a@example.com")
    other = register_owner(client, "billing-b@example.com")
    created = client.post("/api/v1/billing/terminals", headers=owner, json={
        "external_terminal_id": "STORE-01", "display_name": "Main till"
    })
    assert created.status_code == 201
    overview = client.get("/api/v1/billing/me", headers=other)
    assert overview.status_code == 200
    assert overview.json()["active_pos_terminals"] == 0
    hidden = client.patch(
        f"/api/v1/billing/terminals/{created.json()['id']}",
        headers=other,
        json={"status": "inactive"},
    )
    assert hidden.status_code == 404


def test_billing_requires_authentication(client):
    assert client.get("/api/v1/billing/me").status_code == 401



def test_billing_discovers_pos_terminals_from_ingested_till_transactions(client):
    headers = register_owner(client, "billing-auto-discovery@example.com")
    connection = client.post("/api/v1/pos/connections", headers=headers, json={
        "provider_name": "Generic POS", "display_name": "Store POS", "integration_method": "webhook"
    }).json()
    secret = connection["webhook_secret"]
    base = {
        "occurred_at": "2026-11-17T10:00:00+02:00", "currency": "ZAR",
        "gross_amount": "100.00", "discount_amount": "0.00",
        "tax_amount": "0.00", "net_amount": "100.00", "payment_method": "card",
        "transaction_type": "sale",
    }
    records = [
        {**base, "external_transaction_id": "DISCOVER-1", "branch_name": "Durban", "till_name": "Till 01"},
        {**base, "external_transaction_id": "DISCOVER-2", "branch_name": "Durban", "till_name": "Till 02"},
        {**base, "external_transaction_id": "DISCOVER-3", "branch_name": "Pinetown", "till_name": "Till 01"},
    ]
    for payload in records:
        response = client.post(
            f"/api/v1/pos/ingest/{connection['id']}",
            headers={"X-Vexion-Secret": secret},
            json=payload,
        )
        assert response.status_code == 201

    overview = client.get("/api/v1/billing/me", headers=headers)
    assert overview.status_code == 200
    body = overview.json()
    assert body["active_pos_terminals"] == 3
    assert body["estimated_monthly_total"] == "1497.00"
    assert len(body["terminals"]) == 3
    assert all(row["source"] == "connected_pos_feed" for row in body["terminals"])
    assert {row["display_name"] for row in body["terminals"]} == {"Till 01", "Till 02"}
    assert {row["branch_name"] for row in body["terminals"]} == {"Durban", "Pinetown"}

    again = client.get("/api/v1/billing/me", headers=headers)
    assert len(again.json()["terminals"]) == 3


def test_billing_discovers_terminals_from_csv_imported_pos_data(client):
    headers = register_owner(client, "billing-csv-discovery@example.com")
    connection = client.post("/api/v1/pos/connections", headers=headers, json={
        "provider_name": "Generic POS", "display_name": "CSV POS", "integration_method": "webhook"
    }).json()
    csv_text = "Receipt,Date,Total,Branch,Till\nCSV-TILL-1,2026-11-17T10:00:00+02:00,120.00,Durban,Front\n"
    mapping = {
        "external_transaction_id": "Receipt", "occurred_at": "Date",
        "gross_amount": "Total", "net_amount": "Total",
        "branch_name": "Branch", "till_name": "Till",
    }
    imported = client.post(
        f"/api/v1/pos/connections/{connection['id']}/import-csv",
        headers=headers, json={"csv_text": csv_text, "mapping": mapping},
    )
    assert imported.status_code == 200
    assert imported.json()["imported"] == 1
    overview = client.get("/api/v1/billing/me", headers=headers)
    assert overview.status_code == 200
    assert overview.json()["active_pos_terminals"] == 1
    assert overview.json()["terminals"][0]["source"] == "connected_pos_feed"

def test_discovery_does_not_reactivate_a_manually_deactivated_terminal(client):
    headers = register_owner(client, "billing-discovery-deactivated@example.com")
    connection = client.post("/api/v1/pos/connections", headers=headers, json={
        "provider_name": "Generic POS", "display_name": "Store POS", "integration_method": "webhook"
    }).json()
    payload = {
        "external_transaction_id": "DEACTIVATE-01",
        "occurred_at": "2026-11-17T10:00:00+02:00",
        "currency": "ZAR", "gross_amount": "100.00", "discount_amount": "0.00",
        "tax_amount": "0.00", "net_amount": "100.00", "payment_method": "card",
        "transaction_type": "sale", "branch_name": "Durban", "till_name": "Front till",
    }
    ingested = client.post(
        f"/api/v1/pos/ingest/{connection['id']}",
        headers={"X-Vexion-Secret": connection["webhook_secret"]},
        json=payload,
    )
    assert ingested.status_code == 201

    first = client.get("/api/v1/billing/me", headers=headers).json()
    discovered = next(row for row in first["terminals"] if row["source"] == "connected_pos_feed")
    disabled = client.patch(
        f"/api/v1/billing/terminals/{discovered['id']}",
        headers=headers,
        json={"status": "inactive"},
    )
    assert disabled.status_code == 200

    refreshed = client.get("/api/v1/billing/me", headers=headers).json()
    terminal = next(row for row in refreshed["terminals"] if row["id"] == discovered["id"])
    assert terminal["status"] == "inactive"
    assert refreshed["active_pos_terminals"] == 0
    assert refreshed["inactive_pos_terminals"] == 1
    assert refreshed["estimated_monthly_total"] == "0.00"


def test_payfast_checkout_creates_pending_payment_without_activating_subscription(client, monkeypatch):
    from app.core.config import settings
    headers = register_owner(client, "payfast-checkout@example.com")
    terminal = client.post("/api/v1/billing/terminals", headers=headers, json={"external_terminal_id": "PF-01", "display_name": "Main till"})
    assert terminal.status_code == 201
    monkeypatch.setattr(settings, "payfast_merchant_id", "10000100")
    monkeypatch.setattr(settings, "payfast_merchant_key", "merchant-key")
    monkeypatch.setattr(settings, "payfast_passphrase", "test-pass")
    monkeypatch.setattr(settings, "payfast_sandbox", True)
    response = client.post("/api/v1/billing/payfast/checkout", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["amount"] == "499.00"
    assert body["status"] == "pending_verification"
    assert body["checkout_url"] == "https://sandbox.payfast.co.za/eng/process"
    assert body["fields"]["notify_url"].endswith("/api/v1/billing/payfast/itn")
    overview = client.get("/api/v1/billing/me", headers=headers).json()
    assert overview["subscription_status"] == "pending"
    assert overview["payment_status"] == "pending"
    assert overview["checkout_available"] is True


def test_payfast_checkout_requires_active_pos_terminal(client, monkeypatch):
    from app.core.config import settings
    headers = register_owner(client, "payfast-no-pos@example.com")
    monkeypatch.setattr(settings, "payfast_merchant_id", "10000100")
    monkeypatch.setattr(settings, "payfast_merchant_key", "merchant-key")
    monkeypatch.setattr(settings, "payfast_passphrase", "test-pass")
    response = client.post("/api/v1/billing/payfast/checkout", headers=headers)
    assert response.status_code == 400
    assert "active POS terminal" in response.json()["detail"]


def test_payfast_itn_rejects_invalid_signature(client, monkeypatch):
    from app.core.config import settings
    headers = register_owner(client, "payfast-itn-invalid@example.com")
    monkeypatch.setattr(settings, "payfast_merchant_id", "10000100")
    monkeypatch.setattr(settings, "payfast_passphrase", "test-pass")
    response = client.post(
        "/api/v1/billing/payfast/itn",
        content="merchant_id=10000100&m_payment_id=unknown&signature=bad",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    assert "signature" in response.json()["detail"].lower()


def test_verified_payfast_itn_activates_subscription_once(client, monkeypatch):
    from urllib.parse import urlencode
    from app.core.config import settings
    from app.services.payfast import generate_signature
    import app.api.routes.billing as billing_routes

    referrer_headers = register_owner(client, "payfast-referrer@example.com")
    referral_code = client.get("/api/v1/referrals/me", headers=referrer_headers).json()["referral_code"]
    referred_payload = registration_payload("payfast-verified@example.com")
    referred_payload["referral_code"] = referral_code
    referred = client.post("/api/v1/auth/register", json=referred_payload)
    assert referred.status_code == 201
    headers = {"Authorization": f"Bearer {referred.json()['access_token']}"}
    client.post("/api/v1/billing/terminals", headers=headers, json={
        "external_terminal_id": "PF-VERIFIED-01", "display_name": "Verified till"
    })
    monkeypatch.setattr(settings, "payfast_merchant_id", "10000100")
    monkeypatch.setattr(settings, "payfast_merchant_key", "merchant-key")
    monkeypatch.setattr(settings, "payfast_passphrase", "test-pass")
    monkeypatch.setattr(settings, "payfast_sandbox", True)
    checkout = client.post("/api/v1/billing/payfast/checkout", headers=headers)
    assert checkout.status_code == 200
    payment_reference = checkout.json()["payment_reference"]

    monkeypatch.setattr(billing_routes, "_payfast_source_allowed", lambda _address: True)
    async def fake_confirm(_body, _sandbox):
        return True
    monkeypatch.setattr(billing_routes, "_confirm_payfast_itn", fake_confirm)
    fields = {
        "merchant_id": "10000100",
        "m_payment_id": payment_reference,
        "pf_payment_id": "1089250",
        "payment_status": "COMPLETE",
        "item_name": "VEXION monthly subscription",
        "amount_gross": "499.00",
        "amount_fee": "0.00",
        "amount_net": "499.00",
        "currency": "ZAR",
        "token": "dc0521d3-55fe-269b-fa00-b647310d760f",
    }
    signature = generate_signature(fields, "test-pass", fields.keys())
    payload = urlencode({**fields, "signature": signature})
    notification = client.post(
        "/api/v1/billing/payfast/itn",
        content=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "CF-Connecting-IP": "197.97.145.144"},
    )
    assert notification.status_code == 200
    assert notification.json()["payment_status"] == "verified"
    assert notification.json()["referral_payment_verified"] is True
    referral_dashboard = client.get("/api/v1/referrals/me", headers=referrer_headers).json()
    assert referral_dashboard["payment_verified_referrals"] == 1
    assert referral_dashboard["discount_eligible"] is False
    assert referral_dashboard["referrals"][0]["status"] == "payment_verified"
    overview = client.get("/api/v1/billing/me", headers=headers).json()
    assert overview["subscription_status"] == "active"
    assert overview["payment_status"] == "paid"
    assert overview["subscription_update_available"] is True

    update_calls = []
    def fake_recurring_update(**kwargs):
        update_calls.append(kwargs)
        return 49900
    monkeypatch.setattr(billing_routes, "update_recurring_subscription_amount", fake_recurring_update)
    price_update = client.post("/api/v1/billing/payfast/update-amount", headers=headers)
    assert price_update.status_code == 200
    assert price_update.json()["recurring_amount"] == "499.00"
    assert price_update.json()["effective_for"] == "future recurring charges"
    assert update_calls[0]["token"] == "dc0521d3-55fe-269b-fa00-b647310d760f"
    assert update_calls[0]["amount"] == 499
    assert update_calls[0]["sandbox"] is True

    duplicate = client.post(
        "/api/v1/billing/payfast/itn",
        content=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "CF-Connecting-IP": "197.97.145.144"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True

    # Subsequent monthly charges may omit m_payment_id; the subscription token
    # identifies the active recurring subscription.
    recurring_fields = {key: value for key, value in fields.items() if key != "m_payment_id"}
    recurring_fields["pf_payment_id"] = "1089251"
    recurring_fields["amount_gross"] = "498.99"
    recurring_signature = generate_signature(recurring_fields, "test-pass", recurring_fields.keys())
    recurring_payload = urlencode({**recurring_fields, "signature": recurring_signature})
    wrong_amount = client.post(
        "/api/v1/billing/payfast/itn",
        content=recurring_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "CF-Connecting-IP": "197.97.145.144"},
    )
    assert wrong_amount.status_code == 400

    recurring_fields["pf_payment_id"] = "1089252"
    recurring_fields["amount_gross"] = "499.00"
    recurring_signature = generate_signature(recurring_fields, "test-pass", recurring_fields.keys())
    recurring_payload = urlencode({**recurring_fields, "signature": recurring_signature})
    recurring = client.post(
        "/api/v1/billing/payfast/itn",
        content=recurring_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "CF-Connecting-IP": "197.97.145.144"},
    )
    assert recurring.status_code == 200
    assert recurring.json()["recurring"] is True
    assert recurring.json()["subscription_status"] == "active"

    # PayFast cancellation notifications also identify the subscription by token
    # and do not necessarily include m_payment_id or amount_gross.
    cancelled_fields = {
        "merchant_id": "10000100",
        "pf_payment_id": "1089253",
        "payment_status": "CANCELLED",
        "item_name": "VEXION monthly subscription",
        "token": "dc0521d3-55fe-269b-fa00-b647310d760f",
    }
    cancelled_signature = generate_signature(cancelled_fields, "test-pass", cancelled_fields.keys())
    cancelled_payload = urlencode({**cancelled_fields, "signature": cancelled_signature})
    cancelled = client.post(
        "/api/v1/billing/payfast/itn",
        content=cancelled_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "CF-Connecting-IP": "197.97.145.144"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["subscription_status"] == "cancelled"
    after_cancel = client.get("/api/v1/referrals/me", headers=referrer_headers).json()
    assert after_cancel["payment_verified_referrals"] == 0
    assert after_cancel["referrals"][0]["status"] == "cancelled"
    assert client.get("/api/v1/billing/me", headers=headers).json()["subscription_status"] == "cancelled"

    # A business may subscribe again after cancellation. A delayed cancellation
    # from the old token must not cancel the new pending checkout.
    new_checkout = client.post("/api/v1/billing/payfast/checkout", headers=headers)
    assert new_checkout.status_code == 200
    old_cancel_fields = {
        "merchant_id": "10000100",
        "m_payment_id": payment_reference,
        "pf_payment_id": "1089254",
        "payment_status": "CANCELLED",
        "item_name": "VEXION monthly subscription",
        "token": "dc0521d3-55fe-269b-fa00-b647310d760f",
    }
    old_cancel_signature = generate_signature(old_cancel_fields, "test-pass", old_cancel_fields.keys())
    old_cancel_payload = urlencode({**old_cancel_fields, "signature": old_cancel_signature})
    delayed_cancel = client.post(
        "/api/v1/billing/payfast/itn",
        content=old_cancel_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "CF-Connecting-IP": "197.97.145.144"},
    )
    assert delayed_cancel.status_code == 200
    assert delayed_cancel.json()["subscription_status"] == "pending"

    new_token = "a3b3ae55-ab8b-b388-df23-4e6882b86ce0"
    new_payment_fields = {
        "merchant_id": "10000100",
        "m_payment_id": new_checkout.json()["payment_reference"],
        "pf_payment_id": "1089255",
        "payment_status": "COMPLETE",
        "item_name": "VEXION monthly subscription",
        "amount_gross": "499.00",
        "currency": "ZAR",
        "token": new_token,
    }
    new_payment_signature = generate_signature(new_payment_fields, "test-pass", new_payment_fields.keys())
    new_payment_payload = urlencode({**new_payment_fields, "signature": new_payment_signature})
    reactivated = client.post(
        "/api/v1/billing/payfast/itn",
        content=new_payment_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "CF-Connecting-IP": "197.97.145.144"},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["subscription_status"] == "active"
    reactivated_referral = client.get("/api/v1/referrals/me", headers=referrer_headers).json()
    assert reactivated_referral["payment_verified_referrals"] == 1
    assert reactivated_referral["referrals"][0]["status"] == "payment_verified"

    from sqlalchemy import func, select
    from app.db import get_db
    from app.main import app
    from app.models import PayFastCharge
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        charge_count = db.scalar(select(func.count(PayFastCharge.id)))
    finally:
        db_generator.close()
    assert charge_count == 5



def test_payfast_source_ip_uses_cloudflare_client_ip_not_spoofable_forwarded_for():
    from starlette.requests import Request
    from app.api.routes.billing import _payfast_request_ip

    request = Request({
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/api/v1/billing/payfast/itn",
        "raw_path": b"/api/v1/billing/payfast/itn",
        "query_string": b"",
        "headers": [
            (b"cf-connecting-ip", b"197.97.145.144"),
            (b"x-forwarded-for", b"41.74.179.193, 203.0.113.10"),
        ],
        "client": ("10.0.0.10", 12345),
        "server": ("vexion-api", 443),
    })
    assert _payfast_request_ip(request) == "197.97.145.144"


def test_payfast_source_ip_fails_closed_when_cloudflare_header_is_malformed():
    from starlette.requests import Request
    from app.api.routes.billing import _payfast_request_ip, _payfast_source_allowed

    request = Request({
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": "https",
        "path": "/api/v1/billing/payfast/itn",
        "raw_path": b"/api/v1/billing/payfast/itn",
        "query_string": b"",
        "headers": [(b"cf-connecting-ip", b"not-an-ip")],
        "client": ("10.0.0.10", 12345),
        "server": ("vexion-api", 443),
    })
    assert not _payfast_source_allowed(_payfast_request_ip(request))



def test_payfast_itn_requires_recurring_subscription_token(client, monkeypatch):
    from urllib.parse import urlencode
    from app.core.config import settings
    from app.services.payfast import generate_signature
    import app.api.routes.billing as billing_routes

    headers = register_owner(client, "payfast-token-required@example.com")
    client.post("/api/v1/billing/terminals", headers=headers, json={
        "external_terminal_id": "PF-TOKEN-01", "display_name": "Token required till"
    })
    monkeypatch.setattr(settings, "payfast_merchant_id", "10000100")
    monkeypatch.setattr(settings, "payfast_merchant_key", "merchant-key")
    monkeypatch.setattr(settings, "payfast_passphrase", "test-pass")
    monkeypatch.setattr(settings, "payfast_sandbox", True)
    checkout = client.post("/api/v1/billing/payfast/checkout", headers=headers)
    assert checkout.status_code == 200
    monkeypatch.setattr(billing_routes, "_payfast_source_allowed", lambda _address: True)

    async def fake_confirm(_body, _sandbox):
        return True

    monkeypatch.setattr(billing_routes, "_confirm_payfast_itn", fake_confirm)
    fields = {
        "merchant_id": "10000100",
        "m_payment_id": checkout.json()["payment_reference"],
        "pf_payment_id": "1089260",
        "payment_status": "COMPLETE",
        "item_name": "VEXION monthly subscription",
        "amount_gross": "499.00",
    }
    signature = generate_signature(fields, "test-pass", fields.keys())
    payload = urlencode({**fields, "signature": signature})
    response = client.post(
        "/api/v1/billing/payfast/itn",
        content=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded", "CF-Connecting-IP": "197.97.145.144"},
    )
    assert response.status_code == 400
    assert "subscription token" in response.json()["detail"].lower()
