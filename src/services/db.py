import sqlite3
import os
from datetime import datetime, timezone
from src.config import settings

def get_connection():
    # Foreign keys support must be enabled per connection in sqlite
    os.makedirs(os.path.dirname(settings.db_path), exist_ok=True)
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    from src.services.migration import run_migrations
    run_migrations()
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY)
    ''')
    cursor.execute("SELECT MAX(version) FROM schema_versions")
    row = cursor.fetchone()
    if not row or row[0] is None:
        cursor.execute("INSERT INTO schema_versions (version) VALUES (1)")
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS provider_settings (
            provider_name TEXT,
            encrypted_key TEXT,
            is_active BOOLEAN,
            user_id INTEGER REFERENCES users(id),
            status_code TEXT DEFAULT 'untested',
            PRIMARY KEY (provider_name, user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER REFERENCES users(id),
            key TEXT,
            value TEXT,
            PRIMARY KEY (user_id, key)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            provider TEXT,
            model TEXT,
            mode TEXT,
            location TEXT,
            success BOOLEAN,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            total_tokens INTEGER,
            response_time_ms REAL,
            actual_cost REAL,
            estimated_cost REAL,
            currency TEXT DEFAULT 'USD',
            used_fallback BOOLEAN,
            initial_model TEXT,
            final_model TEXT,
            error_type TEXT,
            prevented_tokens INTEGER,
            prevented_cost REAL,
            user_id INTEGER REFERENCES users(id)
        )
    ''')
    
    # Users, Sessions, Conversations, Messages are handled in migration.
    
    conn.commit()
    conn.close()

def save_provider_key(user_id: int, provider_name: str, encrypted_key: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO provider_settings (provider_name, encrypted_key, is_active, user_id, status_code)
        VALUES (?, ?, ?, ?, 'untested')
    ''', (provider_name, encrypted_key, True, user_id))
    conn.commit()
    conn.close()

def get_provider_key(user_id: int, provider_name: str) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT encrypted_key FROM provider_settings WHERE provider_name = ? AND user_id = ?", (provider_name, user_id))
    row = cursor.fetchone()
    conn.close()
    return row['encrypted_key'] if row else None

def delete_provider_key(user_id: int, provider_name: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM provider_settings WHERE provider_name = ? AND user_id = ?", (provider_name, user_id))
    conn.commit()
    conn.close()

def get_all_providers(user_id: int) -> dict:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT provider_name, is_active, status_code FROM provider_settings WHERE user_id = ?", (user_id,))
    
    providers = {}
    for row in cursor.fetchall():
        providers[row['provider_name']] = {
            "has_key": True,
            "is_active": bool(row['is_active']),
            "status_code": row['status_code'] if 'status_code' in row.keys() else 'untested'
        }
    conn.close()
    return providers

def update_provider_status(user_id: int, provider_name: str, status_code: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE provider_settings SET status_code = ? WHERE provider_name = ? AND user_id = ?", (status_code, provider_name, user_id))
    conn.commit()
    conn.close()

def log_usage(user_id: int, log_data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    log_data["user_id"] = user_id
    cursor.execute('''
        INSERT INTO usage_logs (
            provider, model, mode, location, success, 
            prompt_tokens, completion_tokens, total_tokens, 
            response_time_ms, actual_cost, estimated_cost, 
            currency, used_fallback, initial_model, final_model, error_type,
            prevented_tokens, prevented_cost, user_id
        ) VALUES (
            :provider, :model, :mode, :location, :success, 
            :prompt_tokens, :completion_tokens, :total_tokens, 
            :response_time_ms, :actual_cost, :estimated_cost, 
            :currency, :used_fallback, :initial_model, :final_model, :error_type,
            :prevented_tokens, :prevented_cost, :user_id
        )
    ''', log_data)
    conn.commit()
    conn.close()

def get_budget_settings(user_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM user_preferences WHERE key IN ('daily_limit', 'monthly_limit') AND user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    settings = {"daily_limit": None, "monthly_limit": None}
    for row in rows:
        settings[row['key']] = float(row['value']) if row['value'] else None
    return settings

def set_budget_settings(user_id: int, daily: float = None, monthly: float = None):
    conn = get_connection()
    cursor = conn.cursor()
    if daily is not None:
        cursor.execute("INSERT OR REPLACE INTO user_preferences (user_id, key, value) VALUES (?, 'daily_limit', ?)", (user_id, str(daily)))
    if monthly is not None:
        cursor.execute("INSERT OR REPLACE INTO user_preferences (user_id, key, value) VALUES (?, 'monthly_limit', ?)", (user_id, str(monthly)))
    conn.commit()
    conn.close()

def get_current_spend(user_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(COALESCE(actual_cost, 0)) as total FROM usage_logs WHERE date(timestamp) = date('now') AND user_id = ?", (user_id,))
    daily_spend = cursor.fetchone()["total"] or 0.0
    
    cursor.execute("SELECT SUM(COALESCE(actual_cost, 0)) as total FROM usage_logs WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now') AND user_id = ?", (user_id,))
    monthly = cursor.fetchone()['total'] or 0.0
    
    conn.close()
    return {"daily_spend": daily_spend, "monthly_spend": monthly}

def is_first_setup() -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as c FROM users")
    count = cursor.fetchone()['c']
    conn.close()
    return count == 0

def create_user(name: str, email: str, password_hash: str, role: str = 'user') -> int:
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, role)
        )
        user_id = cursor.lastrowid
        
        # If this is the first user (role 'owner'), adopt orphaned data
        if role == 'owner':
            cursor.execute("UPDATE provider_settings SET user_id = ? WHERE user_id IS NULL", (user_id,))
            cursor.execute("UPDATE usage_logs SET user_id = ? WHERE user_id IS NULL", (user_id,))
            cursor.execute("UPDATE user_preferences SET user_id = ? WHERE user_id IS NULL", (user_id,))
            
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError("Bu e-posta adresi zaten kullanılıyor.")
    finally:
        conn.close()

def get_user_consents(user_id: int) -> list:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT permission_type, granted, granted_at, revoked_at FROM user_consents WHERE user_id = ?", (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def grant_consent(user_id: int, permission_type: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
            INSERT INTO user_consents (user_id, permission_type, granted, granted_at, revoked_at)
            VALUES (?, ?, 1, ?, NULL)
            ON CONFLICT(user_id, permission_type) DO UPDATE SET
            granted = 1, granted_at = ?, revoked_at = NULL, version = version + 1
        ''', (user_id, permission_type, now, now))
        conn.commit()
    finally:
        conn.close()

