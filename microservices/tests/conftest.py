"""Shared pytest fixtures for the microservices.

Each service is pointed at a throwaway SQLite database (so the tests never
touch the real *.db files), and the order service's downstream URLs are pinned
so no registry or live service is required. Databases are reset to their seed
state before every test for isolation.
"""

import os
import sys
import tempfile

import pytest

# Make the service modules (one directory up) importable.
MICROSERVICES_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MICROSERVICES_DIR not in sys.path:
    sys.path.insert(0, MICROSERVICES_DIR)

# Point every service at a temporary database BEFORE the modules are imported.
_TMP = tempfile.mkdtemp(prefix="webstore_tests_")
os.environ["USER_DB_PATH"] = os.path.join(_TMP, "users.db")
os.environ["PRODUCT_DB_PATH"] = os.path.join(_TMP, "products.db")
os.environ["ORDER_DB_PATH"] = os.path.join(_TMP, "orders.db")

# Pin the order service's downstream URLs so resolution needs no registry.
os.environ["USERS_SERVICE_URL"] = "http://users.test"
os.environ["PRODUCTS_SERVICE_URL"] = "http://products.test"
os.environ.pop("SERVICE_REGISTRY_URL", None)


def _reset(module, table):
    conn = module.get_connection()
    try:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()
    finally:
        conn.close()
    module.init_db()


@pytest.fixture
def user_client():
    import user_service
    _reset(user_service, "users")
    return user_service.app.test_client()


@pytest.fixture
def product_client():
    import product_service
    _reset(product_service, "products")
    return product_service.app.test_client()


@pytest.fixture
def order_module():
    import order_service
    _reset(order_service, "orders")
    return order_service


@pytest.fixture
def order_client(order_module):
    return order_module.app.test_client()


@pytest.fixture
def registry_client():
    import service_registry
    service_registry.services.clear()
    return service_registry.app.test_client()
