"""Tests for the Service Registry (Task 6)."""


def test_health(registry_client):
    assert registry_client.get("/health").status_code == 200


def test_register_and_discover(registry_client):
    resp = registry_client.post(
        "/register", json={"name": "products", "url": "http://127.0.0.1:5032"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "registered"

    found = registry_client.get("/discover/products")
    assert found.status_code == 200
    assert found.get_json()["url"] == "http://127.0.0.1:5032"


def test_discover_unknown_returns_404(registry_client):
    assert registry_client.get("/discover/nope").status_code == 404


def test_register_requires_fields(registry_client):
    assert registry_client.post("/register", json={"name": "x"}).status_code == 400


def test_list_services(registry_client):
    registry_client.post("/register", json={"name": "users", "url": "http://u"})
    registry_client.post("/register", json={"name": "products", "url": "http://p"})
    listing = registry_client.get("/services").get_json()
    assert listing == {"users": "http://u", "products": "http://p"}


def test_deregister(registry_client):
    registry_client.post("/register", json={"name": "users", "url": "http://u"})
    assert registry_client.post("/deregister", json={"name": "users"}).status_code == 200
    assert registry_client.get("/discover/users").status_code == 404
