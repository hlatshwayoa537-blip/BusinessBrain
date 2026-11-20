"""PayFast hosted checkout and ITN signature helpers.

Payment status must only be changed after a verified PayFast ITN.
"""
from __future__ import annotations

import hashlib
import hmac
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote_plus
from collections.abc import Iterable, Mapping

CHECKOUT_URL_LIVE = "https://www.payfast.co.za/eng/process"
CHECKOUT_URL_SANDBOX = "https://sandbox.payfast.co.za/eng/process"

# PayFast custom checkout signature order. Do not alphabetize this list:
# the custom payment signature differs from the PayFast API signature.
CHECKOUT_FIELD_ORDER = (
    "merchant_id", "merchant_key", "return_url", "cancel_url", "notify_url",
    "name_first", "name_last", "email_address", "cell_number", "m_payment_id",
    "amount", "item_name", "item_description", "custom_int1", "custom_int2",
    "custom_int3", "custom_int4", "custom_int5", "custom_str1", "custom_str2",
    "custom_str3", "custom_str4", "custom_str5", "email_confirmation",
    "confirmation_address", "payment_method", "subscription_type", "billing_date",
    " recurring_amount", "frequency", "cycles",
)


def _encode(value: object) -> str:
    # PayFast requires PHP-style URL encoding: spaces as '+' and uppercase escapes.
    return quote_plus(str(value).strip(), safe="-_.~")


def signature_string(
    fields: Mapping[str, object],
    passphrase: str | None = None,
    order: Iterable[str] | None = None,
) -> str:
    keys = list(order) if order is not None else list(fields.keys())
    parts = []
    for key in keys:
        if key == "signature" or key not in fields:
            continue
        value = fields[key]
        if value is None or str(value).strip() == "":
            continue
        parts.append(f"{key}={_encode(value)}")
    result = "&".join(parts)
    if passphrase:
        result += ("&" if result else "") + f"passphrase={_encode(passphrase)}"
    return result


def generate_signature(
    fields: Mapping[str, object],
    passphrase: str | None = None,
    order: Iterable[str] | None = None,
) -> str:
    return hashlib.md5(signature_string(fields, passphrase, order).encode("utf-8")).hexdigest()


def verify_itn_signature(
    fields_in_order: Iterable[tuple[str, object]],
    supplied_signature: str,
    passphrase: str | None = None,
) -> bool:
    pairs = list(fields_in_order)
    ordered: dict[str, object] = {}
    for key, value in pairs:
        if key == "signature":
            break
        ordered[key] = value
    expected = generate_signature(ordered, passphrase, ordered.keys())
    return bool(supplied_signature) and hmac.compare_digest(expected, supplied_signature.lower())


def money_string(value: Decimal | str | int | float) -> str:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if not amount.is_finite() or amount < Decimal("5.00"):
        raise ValueError("PayFast recurring subscription amount must be at least R5.00.")
    return f"{amount:.2f}"


def build_subscription_checkout(
    *,
    merchant_id: str,
    merchant_key: str,
    passphrase: str,
    sandbox: bool,
    return_url: str,
    cancel_url: str,
    notify_url: str,
    payment_id: str,
    amount: Decimal | str,
    email: str,
    item_name: str = "VEXION monthly subscription",
    frequency: int = 3,
    cycles: int = 0,
) -> tuple[str, dict[str, str]]:
    """Build hosted monthly card subscription fields; no card data enters VEXION."""
    if not all((merchant_id, merchant_key, passphrase)):
        raise ValueError("PayFast merchant ID, key and subscription passphrase are required.")
    recurring_amount = money_string(amount)
    fields: dict[str, str] = {
        "merchant_id": merchant_id.strip(),
        "merchant_key": merchant_key.strip(),
        "return_url": return_url,
        "cancel_url": cancel_url,
        "notify_url": notify_url,
        "email_address": email.strip(),
        "m_payment_id": payment_id,
        "amount": recurring_amount,
        "item_name": item_name[:100],
        "subscription_type": "1",
        "frequency": str(frequency),
        "cycles": str(cycles),
        "recurring_amount": recurring_amount,
    }
    fields["signature"] = generate_signature(fields, passphrase, CHECKOUT_FIELD_ORDER)
    return (CHECKOUT_URL_SANDBOX if sandbox else CHECKOUT_URL_LIVE), fields
