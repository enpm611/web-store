"""Component tests for the User Service (Task 1)."""


def test_health(user_client):
    resp = user_client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "All good"


def test_get_all_users(user_client):
    resp = user_client.get("/")
    assert resp.status_code == 200
    users = resp.get_json()
    assert len(users) == 2
    assert {u["name"] for u in users} == {"Alice", "Bob"}


def test_get_user_by_id(user_client):
    resp = user_client.get("/1")
    assert resp.status_code == 200
    assert resp.get_json() == {"id": 1, "name": "Alice", "email": "alice@example.com"}


def test_get_missing_user_returns_404(user_client):
    resp = user_client.get("/999")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_create_user(user_client):
    resp = user_client.post("/", json={"name": "Carol", "email": "carol@example.com"})
    assert resp.status_code == 201
    created = resp.get_json()
    assert created["name"] == "Carol"
    # The new user is retrievable.
    assert user_client.get(f"/{created['id']}").status_code == 200


def test_create_user_requires_fields(user_client):
    resp = user_client.post("/", json={"name": "NoEmail"})
    assert resp.status_code == 400
