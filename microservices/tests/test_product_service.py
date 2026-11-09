"""Component tests for the Product Service (Task 2)."""


def test_health(product_client):
    resp = product_client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "All good"


def test_list_products(product_client):
    resp = product_client.get("/")
    assert resp.status_code == 200
    products = resp.get_json()
    assert len(products) == 3
    assert {p["name"] for p in products} == {"Laptop", "Mouse", "Keyboard"}


def test_get_product_by_id(product_client):
    resp = product_client.get("/1")
    assert resp.status_code == 200
    product = resp.get_json()
    assert product["name"] == "Laptop"
    assert product["stock"] == 10


def test_get_missing_product_returns_404(product_client):
    assert product_client.get("/999").status_code == 404


def test_update_stock(product_client):
    resp = product_client.put("/1/stock", json={"stock": 30})
    assert resp.status_code == 200
    assert resp.get_json()["stock"] == 30
    # The change persisted.
    assert product_client.get("/1").get_json()["stock"] == 30


def test_update_stock_missing_product(product_client):
    assert product_client.put("/999/stock", json={"stock": 5}).status_code == 404


def test_update_stock_rejects_bad_value(product_client):
    assert product_client.put("/1/stock", json={"stock": -5}).status_code == 400
    assert product_client.put("/1/stock", json={}).status_code == 400
