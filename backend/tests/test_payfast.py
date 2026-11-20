from decimal import Decimal

from app.services.payfast import (
    CHECKOUT_URL_SANDBOX,
    build_subscription_checkout,
    cancel_recurring_subscription,
    generate_signature,
    verify_itn_signature,
    money_string,
)


def test_payfast_checkout_builds_monthly_subscription_and_signature():
    url, fields = build_subscription_checkout(
        merchant_id="10000100", merchant_key="merchant-key", passphrase="salt",
        sandbox=True, return_url="https://vexion.example/return",
        cancel_url="https://vexion.example/cancel",
        notify_url="https://vexion.example/api/v1/billing/payfast/itn",
        payment_id="payment-123", amount=Decimal("1497.00"),
        email="owner@example.com",
    )
    assert url == CHECKOUT_URL_SANDBOX
    assert fields["subscription_type"] == "1"
    assert fields["frequency"] == "3"
    assert fields["cycles"] == "0"
    assert fields["amount"] == "1497.00"
    assert fields["recurring_amount"] == "1497.00"
    assert fields["signature"] == generate_signature(
        {k: v for k, v in fields.items() if k != "signature"},
        "salt",
        [k for k in fields if k != "signature"],
    )


def test_payfast_itn_signature_verifies_in_received_order():
    fields = {"m_payment_id": "pay-1", "payment_status": "COMPLETE", "amount_gross": "499.00"}
    signature = generate_signature(fields, "salt", fields.keys())
    pairs = [*fields.items(), ("signature", signature)]
    assert verify_itn_signature(pairs, signature, "salt")
    assert not verify_itn_signature(pairs, "0" * 32, "salt")


def test_payfast_money_requires_minimum_recurring_amount():
    assert money_string("499") == "499.00"
    try:
        money_string("4.99")
    except ValueError:
        pass
    else:
        raise AssertionError("Amounts below PayFast minimum must be rejected.")



def test_payfast_subscription_cancellation_uses_signed_put(monkeypatch):
    import httpx

    calls = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "success", "data": {"response": True}}

    def fake_put(url, headers, timeout):
        calls.update(url=url, headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setattr(httpx, "put", fake_put)
    result = cancel_recurring_subscription(
        token="dc0521d3-55fe-269b-fa00-b647310d760f",
        merchant_id="10000100",
        passphrase="sandbox-pass",
        sandbox=True,
    )
    assert result is True
    assert calls["url"] == "https://api.payfast.co.za/subscriptions/dc0521d3-55fe-269b-fa00-b647310d760f/cancel?testing=true"
    assert calls["headers"]["merchant-id"] == "10000100"
    assert calls["headers"]["version"] == "v1"
    assert len(calls["headers"]["signature"]) == 32
    assert calls["timeout"] == 15.0


def test_payfast_subscription_cancellation_requires_provider_confirmation(monkeypatch):
    import httpx

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "success", "data": {"response": False}}

    monkeypatch.setattr(httpx, "put", lambda *args, **kwargs: Response())
    try:
        cancel_recurring_subscription(
            token="dc0521d3-55fe-269b-fa00-b647310d760f",
            merchant_id="10000100",
            passphrase="sandbox-pass",
            sandbox=True,
        )
    except ValueError as exc:
        assert "invalid subscription cancellation response" in str(exc).lower()
    else:
        raise AssertionError("Cancellation must fail unless PayFast confirms it.")
