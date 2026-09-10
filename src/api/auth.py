from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from pwdlib import PasswordHash
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
import re

from src.services.db import (
    is_first_setup, create_user, get_user_by_email, get_user_by_id, 
    update_last_login, create_session, get_session, delete_session,
    save_email_verification_token, get_user_by_verification_token, verify_user_email,
    save_password_reset_token, get_user_by_password_reset_token, update_user_password,
    invalidate_verification_tokens
)
from src.config import settings
from src.services.email import (
    is_smtp_configured,
    send_password_reset_email,
    send_verification_email,
)

# Configuration for Argon2
password_hash = PasswordHash.recommended()

router = APIRouter()

# Dependency to get current user from session cookie
def get_current_user(request: Request):
    session_token = request.cookies.get("session_id")
    if not session_token:
        raise HTTPException(status_code=401, detail="Yetkilendirme başarısız. Lütfen giriş yapın.")
        
    token_hash = hashlib.sha256(session_token.encode()).hexdigest()
    session_data = get_session(token_hash)
    
    if not session_data:
        raise HTTPException(status_code=401, detail="Oturum süresi dolmuş veya geçersiz.")
        
    user = get_user_by_id(session_data["user_id"])
    if not user or not user["is_active"]:
        raise HTTPException(status_code=403, detail="Kullanıcı hesabı pasif veya silinmiş.")
        
    # CSRF Protection for state-changing methods
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_header or csrf_header != session_data["csrf_token"]:
            raise HTTPException(status_code=403, detail="CSRF doğrulaması başarısız.")
            
    return user



def validate_password(password: str):
    if len(password) < 8 or len(password) > 64:
        raise ValueError("Parola 8 ile 64 karakter arasında olmalıdır.")
        
    blocklist = {
        "12345678", "123456789", "password", "password123", "qwertyui", 
        "12345678a", "admin123", "11111111", "00000000", "87654321",
        "123123123", "qazwsxedc", "contextlite"
    }
    if password.lower() in blocklist:
        raise ValueError("Bu parola çok yaygın veya kolay tahmin edilebilir. Lütfen daha güvenli bir parola seçin.")


def _store_verification_secret(user_id: int, raw_secret: str, lifetime: timedelta) -> None:
    """Store one expiring verification secret, never the raw value."""
    invalidate_verification_tokens(user_id)
    token_hash = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()
    expires = datetime.now(timezone.utc) + lifetime
    save_email_verification_token(token_hash, user_id, expires.isoformat())


def _send_new_verification_email(user_id: int, email: str) -> bool:
    """Create a link token and remove it if SMTP delivery fails."""
    raw_token = secrets.token_urlsafe(32)
    _store_verification_secret(user_id, raw_token, timedelta(hours=24))
    if send_verification_email(email, raw_token):
        return True
    invalidate_verification_tokens(user_id)
    return False

class SetupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

