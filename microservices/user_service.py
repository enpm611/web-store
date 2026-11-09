# user_service.py
#
# Task 1 (and Task 5: database per service).
#
# The User Service owns the user data that used to live in the monolith.
# It runs as its own Flask application on port 5031. The api_gateway forwards
# "/users/<path>" to this service as "/<path>", so the routes here are
# root-relative: GET /<id>, GET /, POST /, GET /health.
#
# Data is persisted in a SQLite database (Task 5) so it survives restarts.
# The database path is configurable with the USER_DB_PATH environment variable
# (used by the tests to point at a temporary database).
#
# Task 6 (service discovery): on startup the service registers itself with the
# service registry if SERVICE_REGISTRY_URL is set. Registration is best-effort
# and never prevents the service from starting.

import os
import sqlite3

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SERVICE_NAME = "users"
PORT = int(os.environ.get("USER_SERVICE_PORT", "5031"))

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("USER_DB_PATH", os.path.join(HERE, "users.db"))

# Seed data migrated from the monolith's in-memory store.
SEED_USERS = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"},
]


# --- Database helpers -------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the users table and seed it once if it is empty."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id    INTEGER PRIMARY KEY,
                name  TEXT NOT NULL,
                email TEXT NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO users (id, name, email) VALUES (:id, :name, :email)",
                SEED_USERS,
            )
        conn.commit()
    finally:
        conn.close()


def row_to_user(row):
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


# --- Endpoints --------------------------------------------------------------

@app.route("/health", methods=["GET"])
def get_health():
    return jsonify({"status": "All good"}), 200


@app.route("/", methods=["GET"])
def get_users():
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, name, email FROM users ORDER BY id").fetchall()
        return jsonify([row_to_user(r) for r in rows])
    finally:
        conn.close()


@app.route("/<int:user_id>", methods=["GET"])
def get_user(user_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if row:
        return jsonify(row_to_user(row))
    return jsonify({"error": "User not found"}), 404


@app.route("/", methods=["POST"])
def create_user():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid data"}), 400
    name = data.get("name")
    email = data.get("email")
    if not name or not email:
        return jsonify({"error": "name and email are required"}), 400
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email) VALUES (?, ?)", (name, email)
        )
        conn.commit()
        new_id = cursor.lastrowid
        row = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (new_id,)
        ).fetchone()
    finally:
        conn.close()
    return jsonify(row_to_user(row)), 201


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


# Initialize the database as soon as the module is imported so the app is
# usable both when run directly and when imported by the tests.
init_db()


if __name__ == "__main__":
    print(f"User Service starting on http://127.0.0.1:{PORT} (db: {DB_PATH})")
    register_with_registry()
    app.run(host="0.0.0.0", port=PORT, debug=True)
