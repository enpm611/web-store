# Microservices solution notes

This documents the implementation of the six tasks in the web-store exercise.
It supplements the assignment `README.md` (which stays unchanged).

## What was implemented

| Task | Deliverable | File |
| ---- | ----------- | ---- |
| 1 (required) | User Service, port 5031 | `user_service.py` |
| 2 (required) | Product Service, port 5032 | `product_service.py` |
| 3 (required) | Order Service completed (TODOs filled) | `order_service.py` |
| 4 (required) | System test through the gateway | verified; see below |
| 5 (advanced) | SQLite database per service | built into all three services |
| 6 (advanced) | Service registry / discovery | `service_registry.py` + order service |

The `api_gateway.py` routes `/{service}/{path}` to each service and strips the
prefix, so every service uses root-relative routes (e.g. the gateway sends
`/users/1` to the user service as `/1`). Ports: gateway 5030, users 5031,
products 5032, orders 5033, registry 5100.

## Endpoints

- **User** (5031): `GET /health`, `GET /`, `GET /<id>`, `POST /`
- **Product** (5032): `GET /health`, `GET /`, `GET /<id>`, `PUT /<id>/stock`
- **Order** (5033): `GET /health`, `POST /` (also `PUT /`), `GET /<id>`
- **Registry** (5100): `GET /health`, `POST /register`, `GET /discover/<name>`,
  `GET /services`, `POST /deregister`

## Task 5 — database per service

Each service persists its data in its own SQLite file (`users.db`,
`products.db`, `orders.db`), seeded once from the original in-memory data and
retained across restarts. The path is configurable per service with
`USER_DB_PATH`, `PRODUCT_DB_PATH`, `ORDER_DB_PATH` (the tests use throwaway
databases). The `*.db` files are git-ignored.

## Task 6 — service discovery

The order service resolves the user and product URLs at call time, in order of
precedence: explicit `USERS_SERVICE_URL` / `PRODUCTS_SERVICE_URL` env vars, then
the registry at `SERVICE_REGISTRY_URL` (`GET /discover/<name>`), then built-in
defaults. Services register themselves on startup when `SERVICE_REGISTRY_URL` is
set. This keeps Tasks 1-4 working without a registry while fully supporting one.

## Running the microservices

```bash
python -m venv env
source env/bin/activate          # env/Scripts/activate on Windows
pip install -r requirements.txt

# each in its own terminal, from the microservices/ directory
python user_service.py
python product_service.py
python order_service.py
python api_gateway.py            # hosts the UI at http://127.0.0.1:5030
```

To run with service discovery, start `python service_registry.py` first and set
`SERVICE_REGISTRY_URL=http://127.0.0.1:5100` in each service's environment.

## Testing

Automated component + integration tests (order-service inter-service calls are
mocked for determinism):

```bash
pip install -r requirements-dev.txt
cd microservices
python -m pytest tests/ -v
```

30 tests pass. The full flow was also verified live through the gateway: order
creation decrements stock, orders are retrievable, and bad user / bad product /
insufficient stock return 404 / 404 / 400. Service discovery was verified by
running the product service on a non-default port and letting the order service
find it through the registry. Persistence was verified by changing stock,
restarting the service, and confirming the value survived.