@router.post("/setup")
async def setup_first_user(req: SetupRequest):
    if not is_first_setup():
        raise HTTPException(status_code=403, detail="Kurulum zaten yapılmış. Yeni hesap oluşturulamaz.")
        
    try:
        validate_password(req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    email = req.email.strip().lower()
    hashed_pw = password_hash.hash(req.password)
    
    try:
        user_id = create_user(req.name, email, hashed_pw, role="owner")
        # Owner bypasses email verification initially for setup
        from src.services.db import verify_user_email
        verify_user_email(user_id)
        return {"status": "success", "message": "İlk yönetici hesabı başarıyla oluşturuldu.", "user_id": user_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

@router.post("/signup")
async def signup_user(req: SignupRequest, request: Request, response: Response):
    try:
        validate_password(req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    email = req.email.strip().lower()
    hashed_pw = password_hash.hash(req.password)
    
    try:
        user_id = create_user(req.name, email, hashed_pw, role="user")
        
        # Create session automatically on signup
        session_token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        session_token_hash = hashlib.sha256(session_token.encode()).hexdigest()
        session_expires = datetime.now(timezone.utc) + timedelta(hours=12)
        create_session(user_id, session_token_hash, csrf_token, session_expires.isoformat())
        
        is_secure = request.url.scheme == "https"
        response.set_cookie(
            key="session_id",
            value=session_token,
            httponly=True,
            samesite="lax",
            secure=is_secure,
            path="/",
            max_age=None
        )
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            samesite="lax",
            secure=is_secure,
            path="/",
            max_age=None
        )
        
        email_sent = False
        if is_smtp_configured():
            email_sent = _send_new_verification_email(user_id, email)

        return {
            "status": "success",
            "message": "Kayıt başarılı. E-posta doğrulama adımına yönlendiriliyorsunuz.",
            "user_id": user_id,
            "email": email,
            "verification_required": True,
            "verification_delivery": "email" if is_smtp_configured() else "local",
            "email_sent": email_sent,
        }
    except ValueError as e:
        if "zaten kullanılıyor" in str(e):
            raise HTTPException(status_code=400, detail="Bu e-posta adresi zaten kullanılıyor.")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Bellekte tutulan basit hız sınırlama sözlüğü (Yeniden başlatmada sıfırlanır)
login_attempts = {}

class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False

@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    email = req.email.strip().lower()
    rate_key = f"{client_ip}_{email}"
    now = datetime.now()
    
    # Check rate limit
    attempt_info = login_attempts.get(rate_key, {"count": 0, "locked_until": None})
    if attempt_info["locked_until"]:
        if now < attempt_info["locked_until"]:
            remaining = int((attempt_info["locked_until"] - now).total_seconds())
            raise HTTPException(status_code=429, detail=f"Çok fazla hatalı deneme. Lütfen {remaining} saniye sonra tekrar deneyin.")
        else:
            # Lock expired, reset
            attempt_info = {"count": 0, "locked_until": None}
        
    user = get_user_by_email(email)
    
    # Avoid timing attacks
    if not user or not password_hash.verify(req.password, user["password_hash"]):
        # Increment attempt
        attempt_info["count"] += 1
        if attempt_info["count"] >= 5:
            attempt_info["locked_until"] = now + timedelta(minutes=5)
        login_attempts[rate_key] = attempt_info
        
        raise HTTPException(status_code=401, detail="E-posta veya parola hatalı.")
        
    # Reset attempts on success
    if rate_key in login_attempts:
        del login_attempts[rate_key]
        
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Bu hesap devre dışı bırakılmış.")
        
    update_last_login(user["id"])
    
    # Create secure session
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(session_token.encode()).hexdigest()
    
    if req.remember_me:
        max_age = 30 * 24 * 60 * 60
        expires = datetime.now(timezone.utc) + timedelta(days=30)
    else:
        max_age = None
        expires = datetime.now(timezone.utc) + timedelta(hours=12)
        
    create_session(user["id"], token_hash, csrf_token, expires.isoformat())
    
    is_secure = request.url.scheme == "https"
    
    # Set HttpOnly Cookie for session
    response.set_cookie(
        key="session_id",
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=is_secure,
        max_age=max_age,
        path="/"
    )
    
    # Set non-HttpOnly Cookie for CSRF
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=is_secure,
        max_age=max_age,
        path="/"
    )
    
    return {"status": "success", "message": "Giriş başarılı."}

@router.post("/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_id")
    if session_token:
        token_hash = hashlib.sha256(session_token.encode()).hexdigest()
        delete_session(token_hash)
        
    response.delete_cookie(key="session_id", path="/")
    response.delete_cookie(key="csrf_token", path="/")
    return {"status": "success", "message": "Çıkış yapıldı."}

@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "email_verified_at": user.get("email_verified_at")
    }

class VerifyEmailRequest(BaseModel):
    token: str

@router.post("/verify-email")
async def verify_email_api(req: VerifyEmailRequest):
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    user = get_user_by_verification_token(token_hash)
    if not user:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş doğrulama bağlantısı.")
        
    verify_user_email(user["id"])
    return {"status": "success", "message": "E-posta başarıyla doğrulandı. Giriş yapabilirsiniz."}


class VerifyCodeRequest(BaseModel):
    code: str


@router.post("/verify-code")
async def verify_code(req: VerifyCodeRequest, user: dict = Depends(get_current_user)):
    """Verify a short-lived code that is visible only to its signed-in local user."""
    code = re.sub(r"\s+", "", req.code)
    if not re.fullmatch(r"\d{6}", code):
        raise HTTPException(status_code=400, detail="Doğrulama kodu 6 rakamdan oluşmalıdır.")

    code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    token_user = get_user_by_verification_token(code_hash)
    if not token_user or token_user["id"] != user["id"]:
        raise HTTPException(status_code=400, detail="Doğrulama kodu hatalı veya süresi dolmuş.")

    verify_user_email(user["id"])
    return {"status": "success", "message": "E-posta doğrulama durumu başarıyla kaydedildi."}

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    email = req.email.strip().lower()
    user = get_user_by_email(email)
    
    # Check if SMTP is configured before attempting
    if not is_smtp_configured():
        # User requested: E-posta servisi hiç yapılandırılmamışsa "Parola sıfırlama hizmeti şu anda kullanılamıyor." mesajı gösterilsin.
        raise HTTPException(status_code=503, detail="Parola sıfırlama hizmeti şu anda kullanılamıyor.")
    
    msg = "Bu e-posta adresiyle kayıtlı bir hesap varsa parola sıfırlama bağlantısı birkaç dakika içinde gönderilecektir."
    
    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Sadece e-posta başarıyla gönderilirse veritabanına kaydet.
        success = send_password_reset_email(email, raw_token)
        if success:
            save_password_reset_token(token_hash, user["id"], expires.isoformat())
        else:
            # Sızdırmamak için yine genel mesaj verilebilir ama admin log'da görür.
            pass
            
    return {"status": "success", "message": msg}

