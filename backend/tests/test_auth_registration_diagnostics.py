from uuid import uuid4

PREVIEW_ORIGIN = "https://preview--vexion-next-core.base44.app"


def registration_payload(email: str) -> dict:
    return {
        "full_name": "Registration Test Owner",
        "email": email,
        "password": "A-strong-test-password-123",
        "business_name": "Registration Test Business",
        "industry": "Retail",
        "country": "ZA",
    }


def test_invalid_referral_registration_does_not_reserve_email(client):
    email = f"invalid-referral-{uuid4().hex}@example.com"
    payload = registration_payload(email)
    payload["referral_code"] = "INVALID-CODE"

    rejected = client.post("/api/v1/auth/register", json=payload)

    assert rejected.status_code == 400
    assert rejected.json()["detail"] == "That VEXION referral code is not valid."

    # The failed referral check must not leave a partial user/business record.
    payload.pop("referral_code")
    accepted = client.post("/api/v1/auth/register", json=payload)

    assert accepted.status_code == 201
    assert accepted.json()["user"]["email"] == email
    assert accepted.json()["business"]["name"] == "Registration Test Business"


def test_base44_preview_can_preflight_registration(client):
    response = client.options(
        "/api/v1/auth/register",
        headers={
            "Origin": PREVIEW_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == PREVIEW_ORIGIN
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    assert "content-type" in response.headers.get("access-control-allow-headers", "").lower()


def test_untrusted_origin_cannot_preflight_registration(client):
    response = client.options(
        "/api/v1/auth/register",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_registration_validation_never_echoes_password(client):
    payload = registration_payload(f"short-password-{uuid4().hex}@example.com")
    payload["password"] = "too-short"

    response = client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert "detail" in body
    assert "input" not in str(body).lower()
    assert "too-short" not in str(body)


def test_registration_login_and_authenticated_workspace_round_trip(client):
    email = f"auth-round-trip-{uuid4().hex}@example.com"
    payload = registration_payload(email)

    registered = client.post("/api/v1/auth/register", json=payload)
    assert registered.status_code == 201
    access_token = registered.json()["access_token"]
    assert access_token

    headers = {"Authorization": f"Bearer {access_token}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == email

    workspaces = client.get("/api/v1/auth/businesses", headers=headers)
    assert workspaces.status_code == 200
    assert len(workspaces.json()) == 1
    assert workspaces.json()[0]["name"] == "Registration Test Business"

    login = client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": payload["password"]},
    )
    assert login.status_code == 200
    assert login.json()["user"]["email"] == email
    assert login.json()["business"]["name"] == "Registration Test Business"
