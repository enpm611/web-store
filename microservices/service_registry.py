# service_registry.py
#
# Task 6: Service discovery.
#
# A tiny registry where services register their URL on startup and consumers
# look them up by name instead of hard-coding host/port. Runs on port 5100.
#
#   POST /register            body {"name": ..., "url": ...}  -> record a service
#   GET  /discover/<name>                                     -> {"url": ...} or 404
#   GET  /services                                            -> all registered
#   POST /deregister          body {"name": ...}              -> remove a service
#   GET  /health                                              -> health check
#
# Services register with this registry when SERVICE_REGISTRY_URL is set to
# http://127.0.0.1:5100, and the order service resolves the user/product URLs
# through GET /discover/<name>.

import os

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get("SERVICE_REGISTRY_PORT", "5100"))

# {service_name: url}
services = {}


@app.route("/health", methods=["GET"])
def get_health():
    return jsonify({"status": "All good"}), 200


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid data"}), 400
    service_name = data.get("name")
    service_url = data.get("url")
    if not service_name or not service_url:
        return jsonify({"error": "name and url are required"}), 400
    services[service_name] = service_url
    print(f"Registered '{service_name}' -> {service_url}")
    return jsonify({"status": "registered", "name": service_name, "url": service_url})


@app.route("/discover/<service_name>", methods=["GET"])
def discover(service_name):
    url = services.get(service_name)
    if url:
        return jsonify({"url": url})
    return jsonify({"error": "Service not found"}), 404


@app.route("/services", methods=["GET"])
def list_services():
    return jsonify(services)


@app.route("/deregister", methods=["POST"])
def deregister():
    data = request.get_json(silent=True) or {}
    service_name = data.get("name")
    if service_name in services:
        removed = services.pop(service_name)
        return jsonify({"status": "deregistered", "name": service_name, "url": removed})
    return jsonify({"error": "Service not found"}), 404


if __name__ == "__main__":
    print(f"Service Registry starting on http://127.0.0.1:{PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=True)
