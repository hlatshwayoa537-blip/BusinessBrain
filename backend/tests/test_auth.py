def registration_payload(email="founder@example.com"):
    return {"full_name":"Test Founder","email":email,"password":"A-strong-test-password-123","business_name":"Example Trading","industry":"Retail","country":"ZA"}

def test_register_creates_user_and_business_workspace(client):
    response = client.post("/api/v1/auth/register", json=registration_payload())
    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "founder@example.com"
    assert body["business"]["name"] == "Example Trading"
    assert len(body["access_token"]) > 20

def test_duplicate_email_is_rejected(client):
    client.post("/api/v1/auth/register", json=registration_payload())
    response = client.post("/api/v1/auth/register", json=registration_payload())
    assert response.status_code == 409

def test_login_and_authenticated_profile(client):
    client.post("/api/v1/auth/register", json=registration_payload())
    login = client.post("/api/v1/auth/login", json={"email":"FOUNDER@example.com","password":"A-strong-test-password-123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    profile = client.get("/api/v1/auth/me", headers={"Authorization":f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["email"] == "founder@example.com"

def test_wrong_password_is_rejected(client):
    client.post("/api/v1/auth/register", json=registration_payload())
    response = client.post("/api/v1/auth/login", json={"email":"founder@example.com","password":"wrong-password"})
    assert response.status_code == 401

def test_registration_requires_strong_password(client):
    payload = registration_payload()
    payload["password"] = "short"
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422
