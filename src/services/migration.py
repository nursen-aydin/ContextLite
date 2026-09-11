import sqlite3
import shutil
import os
from datetime import datetime
from src.config import settings

def run_migrations():
    db_path = settings.db_path
    db_exists = os.path.exists(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY)")
    cursor.execute("SELECT MAX(version) FROM schema_versions")
    row = cursor.fetchone()
    current_version = row[0] if row and row[0] is not None else 0

    if current_version < 1:
        print("Starting migration to version 1...")
        if db_exists:
            backup_path = f"{db_path}.v0_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(db_path, backup_path)
            print(f"Backup created at {backup_path}")
        else:
            print("Fresh database, no backup needed.")

        try:
            conn.execute("BEGIN TRANSACTION")

            cursor.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login_at DATETIME
                )
            ''')

            cursor.execute('''
                CREATE TABLE sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_token_hash TEXT UNIQUE NOT NULL,
                    csrf_token TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    expires_at DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')

            cursor.execute('''
                CREATE TABLE conversations (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_archived BOOLEAN NOT NULL DEFAULT 0,
                    last_provider_model TEXT,
                    selected_mode TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')

            cursor.execute('''
                CREATE TABLE messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    provider_model TEXT,
                    token_info TEXT,
                    response_time_ms REAL,
                    fallback_info TEXT,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
                )
            ''')

            try:
                cursor.execute("ALTER TABLE provider_settings ADD COLUMN user_id INTEGER REFERENCES users(id)")
            except sqlite3.OperationalError:
                pass # Column might exist if manually added

            try:
                cursor.execute("ALTER TABLE usage_logs ADD COLUMN user_id INTEGER REFERENCES users(id)")
            except sqlite3.OperationalError:
                pass

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'")
            if cursor.fetchone():
                cursor.execute("CREATE TABLE user_preferences_new (user_id INTEGER, key TEXT, value TEXT, PRIMARY KEY (user_id, key))")
                cursor.execute("INSERT INTO user_preferences_new (user_id, key, value) SELECT NULL, key, value FROM user_preferences")
                cursor.execute("DROP TABLE user_preferences")
                cursor.execute("ALTER TABLE user_preferences_new RENAME TO user_preferences")
            else:
                cursor.execute("CREATE TABLE user_preferences (user_id INTEGER, key TEXT, value TEXT, PRIMARY KEY (user_id, key))")

            cursor.execute("INSERT INTO schema_versions (version) VALUES (1)")
            
            conn.commit()
            print("Migration to version 1 successful.")
        except Exception as e:
            conn.rollback()
            print(f"Migration failed: {e}. Rolled back.")
            raise
    
    if current_version < 2:
        print("Starting migration to version 2...")
        try:
            conn.execute("BEGIN TRANSACTION")
            
            try:
                cursor.execute("ALTER TABLE conversations ADD COLUMN project_summary TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE conversations ADD COLUMN token_saver_enabled BOOLEAN DEFAULT 0")
            except sqlite3.OperationalError:
                pass
                
            try:
                cursor.execute("ALTER TABLE usage_logs ADD COLUMN prevented_tokens INTEGER")
            except sqlite3.OperationalError:
                pass
                
            try:
                cursor.execute("ALTER TABLE usage_logs ADD COLUMN prevented_cost REAL")
            except sqlite3.OperationalError:
                pass

            cursor.execute("INSERT INTO schema_versions (version) VALUES (2)")
            
            conn.commit()
            print("Migration to version 2 successful.")
        except Exception as e:
            conn.rollback()
            print(f"Migration to version 2 failed: {e}. Rolled back.")
            raise
    
    if current_version < 3:
        print("Starting migration to version 3...")
        try:
            conn.execute("BEGIN TRANSACTION")
            
            cursor.execute('''
                CREATE TABLE projects (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')
            
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN email_verified_at DATETIME")
            except sqlite3.OperationalError:
                pass
                
            cursor.execute('''
                CREATE TABLE email_verification_tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    expires_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE password_reset_tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    expires_at DATETIME NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')
            
            try:
                cursor.execute("ALTER TABLE conversations ADD COLUMN project_id TEXT REFERENCES projects(id) ON DELETE CASCADE")
            except sqlite3.OperationalError:
                pass
                
            cursor.execute("INSERT INTO schema_versions (version) VALUES (3)")
            
            conn.commit()
            print("Migration to version 3 successful.")
        except Exception as e:
            conn.rollback()
            print(f"Migration to version 3 failed: {e}. Rolled back.")
            raise
            
    if current_version < 4:
        print("Starting migration to version 4...")
        try:
            conn.execute("BEGIN TRANSACTION")
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_consents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    permission_type TEXT NOT NULL,
                    granted BOOLEAN NOT NULL DEFAULT 0,
                    granted_at DATETIME,
                    revoked_at DATETIME,
                    version INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    UNIQUE(user_id, permission_type)
                )
            ''')
            
            cursor.execute("INSERT INTO schema_versions (version) VALUES (4)")
            
            conn.commit()
            print("Migration to version 4 successful.")
        except Exception as e:
            conn.rollback()
            print(f"Migration to version 4 failed: {e}. Rolled back.")
            raise
    if current_version < 5:
        print("Starting migration to version 5...")
        try:
            conn.execute("BEGIN TRANSACTION")
            
            try:
                cursor.execute("ALTER TABLE provider_settings ADD COLUMN encrypted_key TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                # Attempt to migrate old api_key data if it exists
                from src.services.crypto import encrypt_key
                cursor.execute("SELECT provider_name, user_id, api_key FROM provider_settings WHERE api_key IS NOT NULL AND api_key != ''")
                rows = cursor.fetchall()
                for row in rows:
                    if row['api_key']:
                        enc = encrypt_key(row['api_key'])
                        cursor.execute("UPDATE provider_settings SET encrypted_key = ?, api_key = NULL WHERE provider_name = ? AND user_id = ?", (enc, row['provider_name'], row['user_id']))
            except sqlite3.OperationalError:
                pass # api_key column might not exist depending on table history
                
            cursor.execute("INSERT INTO schema_versions (version) VALUES (5)")
            
            conn.commit()
            print("Migration to version 5 successful.")
        except Exception as e:
            conn.rollback()
            print(f"Migration to version 5 failed: {e}. Rolled back.")
            raise
    
    
    if current_version < 6:
        print("Starting migration to version 6...")
        try:
            conn.execute("BEGIN TRANSACTION")
            
            try:
                cursor.execute("ALTER TABLE provider_settings ADD COLUMN status_code TEXT DEFAULT 'untested'")
            except sqlite3.OperationalError:
                pass
                
            cursor.execute("INSERT INTO schema_versions (version) VALUES (6)")
            
            conn.commit()
            print("Migration to version 6 successful.")
        except Exception as e:
            conn.rollback()
            print(f"Migration to version 6 failed: {e}. Rolled back.")
            raise
    
    if current_version < 7:
        print("Starting migration to version 7...")
        try:
            conn.execute("BEGIN TRANSACTION")
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    project_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    project_id TEXT NOT NULL,
                    file_id TEXT NOT NULL,
                    page_number INTEGER,
                    chunk_index INTEGER,
                    content TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
                    FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
                    content,
                    chunk_id UNINDEXED
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS prompt_optimizations (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    project_id TEXT,
                    original_prompt TEXT NOT NULL,
                    optimized_prompt TEXT NOT NULL,
                    model TEXT NOT NULL,
                    original_tokens INTEGER,
                    optimized_tokens INTEGER,
                    saved_tokens INTEGER,
                    saved_percent REAL,
                    is_approximate BOOLEAN,
                    success BOOLEAN,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            ''')
            
            cursor.execute("INSERT INTO schema_versions (version) VALUES (7)")
            
            conn.commit()
            print("Migration to version 7 successful.")
        except Exception as e:
            conn.rollback()
            print(f"Migration to version 7 failed: {e}. Rolled back.")
            raise

    if current_version < 8:
        print("Starting migration to version 8...")
        try:
            conn.execute("BEGIN TRANSACTION")
            try:
                cursor.execute("ALTER TABLE document_chunks ADD COLUMN embedding_json TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                cursor.execute("ALTER TABLE document_chunks ADD COLUMN embedding_model TEXT")
            except sqlite3.OperationalError:
                pass
            cursor.execute("INSERT OR IGNORE INTO schema_versions (version) VALUES (8)")
            conn.commit()
            print("Migration to version 8 successful.")
        except Exception as e:
            conn.rollback()
            print(f"Migration to version 8 failed: {e}. Rolled back.")
            raise
    
    conn.close()

if __name__ == "__main__":
    run_migrations()