def revoke_consent(user_id: int, permission_type: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute('''
            UPDATE user_consents
            SET granted = 0, revoked_at = ?, version = version + 1
            WHERE user_id = ? AND permission_type = ?
        ''', (now, user_id, permission_type))
        conn.commit()
    finally:
        conn.close()

def get_user_by_email(email: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, role, is_active, email_verified_at, created_at, last_login_at FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_last_login(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def create_session(user_id: int, session_token_hash: str, csrf_token: str, expires_at: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (session_token_hash, csrf_token, user_id, expires_at) VALUES (?, ?, ?, ?)",
        (session_token_hash, csrf_token, user_id, expires_at)
    )
    conn.commit()
    conn.close()

def get_session(session_token_hash: str) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM sessions WHERE session_token_hash = ? AND julianday(expires_at) > julianday('now')",
        (session_token_hash,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_session(session_token_hash: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE session_token_hash = ?", (session_token_hash,))
    conn.commit()
    conn.close()

def clean_expired_sessions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE julianday(expires_at) <= julianday('now')")
    conn.commit()
    conn.close()

def get_conversations(user_id: int) -> list:
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversations WHERE user_id = ? AND is_archived = 0 ORDER BY updated_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def create_conversation(conversation_id: str, user_id: int, title: str, mode: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (id, user_id, title, selected_mode, token_saver_enabled, project_summary) VALUES (?, ?, ?, ?, ?, ?)",
        (conversation_id, user_id, title, mode, False, "")
    )
    conn.commit()
    conn.close()

def update_conversation_token_saver(conversation_id: str, user_id: int, enabled: bool):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE conversations SET token_saver_enabled = ? WHERE id = ? AND user_id = ?",
        (enabled, conversation_id, user_id)
    )
    conn.commit()
    conn.close()

def update_project_summary(conversation_id: str, summary: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE conversations SET project_summary = ? WHERE id = ?",
        (summary, conversation_id)
    )
    conn.commit()
    conn.close()

def get_conversation_info(conversation_id: str, user_id: int) -> dict:
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return row

def get_conversation_messages(conversation_id: str, user_id: int) -> list:
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, project_summary, token_saver_enabled FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
    conv = cursor.fetchone()
    if not conv:
        conn.close()
        return None
        
    cursor.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conversation_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def add_message(message_id: str, conversation_id: str, role: str, content: str, 
                provider_model: str = None, token_info: str = None, 
                response_time_ms: float = None, fallback_info: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO messages (id, conversation_id, role, content, provider_model, 
                              token_info, response_time_ms, fallback_info)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (message_id, conversation_id, role, content, provider_model, token_info, response_time_ms, fallback_info))
    
    cursor.execute("UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (conversation_id,))
    
    conn.commit()
    conn.close()

def delete_conversation(conversation_id: str, user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (conversation_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def save_email_verification_token(token_hash: str, user_id: int, expires_at: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO email_verification_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)", 
                   (token_hash, user_id, expires_at))
    conn.commit()
    conn.close()

def invalidate_verification_tokens(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM email_verification_tokens WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user_by_verification_token(token_hash: str) -> dict:
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.* FROM users u 
        JOIN email_verification_tokens t ON u.id = t.user_id 
        WHERE t.token_hash = ? AND julianday(t.expires_at) > julianday('now')
    ''', (token_hash,))
    row = cursor.fetchone()
    conn.close()
    return row

def verify_user_email(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET email_verified_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
    cursor.execute("DELETE FROM email_verification_tokens WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def save_password_reset_token(token_hash: str, user_id: int, expires_at: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO password_reset_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)", 
                   (token_hash, user_id, expires_at))
    conn.commit()
    conn.close()

def get_user_by_password_reset_token(token_hash: str) -> dict:
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.* FROM users u 
        JOIN password_reset_tokens t ON u.id = t.user_id 
        WHERE t.token_hash = ? AND julianday(t.expires_at) > julianday('now')
    ''', (token_hash,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_user_password(user_id: int, new_password_hash: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password_hash, user_id))
    cursor.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user_id,))
    # Invalidate all sessions for this user
    cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def create_project(project_id: str, user_id: int, name: str, description: str = ""):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO projects (id, user_id, name, description) VALUES (?, ?, ?, ?)",
        (project_id, user_id, name, description)
    )
    conn.commit()
    conn.close()

def get_projects(user_id: int) -> list:
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_project(project_id: str, user_id: int) -> dict:
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return row

def update_project(project_id: str, user_id: int, name: str, description: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE projects SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
        (name, description, project_id, user_id)
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def delete_project(project_id: str, user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM projects WHERE id = ? AND user_id = ?", (project_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def add_file(file_id: str, user_id: int, project_id: str, filename: str, file_type: str, size: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO files (id, user_id, project_id, filename, file_type, size) VALUES (?, ?, ?, ?, ?, ?)",
        (file_id, user_id, project_id, filename, file_type, size)
    )
    conn.commit()
    conn.close()

def get_files(user_id: int, project_id: str = None) -> list:
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    if project_id:
        cursor.execute("SELECT * FROM files WHERE user_id = ? AND project_id = ? ORDER BY created_at DESC", (user_id, project_id))
    else:
        cursor.execute("SELECT * FROM files WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_file(file_id: str, user_id: int) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    # FTS is a contentless virtual table and is not covered by the foreign-key
    # cascade, so remove its rows before deleting the source chunks.
    cursor.execute("DELETE FROM document_chunks_fts WHERE chunk_id IN (SELECT id FROM document_chunks WHERE file_id = ? AND user_id = ?)", (file_id, user_id))
    cursor.execute("DELETE FROM files WHERE id = ? AND user_id = ?", (file_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def add_document_chunk(chunk_id: str, user_id: int, project_id: str, file_id: str,
                       page_number: int, chunk_index: int, content: str,
                       embedding_json: str = None, embedding_model: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO document_chunks
           (id, user_id, project_id, file_id, page_number, chunk_index, content,
            embedding_json, embedding_model)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (chunk_id, user_id, project_id, file_id, page_number, chunk_index,
         content, embedding_json, embedding_model)
    )
    cursor.execute(
        "INSERT INTO document_chunks_fts (chunk_id, content) VALUES (?, ?)",
        (chunk_id, content)
    )
    conn.commit()
    conn.close()

def message_exists(message_id: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute("SELECT 1 FROM messages WHERE id = ?", (message_id,)).fetchone()
        return row is not None
    finally:
        conn.close()

def search_chunks(user_id: int, project_id: str, query: str, limit: int = 5) -> list:
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    # We join with document_chunks to ensure it belongs to user_id and project_id
    sql = """
        SELECT c.*, f.filename 
        FROM document_chunks_fts fts
        JOIN document_chunks c ON fts.chunk_id = c.id
        JOIN files f ON c.file_id = f.id
        WHERE document_chunks_fts MATCH ?
          AND c.user_id = ? 
          AND c.project_id = ?
        ORDER BY bm25(document_chunks_fts)
        LIMIT ?
    """
    try:
        cursor.execute(sql, (query, user_id, project_id, limit))
        rows = cursor.fetchall()
    except Exception as e:
        # Fallback if match syntax error or empty
        print("Search error:", e)
        rows = []
    conn.close()
    return rows
