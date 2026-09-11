import os
import pytest
import tempfile
import sqlite3

# This must happen before any src.main or config imports in test files
# to prevent the production database from ever being loaded!
import tempfile
# Initialize with a dummy path to pass config initialization
dummy_fd, dummy_path = tempfile.mkstemp(suffix=".db", prefix="contextlite_dummy_")
os.environ["DB_PATH"] = dummy_path
print(f"\\n[TEST ENVIRONMENT] DB_PATH initially set to dummy: {dummy_path}")

from src.main import app
from fastapi.testclient import TestClient
from src.services.db import init_db
from src.config import settings

@pytest.fixture(scope="function", autouse=True)
def setup_teardown_db(tmp_path):
    new_db_path = str(tmp_path / "test.db")
    settings.db_path = new_db_path
    
    init_db()
    
    yield

def pytest_sessionfinish(session, exitstatus):
    os.close(dummy_fd)
    if os.path.exists(dummy_path):
        os.remove(dummy_path)
