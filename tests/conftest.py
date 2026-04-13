import shutil

import pytest
from flask import Flask
from sqlalchemy import text
from testing.postgresql import Postgresql

from matcher import database
from matcher.model import Base, Item  # noqa: F401
from matcher.place import Place  # noqa: F401


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests requiring a real osm2pgsql binary on PATH",
    )


@pytest.fixture(scope="session")
def postgresql(request):
    psql = Postgresql()
    yield psql
    psql.stop()


@pytest.fixture(scope="session")
def app(request, postgresql):
    app = Flask("test_app")

    class TestConfig:
        DB_URL = postgresql.url()
        DB_PASS = ""
        TESTING = True
        DEBUG = True
        ADMIN_EMAIL = "tests@osm.wikidata.link"
        SERVER_NAME = "test"
        SECRET_KEY = "secret"
        SOCIAL_AUTH_USER_MODEL = "matcher.model.User"
        DATA_DIR = "data"

    app.config.from_object(TestConfig)
    database.init_app(app)

    ctx = app.app_context()
    ctx.push()

    engine = database.session.get_bind()
    with engine.begin() as conn:
        conn.execute(text("create extension if not exists postgis"))
        conn.execute(text("create extension if not exists hstore"))
    Base.metadata.create_all(engine)

    yield app

    ctx.pop()


@pytest.fixture(scope="session")
def osm2pgsql_available():
    """True if osm2pgsql is on PATH. Integration tests skip when False."""
    return shutil.which("osm2pgsql") is not None
