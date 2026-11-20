from urllib.parse import urlparse, parse_qs

from app.api.routes import auth as auth_routes


def test_password_reset_is_one_time_and_revokes_existing_access_tokens(client, monkeypatch):
    monkeypatch.setattr(auth_routes.settings, "smtp_host", "smtp.example.co.za")
    monkeypatch.setattr(auth_routes.settings, "smtp_from_email", "no-reply@example.co.za")
    sent = []

    def fake_send(email, full_name, reset_url):
        sent.append({"email": email, "full_name": full_name, "reset_url": reset_url})

    monkeypatch.setattr(auth_routes, "send_password_reset_email", fake_send)
    registration = client.post("/api/v1/auth/register", json=registration_payload())
    assert registration.status_code == 201
    old_access_token = registration.json()["access_token"]

    request = client.post("/api/v1/auth/password-reset/request", json={"email": "FOUNDER@example.com"})
    assert request.status_code == 202
    assert request.json()["message"].startswith("If an active account exists")
    assert sent[0]["email"] == "founder@example.com"
    raw_token = parse_qs(urlparse(sent[0]["reset_url"]).query)["reset_token"][0]
    assert len(raw_token) >= 32

    # A second request inside the throttle window does not create another token or send another email.
    client.post("/api/v1/auth/password-reset/request", json={"email": "founder@example.com"})
    assert len(sent) == 1

    reset = client.post("/api/v1/auth/password-reset/confirm", json={
        "token": raw_token,
        "new_password": "A-new-strong-password-456",
    })
    assert reset.status_code == 200

    old_session = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access_token}"})
    assert old_session.status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "founder@example.com", "password": "A-strong-test-password-123"}).status_code == 401
    new_login = client.post("/api/v1/auth/login", json={"email": "founder@example.com", "password": "A-new-strong-password-456"})
    assert new_login.status_code == 200

    reused = client.post("/api/v1/auth/password-reset/confirm", json={
        "token": raw_token,
        "new_password": "Another-strong-password-789",
    })
    assert reused.status_code == 400


def test_password_reset_request_requires_smtp_configuration(client):
    response = client.post("/api/v1/auth/password-reset/request", json={"email": "unknown@example.com"})
    assert response.status_code == 503


def test_password_reset_unknown_email_uses_same_generic_response(client, monkeypatch):
    monkeypatch.setattr(auth_routes.settings, "smtp_host", "smtp.example.co.za")
    monkeypatch.setattr(auth_routes.settings, "smtp_from_email", "no-reply@example.co.za")
    sent = []
    monkeypatch.setattr(auth_routes, "send_password_reset_email", lambda *_args: sent.append(True))
    response = client.post("/api/v1/auth/password-reset/request", json={"email": "unknown@example.com"})
    assert response.status_code == 202
    assert response.json()["message"].startswith("If an active account exists")
    assert sent == []
