import pytest
from fastapi.testclient import TestClient

from app.db import connect, init_db
from app.main import create_app


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.sqlite"
    conn = connect(str(path))
    try:
        init_db(conn)
    finally:
        conn.close()
    return path


@pytest.fixture
def conn(db_path):
    connection = connect(str(db_path))
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def client(db_path):
    with TestClient(create_app(str(db_path))) as test_client:
        yield test_client
