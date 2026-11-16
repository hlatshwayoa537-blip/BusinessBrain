def registration_payload(email="founder@example.com"):
    return {"full_name":"Test Founder","email":email,"password":"A-strong-test-password-123","business_name":"Example Trading","industry":"Retail","country":"ZA"}

def auth_headers(client):
    response = client.post("/api/v1/auth/register", json=registration_payload())
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

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

def test_business_profile_can_be_updated_and_retrieved(client):
    headers = auth_headers(client)
    update = client.patch("/api/v1/auth/business/profile", headers=headers, json={
        "registration_number": "2026/123456/07",
        "website": "https://example.co.za",
        "contact_email": "hello@example.co.za",
        "phone": "+27123456789",
        "address_line": "10 Main Road",
        "city": "Durban",
        "province": "KwaZulu-Natal",
        "postal_code": "4001",
        "description": "A retail business serving local customers."
    })
    assert update.status_code == 200
    assert update.json()["city"] == "Durban"
    assert update.json()["registration_number"] == "2026/123456/07"
    fetched = client.get("/api/v1/auth/business/profile", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["website"] == "https://example.co.za"

def test_business_profile_requires_authentication(client):
    response = client.patch("/api/v1/auth/business/profile", json={"city":"Durban"})
    assert response.status_code == 401

def test_business_profile_rejects_unsafe_website_format(client):
    headers = auth_headers(client)
    response = client.patch("/api/v1/auth/business/profile", headers=headers, json={"website":"example.co.za"})
    assert response.status_code == 422

def test_wrong_password_is_rejected(client):
    client.post("/api/v1/auth/register", json=registration_payload())
    response = client.post("/api/v1/auth/login", json={"email":"founder@example.com","password":"wrong-password"})
    assert response.status_code == 401

def test_registration_requires_strong_password(client):
    payload = registration_payload()
    payload["password"] = "short"
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


def test_business_network_directory_is_opt_in_and_respects_contact_privacy(client):
    owner_headers = auth_headers(client)
    update = client.patch("/api/v1/auth/business/profile", headers=owner_headers, json={
        "directory_listed": True,
        "contact_email": "public@example.co.za",
        "phone": "+27111222333",
        "website": "https://example.co.za",
        "city": "Durban",
        "province": "KwaZulu-Natal",
        "description": "Independent retail supplier.",
        "public_email": True,
        "public_phone": False,
        "public_website": True,
        "public_location": False,
    })
    assert update.status_code == 200
    assert update.json()["directory_listed"] is True
    results = client.get("/api/v1/network/businesses", headers=owner_headers)
    assert results.status_code == 200
    assert len(results.json()) == 1
    listed = results.json()[0]
    assert listed["contact_email"] == "public@example.co.za"
    assert listed["phone"] is None
    assert listed["website"] == "https://example.co.za"
    assert listed["city"] is None
    assert listed["province"] is None
    assert "registration_number" not in listed

def test_business_network_directory_excludes_unlisted_businesses(client):
    headers = auth_headers(client)
    response = client.get("/api/v1/network/businesses", headers=headers)
    assert response.status_code == 200
    assert response.json() == []

def test_business_network_directory_requires_authentication(client):
    response = client.get("/api/v1/network/businesses")
    assert response.status_code == 401


def register_second_business(client):
    payload = registration_payload("supplier@example.com")
    payload.update({"full_name":"Supplier Owner","business_name":"Supplier Co","industry":"Manufacturing"})
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    return response.json()

def test_private_invitation_requires_password_and_creates_conversation(client):
    host_headers = auth_headers(client)
    recipient = register_second_business(client)
    recipient_headers = {"Authorization": f"Bearer {recipient['access_token']}"}
    visible = client.patch("/api/v1/auth/business/profile", headers=recipient_headers, json={"directory_listed":True})
    assert visible.status_code == 200
    invite = client.post("/api/v1/network/invitations", headers=host_headers, json={
        "invited_business_id": recipient["business"]["id"],
        "invitation_message":"We would like to discuss a supplier partnership.",
        "access_password":"Separate-Secret-42"
    })
    assert invite.status_code == 201
    invitation_id = invite.json()["id"]
    wrong = client.post(f"/api/v1/network/invitations/{invitation_id}/accept", headers=recipient_headers, json={"access_password":"Wrong-Password-42"})
    assert wrong.status_code == 403
    accepted = client.post(f"/api/v1/network/invitations/{invitation_id}/accept", headers=recipient_headers, json={"access_password":"Separate-Secret-42"})
    assert accepted.status_code == 200
    assert accepted.json()["host_business_id"] != accepted.json()["invited_business_id"]
    assert client.get("/api/v1/network/conversations", headers=host_headers).json()[0]["id"] == accepted.json()["id"]

def test_conversation_messages_and_deal_room_are_shared_only_with_participants(client):
    host_headers = auth_headers(client)
    recipient = register_second_business(client)
    recipient_headers = {"Authorization": f"Bearer {recipient['access_token']}"}
    client.patch("/api/v1/auth/business/profile", headers=recipient_headers, json={"directory_listed":True})
    invite = client.post("/api/v1/network/invitations", headers=host_headers, json={
        "invited_business_id":recipient["business"]["id"],"access_password":"Separate-Secret-42"
    }).json()
    conversation = client.post(f"/api/v1/network/invitations/{invite['id']}/accept", headers=recipient_headers, json={"access_password":"Separate-Secret-42"}).json()
    conversation_id = conversation["id"]
    sent = client.post(f"/api/v1/network/conversations/{conversation_id}/messages", headers=host_headers, json={"body":"Hello, let's discuss a partnership."})
    assert sent.status_code == 201
    received = client.get(f"/api/v1/network/conversations/{conversation_id}/messages", headers=recipient_headers)
    assert received.status_code == 200
    assert received.json()[0]["body"] == "Hello, let's discuss a partnership."
    room = client.post(f"/api/v1/network/conversations/{conversation_id}/deal-room", headers=recipient_headers)
    assert room.status_code == 201
    room_id = room.json()["id"]
    deal_message = client.post(f"/api/v1/network/deal-rooms/{room_id}/messages", headers=host_headers, json={"body":"Our proposal is ready for review."})
    assert deal_message.status_code == 201
    status_update = client.patch(f"/api/v1/network/deal-rooms/{room_id}", headers=recipient_headers, json={"status":"proposal_submitted"})
    assert status_update.status_code == 200
    assert status_update.json()["status"] == "proposal_submitted"

def test_business_cannot_read_another_business_conversation(client):
    host_headers = auth_headers(client)
    recipient = register_second_business(client)
    outsider = registration_payload("outsider@example.com")
    outsider.update({"full_name":"Outsider","business_name":"Outsider Ltd","industry":"Services"})
    outsider_auth = client.post("/api/v1/auth/register", json=outsider).json()
    recipient_headers = {"Authorization":f"Bearer {recipient['access_token']}"}
    client.patch("/api/v1/auth/business/profile", headers=recipient_headers, json={"directory_listed":True})
    invite = client.post("/api/v1/network/invitations", headers=host_headers, json={"invited_business_id":recipient["business"]["id"],"access_password":"Separate-Secret-42"}).json()
    conversation = client.post(f"/api/v1/network/invitations/{invite['id']}/accept", headers=recipient_headers, json={"access_password":"Separate-Secret-42"}).json()
    outsider_headers = {"Authorization":f"Bearer {outsider_auth['access_token']}"}
    response = client.get(f"/api/v1/network/conversations/{conversation['id']}/messages", headers=outsider_headers)
    assert response.status_code == 404


def test_deal_room_quotation_is_shared_and_recipient_can_decide(client):
    host_headers = auth_headers(client)
    recipient = register_second_business(client)
    recipient_headers = {"Authorization": f"Bearer {recipient['access_token']}"}
    client.patch("/api/v1/auth/business/profile", headers=recipient_headers, json={"directory_listed": True})
    invite = client.post("/api/v1/network/invitations", headers=host_headers, json={"invited_business_id": recipient["business"]["id"], "access_password": "Separate-Secret-42"}).json()
    conversation = client.post(f"/api/v1/network/invitations/{invite['id']}/accept", headers=recipient_headers, json={"access_password": "Separate-Secret-42"}).json()
    room = client.post(f"/api/v1/network/conversations/{conversation['id']}/deal-room", headers=host_headers).json()
    quote = client.post(f"/api/v1/network/deal-rooms/{room['id']}/quotations", headers=host_headers, json={
        "title": "Supply of office equipment", "currency": "ZAR",
        "line_items": [{"description": "Laptop", "quantity": "2", "unit_price": "12500.00", "tax_rate": "15"}, {"description": "Delivery", "quantity": "1", "unit_price": "500.00", "tax_rate": "0"}],
        "notes": "Subject to final written agreement."
    })
    assert quote.status_code == 201
    body = quote.json()
    assert body["subtotal"] == "25500.00" and body["tax_total"] == "3750.00" and body["total"] == "29250.00"
    received = client.get(f"/api/v1/network/deal-rooms/{room['id']}/quotations", headers=recipient_headers)
    assert received.status_code == 200 and received.json()[0]["id"] == body["id"]
    accepted = client.post(f"/api/v1/network/quotations/{body['id']}/decision", headers=recipient_headers, json={"decision": "accepted", "note": "Approved for contract drafting."})
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"

def test_only_recipient_can_accept_a_quotation(client):
    host_headers = auth_headers(client)
    recipient = register_second_business(client)
    recipient_headers = {"Authorization": f"Bearer {recipient['access_token']}"}
    client.patch("/api/v1/auth/business/profile", headers=recipient_headers, json={"directory_listed": True})
    invite = client.post("/api/v1/network/invitations", headers=host_headers, json={"invited_business_id": recipient["business"]["id"], "access_password": "Separate-Secret-42"}).json()
    conversation = client.post(f"/api/v1/network/invitations/{invite['id']}/accept", headers=recipient_headers, json={"access_password": "Separate-Secret-42"}).json()
    room = client.post(f"/api/v1/network/conversations/{conversation['id']}/deal-room", headers=host_headers).json()
    quote = client.post(f"/api/v1/network/deal-rooms/{room['id']}/quotations", headers=host_headers, json={"title": "Monthly services", "currency": "ZAR", "line_items": [{"description": "Service", "quantity": 1, "unit_price": "1000.00"}]}).json()
    denied = client.post(f"/api/v1/network/quotations/{quote['id']}/decision", headers=host_headers, json={"decision": "accepted"})
    assert denied.status_code == 403
