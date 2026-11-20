def register(client, email, business):
    response = client.post("/api/v1/auth/register", json={
        "full_name": "Audit Owner", "email": email,
        "password": "A-strong-test-password-123",
        "business_name": business, "industry": "Retail", "country": "ZA",
    })
    assert response.status_code == 201
    return response.json()


def headers(auth):
    return {"Authorization": f"Bearer {auth['access_token']}"}


def test_activity_feed_aggregates_existing_daily_close_audit_and_scopes_business(client):
    owner = register(client, "activity-owner@example.com", "Activity Store")
    other = register(client, "activity-other@example.com", "Other Activity Store")
    auth = headers(owner)
    saved = client.post("/api/v1/daily-closes", headers=auth, json={
        "business_date": "2026-11-20", "branch_name": "Main branch",
        "expected_cash": "100.00", "expected_card": "0.00", "expected_other": "0.00",
        "actual_cash": "95.00", "actual_card": "0.00", "actual_other": "0.00",
        "notes": "Cash count",
    })
    assert saved.status_code == 201

    response = client.get("/api/v1/activity?source=daily_close&limit=10", headers=auth)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    event = payload["items"][0]
    assert event["source"] == "daily_close"
    assert event["action"] == "created"
    assert event["entity_id"] == saved.json()["id"]
    assert event["actor_user_id"] == owner["user"]["id"]
    assert event["actor_name"] == "Audit Owner"

    other_feed = client.get("/api/v1/activity", headers=headers(other))
    assert other_feed.status_code == 200
    assert other_feed.json()["total"] == 0


def test_activity_feed_validates_date_range_and_supports_pagination(client):
    owner = register(client, "activity-filters@example.com", "Filter Store")
    auth = headers(owner)
    invalid = client.get(
        "/api/v1/activity?from_date=2026-11-21&to_date=2026-11-20",
        headers=auth,
    )
    assert invalid.status_code == 422

    empty = client.get("/api/v1/activity?limit=1&offset=0", headers=auth)
    assert empty.status_code == 200
    assert empty.json()["items"] == []
    assert empty.json()["limit"] == 1
    assert empty.json()["offset"] == 0


def test_activity_feed_is_restricted_to_business_managers(client):
    owner = register(client, "activity-manager@example.com", "Manager Store")
    from app.db import get_db
    from app.main import app
    from app.models import Membership
    db_generator = app.dependency_overrides[get_db]()
    db = next(db_generator)
    try:
        membership = db.query(Membership).filter_by(user_id=owner["user"]["id"]).first()
        membership.role = "cashier"
        db.commit()
    finally:
        try:
            next(db_generator)
        except StopIteration:
            pass

    response = client.get("/api/v1/activity", headers=headers(owner))
    assert response.status_code == 403
