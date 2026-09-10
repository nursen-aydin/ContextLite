import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "ContextLite"
    encryption_key: str = ""
    db_path: str = "data/contextlite.db"
    foundry_chat_model: str = ""
    foundry_embedding_model: str = ""
    foundry_data_dir: str = "data/foundry"
    
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    mail_provider: str = ""
    mail_from: str = "noreply@contextlite.com"
    mail_from_name: str = "ContextLite"
    app_base_url: str = "http://127.0.0.1:8124"

    class Config:
        env_file = ".env"

settings = Settings()

# A local-first application should start on a clean machine without requiring
# the user to understand secret management first.  Explicit ENCRYPTION_KEY
# still wins; otherwise a private, git-ignored key is generated once.
if not settings.encryption_key:
    from cryptography.fernet import Fernet

    key_path = os.path.join("data", ".encryption_key")
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    if os.path.exists(key_path):
        with open(key_path, "r", encoding="utf-8") as key_file:
            settings.encryption_key = key_file.read().strip()
    else:
        settings.encryption_key = Fernet.generate_key().decode()
        with open(key_path, "x", encoding="utf-8") as key_file:
            key_file.write(settings.encryption_key)

# GÜVENLİK KONTROLÜ: Test/Debug ortamında üretim veritabanına bağlanılamaz.
# Import sırasında (TestClient dahil) bu kontrol tetiklenir ve uygulamayı başlatmadan durdurur.
import sys
is_test = "pytest" in sys.modules or "fastapi.testclient" in sys.modules
if is_test:
    import os
    abs_db_path = os.path.abspath(settings.db_path)
    abs_prod1 = os.path.abspath("data/contextlite.db")
    abs_prod2 = os.path.abspath("context_lite.db")
    if abs_db_path in [abs_prod1, abs_prod2]:
        raise RuntimeError("KRİTİK GÜVENLİK HATASI: Test/Debug ortamında üretim veritabanı kullanılamaz! 'DB_PATH' çevre değişkeni ile geçici bir yol verin.")
