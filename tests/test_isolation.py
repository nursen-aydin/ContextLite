import pytest
import os
import hashlib
import sqlite3
from src.config import settings
from src.services.db import get_connection

def get_file_sha256(filepath):
    if not os.path.exists(filepath):
        return None
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def test_database_isolation():
    canonical_db = os.path.abspath("data/contextlite.db")
    
    assert "tmp" in settings.db_path or "var/folders" in settings.db_path or "pytest" in settings.db_path
    assert os.path.abspath(settings.db_path) != canonical_db
    
    if os.path.exists(canonical_db):
        prod_conn = sqlite3.connect(f"file:{canonical_db}?mode=ro", uri=True)
        prod_conn.close()
        
    from src.services.migration import run_migrations
    run_migrations()  # Run it a second time on the temp db
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM schema_versions")
    assert cursor.fetchone()[0] == 8
    cursor.execute("SELECT MAX(version) FROM schema_versions")
    assert cursor.fetchone()[0] == 8
    conn.close()

def test_production_db_is_protected_from_import():
    import sys
    import importlib
    import os
    import pytest
    
    original_db_path = os.environ.get("DB_PATH")
    
    # Simulate someone starting a test without DB_PATH (so it defaults to data/contextlite.db)
    if "DB_PATH" in os.environ:
        del os.environ["DB_PATH"]
    
    import src.config
    
    with pytest.raises(RuntimeError) as exc_info:
        importlib.reload(src.config)
        
    assert "Test/Debug ortamında üretim veritabanı kullanılamaz" in str(exc_info.value)
    
    if original_db_path:
        os.environ["DB_PATH"] = original_db_path
    importlib.reload(src.config)
