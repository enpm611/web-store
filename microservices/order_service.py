# order_service.py
#
# Task 3 (and Task 5: persistence, Task 6: service discovery).
#
# The Order Service orchestrates an order. Unlike the user and product
# services, it has to call the other services over REST (using `requests`) to
# validate the user, check the product, and decrement stock.
#
# The api_gateway forwards "/orders/<path>" to this service as "/<path>":
#   POST /       - create an order (also accepts PUT, per the assignment text)
#   GET  /<id>   - get an order by id
#   GET  /health - health check
#
# Orders are persisted in SQLite (Task 5); path set with ORDER_DB_PATH.
#
# Service discovery (Task 6): the URLs of the user and product services are
# resolved at call time, in this order of precedence:
#   1. USERS_SERVICE_URL / PRODUCTS_SERVICE_URL environment variables
#   2. the service registry at SERVICE_REGISTRY_URL (GET /discover/<name>)
#   3. the built-in defaults (127.0.0.1:5031 / 127.0.0.1:5032)
# This keeps the required Tasks 1-4 working with no registry running, while
# fully supporting the registry when it is.

import os
import sqlite3
from datetime import datetime

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SERVICE_NAME = "orders"
PORT = int(os.environ.get("ORDER_SERVICE_PORT", "5033"))

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("ORDER_DB_PATH", os.path.join(HERE, "orders.db"))

DEFAULT_URLS = {
    "users": "http://127.0.0.1:5031",
    "products": "http://127.0.0.1:5032",
}


class ServiceUnavailable(Exception):
    """Raised when a downstream service cannot be reached."""

    def __init__(self, service):
        self.service = service
        super().__init__(f"{service} service unavailable")


# --- Database helpers -------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity   INTEGER NOT NULL,
                total      REAL NOT NULL,
                status     TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def row_to_order(row):
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "product_id": row["product_id"],
        "quantity": row["quantity"],
        "total": row["total"],
        "status": row["status"],
        "created_at": row["created_at"],
    }


# --- Service discovery ------------------------------------------------------

def resolve_service_url(name):
    env = os.environ.get(f"{name.upper()}_SERVICE_URL")
    if env:
        return env.rstrip("/")
    registry = os.environ.get("SERVICE_REGISTRY_URL")
    if registry:
        try:
            resp = requests.get(f"{registry}/discover/{name}", timeout=2)
            if resp.status_code == 200:
                url = resp.json().get("url")
                if url:
                    return url.rstrip("/")
        except requests.exceptions.RequestException:
            pass  # fall through to the default
    return DEFAULT_URLS[name]


# --- Calls to the other services (the scaffold's TODO helpers) --------------

def get_user_object(user_id):
    """GET the user from the user service. None if 404; raises if unreachable."""
    url = f"{resolve_service_url('users')}/{user_id}"
    try:
        resp = requests.get(url, timeout=5)
    except requests.exceptions.RequestException:
        raise ServiceUnavailable("user")
    if resp.status_code == 404:
        return None
    if resp.status_code == 200:
        return resp.json()
    return None


def get_product_object(product_id):
    """GET the product from the product service. None if 404; raises if down."""
    url = f"{resolve_service_url('products')}/{product_id}"
    try:
        resp = requests.get(url, timeout=5)
    except requests.exceptions.RequestException:
        raise ServiceUnavailable("product")
    if resp.status_code == 404:
        return None
    if resp.status_code == 200:
        return resp.json()
    return None


def update_stock(product_id, stock):
    """PUT the new absolute stock value to the product service."""
    url = f"{resolve_service_url('products')}/{product_id}/stock"
    try:
        resp = requests.put(url, json={"stock": stock}, timeout=5)
    except requests.exceptions.RequestException:
        raise ServiceUnavailable("product")
    if resp.status_code == 200:
        return resp.json()
    return None


# --- Endpoints --------------------------------------------------------------

@app.route("/health", methods=["GET"])
def get_health():
    return jsonify({"status": "All good"}), 200


@app.route("/", methods=["POST", "PUT"])
def create_order():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid data"}), 400

    user_id = data.get("user_id")
    product_id = data.get("product_id")
    quantity = data.get("quantity", 1)

    if user_id is None or product_id is None:
        return jsonify({"error": "user_id and product_id are required"}), 400
    if not isinstance(quantity, int) or quantity <= 0:
        return jsonify({"error": "quantity must be a positive integer"}), 400

    try:
        # 1. Validate the user exists (call the user service).
        if not get_user_object(user_id):
            return jsonify({"error": "User not found"}), 404

        # 2. Check the product exists and has stock (call the product service).
        product = get_product_object(product_id)
        if not product:
            return jsonify({"error": "Product not found"}), 404
        if product["stock"] < quantity:
            return jsonify({"error": "Insufficient stock"}), 400

        # 3. Decrement stock (call the product service to set the new value).
        new_stock = product["stock"] - quantity
        if update_stock(product_id, new_stock) is None:
            return jsonify({"error": "Failed to update product stock"}), 502
    except ServiceUnavailable as exc:
        return jsonify({"error": f"{exc.service} service unavailable"}), 503

    # 4. Persist and return the order.
    total = round(product["price"] * quantity, 2)
    created_at = datetime.now().isoformat()
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO orders (user_id, product_id, quantity, total, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, product_id, quantity, total, "pending", created_at),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    finally:
        conn.close()
    return jsonify(row_to_order(row)), 201


@app.route("/<int:order_id>", methods=["GET"])
def get_order(order_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
    finally:
        conn.close()
    if row:
        return jsonify(row_to_order(row))
    return jsonify({"error": "Order not found"}), 404


# --- Service discovery registration (Task 6) --------------------------------

def register_with_registry():
    registry = os.environ.get("SERVICE_REGISTRY_URL")
    if not registry:
        return
    try:
        requests.post(
            f"{registry}/register",
            json={"name": SERVICE_NAME, "url": f"http://127.0.0.1:{PORT}"},
            timeout=2,
        )
        print(f"Registered '{SERVICE_NAME}' with registry at {registry}")
    except requests.exceptions.RequestException as exc:
        print(f"Could not register with registry ({exc}); continuing anyway.")


init_db()


if __name__ == "__main__":
    print(f"Order Service starting on http://127.0.0.1:{PORT} (db: {DB_PATH})")
    register_with_registry()
    app.run(host="0.0.0.0", port=PORT, debug=True)
