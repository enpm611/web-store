# product_service.py
#
# Task 2 (and Task 5: database per service).
#
# The Product Service owns the product catalog and stock. It runs on port 5032.
# The api_gateway forwards "/products/<path>" to this service as "/<path>", so
# the routes are root-relative:
#   GET  /            - list all products
#   GET  /<id>        - get a product by id
#   PUT  /<id>/stock  - set a product's stock (called by the order service)
#   GET  /health      - health check
#
# Data is persisted in SQLite (Task 5); the path is set with PRODUCT_DB_PATH.
# Task 6: registers with SERVICE_REGISTRY_URL on startup if configured.

import os
import sqlite3

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SERVICE_NAME = "products"
PORT = int(os.environ.get("PRODUCT_SERVICE_PORT", "5032"))

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("PRODUCT_DB_PATH", os.path.join(HERE, "products.db"))

# Seed data migrated from the monolith's in-memory store.
SEED_PRODUCTS = [
    {"id": 1, "name": "Laptop", "price": 999.99, "stock": 10},
    {"id": 2, "name": "Mouse", "price": 29.99, "stock": 50},
    {"id": 3, "name": "Keyboard", "price": 79.99, "stock": 30},
]


# --- Database helpers -------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the products table and seed it once if it is empty."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id    INTEGER PRIMARY KEY,
                name  TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO products (id, name, price, stock) "
                "VALUES (:id, :name, :price, :stock)",
                SEED_PRODUCTS,
            )
        conn.commit()
    finally:
        conn.close()


def row_to_product(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "price": row["price"],
        "stock": row["stock"],
    }


def fetch_product(conn, product_id):
    return conn.execute(
        "SELECT id, name, price, stock FROM products WHERE id = ?", (product_id,)
    ).fetchone()


# --- Endpoints --------------------------------------------------------------

@app.route("/health", methods=["GET"])
def get_health():
    return jsonify({"status": "All good"}), 200


@app.route("/", methods=["GET"])
def get_products():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, price, stock FROM products ORDER BY id"
        ).fetchall()
        return jsonify([row_to_product(r) for r in rows])
    finally:
        conn.close()


@app.route("/<int:product_id>", methods=["GET"])
def get_product(product_id):
    conn = get_connection()
    try:
        row = fetch_product(conn, product_id)
    finally:
        conn.close()
    if row:
        return jsonify(row_to_product(row))
    return jsonify({"error": "Product not found"}), 404


@app.route("/<int:product_id>/stock", methods=["PUT"])
def update_product_stock(product_id):
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid data"}), 400
    stock = data.get("stock")
    if stock is None:
        return jsonify({"error": "stock is required"}), 400
    if not isinstance(stock, int) or stock < 0:
        return jsonify({"error": "stock must be a non-negative integer"}), 400

    conn = get_connection()
    try:
        row = fetch_product(conn, product_id)
        if row is None:
            return jsonify({"error": "Product not found"}), 404
        conn.execute(
            "UPDATE products SET stock = ? WHERE id = ?", (stock, product_id)
        )
        conn.commit()
        row = fetch_product(conn, product_id)
    finally:
        conn.close()
    return jsonify(row_to_product(row))


# --- Service discovery (Task 6) --------------------------------------------

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
    print(f"Product Service starting on http://127.0.0.1:{PORT} (db: {DB_PATH})")
    register_with_registry()
    app.run(host="0.0.0.0", port=PORT, debug=True)
