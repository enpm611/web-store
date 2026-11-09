"""Integration tests for the Order Service (Task 3).

The order service calls the user and product services over HTTP. Here those
downstream calls are replaced with an in-memory fake so the order logic
(validation, stock check, decrement, error handling) can be tested
deterministically without running the other services.
"""

import requests


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def install_fakes(order_module, monkeypatch, users, products, down=None):
    """Patch order_module.requests.get/put with a fake user+product backend.

    `down` can be 'users' or 'products' to simulate an unreachable service.
    """

    def fake_get(url, timeout=None):
        if url.startswith("http://users.test/"):
            if down == "users":
                raise requests.exceptions.ConnectionError()
            uid = int(url.rsplit("/", 1)[1])
            if uid in users:
                return FakeResponse(200, users[uid])
            return FakeResponse(404, {"error": "User not found"})
        if url.startswith("http://products.test/"):
            if down == "products":
                raise requests.exceptions.ConnectionError()
            pid = int(url.rsplit("/", 1)[1])
            if pid in products:
                return FakeResponse(200, products[pid])
            return FakeResponse(404, {"error": "Product not found"})
        raise AssertionError(f"unexpected GET {url}")

    def fake_put(url, json=None, timeout=None):
        if down == "products":
            raise requests.exceptions.ConnectionError()
        # url: http://products.test/<id>/stock
        pid = int(url.rsplit("/", 2)[1])
        if pid not in products:
            return FakeResponse(404, {"error": "Product not found"})
        products[pid]["stock"] = json["stock"]
        return FakeResponse(200, products[pid])

    monkeypatch.setattr(order_module.requests, "get", fake_get)
    monkeypatch.setattr(order_module.requests, "put", fake_put)


def seed():
    users = {1: {"id": 1, "name": "Alice", "email": "alice@example.com"}}
    products = {1: {"id": 1, "name": "Laptop", "price": 999.99, "stock": 10}}
    return users, products


def test_health(order_client):
    resp = order_client.get("/health")
    assert resp.status_code == 200


def test_create_order_success(order_module, order_client, monkeypatch):
    users, products = seed()
    install_fakes(order_module, monkeypatch, users, products)

    resp = order_client.post("/", json={"user_id": 1, "product_id": 1, "quantity": 2})
    assert resp.status_code == 201
    order = resp.get_json()
    assert order["total"] == round(999.99 * 2, 2)
    assert order["status"] == "pending"
    # Stock was decremented via the product service.
    assert products[1]["stock"] == 8
    # The order was persisted and is retrievable.
    assert order_client.get(f"/{order['id']}").status_code == 200


def test_order_user_not_found(order_module, order_client, monkeypatch):
    users, products = seed()
    install_fakes(order_module, monkeypatch, users, products)
    resp = order_client.post("/", json={"user_id": 99, "product_id": 1, "quantity": 1})
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "User not found"


def test_order_product_not_found(order_module, order_client, monkeypatch):
    users, products = seed()
    install_fakes(order_module, monkeypatch, users, products)
    resp = order_client.post("/", json={"user_id": 1, "product_id": 99, "quantity": 1})
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "Product not found"


def test_order_insufficient_stock(order_module, order_client, monkeypatch):
    users, products = seed()
    install_fakes(order_module, monkeypatch, users, products)
    resp = order_client.post("/", json={"user_id": 1, "product_id": 1, "quantity": 999})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "Insufficient stock"
    # Stock unchanged because the order failed.
    assert products[1]["stock"] == 10


def test_order_user_service_unavailable(order_module, order_client, monkeypatch):
    users, products = seed()
    install_fakes(order_module, monkeypatch, users, products, down="users")
    resp = order_client.post("/", json={"user_id": 1, "product_id": 1, "quantity": 1})
    assert resp.status_code == 503


def test_order_product_service_unavailable(order_module, order_client, monkeypatch):
    users, products = seed()
    install_fakes(order_module, monkeypatch, users, products, down="products")
    resp = order_client.post("/", json={"user_id": 1, "product_id": 1, "quantity": 1})
    assert resp.status_code == 503


def test_order_invalid_body(order_client):
    assert order_client.post("/", data="not json",
                             content_type="text/plain").status_code == 400


def test_order_invalid_quantity(order_module, order_client, monkeypatch):
    users, products = seed()
    install_fakes(order_module, monkeypatch, users, products)
    resp = order_client.post("/", json={"user_id": 1, "product_id": 1, "quantity": 0})
    assert resp.status_code == 400


def test_get_missing_order(order_client):
    assert order_client.get("/4242").status_code == 404


def test_create_order_via_put(order_module, order_client, monkeypatch):
    # The assignment text describes the create endpoint as "PUT /".
    users, products = seed()
    install_fakes(order_module, monkeypatch, users, products)
    resp = order_client.put("/", json={"user_id": 1, "product_id": 1, "quantity": 1})
    assert resp.status_code == 201
