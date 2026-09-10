from cryptography.fernet import Fernet
from src.config import settings

fernet = Fernet(settings.encryption_key.encode())

def encrypt_key(api_key: str) -> str:
    if not api_key:
        return ""
    return fernet.encrypt(api_key.encode()).decode()

def decrypt_key(encrypted_key: str) -> str:
    if not encrypted_key:
        return ""
    try:
        return fernet.decrypt(encrypted_key.encode()).decode()
    except Exception:
        return ""