class ResetPasswordRequest(BaseModel):
    token: str
    password: str

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    try:
        validate_password(req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    token_hash = hashlib.sha256(req.token.encode()).hexdigest()
    user = get_user_by_password_reset_token(token_hash)
    if not user:
        raise HTTPException(status_code=400, detail="Geçersiz veya süresi dolmuş sıfırlama bağlantısı.")
        
    hashed_pw = password_hash.hash(req.password)
    update_user_password(user["id"], hashed_pw)
    
    return {"status": "success", "message": "Parolanız başarıyla güncellendi."}

resend_attempts = {}

class ResendVerificationRequest(BaseModel):
    email: EmailStr

@router.post("/resend-verification")
async def resend_verification(req: ResendVerificationRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    email = req.email.strip().lower()
    rate_key = f"{client_ip}_{email}_resend"
    now = datetime.now()
    
    # Check rate limit (60 seconds)
    last_attempt = resend_attempts.get(rate_key)
    if last_attempt:
        diff = (now - last_attempt).total_seconds()
        if diff < 60:
            raise HTTPException(status_code=429, detail=f"Lütfen yeni bir e-posta istemeden önce {int(60 - diff)} saniye bekleyin.")
            
    user = get_user_by_email(email)
    if not user:
        # Pretend we sent it so we don't leak user existence
        resend_attempts[rate_key] = now
        return {"status": "success", "message": "Eğer hesabınız varsa aktivasyon e-postası gönderildi."}
        
    if user.get("email_verified_at"):
        raise HTTPException(status_code=400, detail="Bu hesap zaten doğrulanmış.")
        
    resend_attempts[rate_key] = now
    
    if not is_smtp_configured():
        raise HTTPException(
            status_code=503,
            detail="E-posta servisi yapılandırılmamış. Giriş yapıp yerel doğrulama kodunu kullanabilirsiniz.",
        )

    if not _send_new_verification_email(user["id"], email):
        raise HTTPException(status_code=502, detail="Doğrulama e-postası gönderilemedi. SMTP ayarlarını kontrol edin.")
        
    return {"status": "success", "message": "Aktivasyon e-postası gönderildi. Gelen kutunu ve gerekirse Spam/Gereksiz klasörünü kontrol et."}


@router.post("/request-verification")
async def request_verification(request: Request, user: dict = Depends(get_current_user)):
    """Send email when configured, otherwise generate a local presentation code."""
    if user.get("email_verified_at"):
        raise HTTPException(status_code=400, detail="Bu hesap zaten doğrulanmış.")

    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}_{user['id']}_authenticated_verification"
    now = datetime.now()
    last_attempt = resend_attempts.get(rate_key)
    if last_attempt:
        diff = (now - last_attempt).total_seconds()
        if diff < 10:
            raise HTTPException(
                status_code=429,
                detail=f"Lütfen yeni bir doğrulama istemeden önce {max(1, int(10 - diff))} saniye bekleyin.",
            )
    resend_attempts[rate_key] = now

    if is_smtp_configured():
        if not _send_new_verification_email(user["id"], user["email"]):
            raise HTTPException(status_code=502, detail="Doğrulama e-postası gönderilemedi. SMTP ayarlarını kontrol edin.")
        return {
            "status": "success",
            "delivery": "email",
            "message": "Doğrulama bağlantısı e-posta adresinize gönderildi.",
        }

    local_code = f"{secrets.randbelow(1_000_000):06d}"
    _store_verification_secret(user["id"], local_code, timedelta(minutes=15))
    return {
        "status": "success",
        "delivery": "local",
        "local_code": local_code,
        "expires_in_minutes": 15,
        "message": "SMTP ayarlı olmadığı için yerel sunum kodu oluşturuldu.",
    }

@router.get("/verify-status")
async def get_verify_status(user: dict = Depends(get_current_user)):
    return {
        "verified": bool(user.get("email_verified_at")),
        "smtp_configured": is_smtp_configured(),
        "email": user["email"],
        "verification_mode": "email" if is_smtp_configured() else "local",
    }

from pydantic import BaseModel
class ConsentRequest(BaseModel):
    permission_type: str
    granted: bool

@router.get("/consents")
async def list_consents(user: dict = Depends(get_current_user)):
    from src.services.db import get_user_consents
    consents = get_user_consents(user["id"])
    return {"status": "success", "consents": consents}

@router.post("/consents")
async def update_consent(req: ConsentRequest, user: dict = Depends(get_current_user)):
    from src.services.db import grant_consent, revoke_consent
    if req.granted:
        grant_consent(user["id"], req.permission_type)
    else:
        revoke_consent(user["id"], req.permission_type)
    return {"status": "success"}
