def registration_payload(email):
    return {"full_name":"Test Founder","email":email,"password":"A-strong-test-password-123","business_name":"Example Trading","industry":"Retail","country":"ZA"}



def auth_headers(response):
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_referral_code_is_created_and_direct_registration_is_attributed(client):
    referrer = client.post("/api/v1/auth/register", json=registration_payload("referrer@example.com"))
    assert referrer.status_code == 201
    referrer_headers = auth_headers(referrer)

    dashboard = client.get("/api/v1/referrals/me", headers=referrer_headers)
    assert dashboard.status_code == 200
    code = dashboard.json()["referral_code"]
    assert code.startswith("VEX")
    assert dashboard.json()["registered_referrals"] == 0
    assert dashboard.json()["payment_verified_referrals"] == 0
    assert dashboard.json()["discount_eligible"] is False

    referred_payload = registration_payload("referred@example.com")
    referred_payload.update({
        "full_name": "Referred Owner",
        "business_name": "Referred Retail",
        "referral_code": code.lower(),
    })
    referred = client.post("/api/v1/auth/register", json=referred_payload)
    assert referred.status_code == 201

    refreshed = client.get("/api/v1/referrals/me", headers=referrer_headers)
    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["registered_referrals"] == 1
    assert body["referrals"][0]["business_name"] == "Referred Retail"
    assert body["referrals"][0]["status"] == "pending_payment"
    assert body["discount_eligible"] is False
    assert body["reward_terms"]["payment_verification_available"] is True


def test_invalid_referral_code_does_not_create_an_account(client):
    payload = registration_payload("invalid-ref@example.com")
    payload["referral_code"] = "VEXNOTREAL"
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "That VEXION referral code is not valid."
