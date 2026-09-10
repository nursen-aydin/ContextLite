import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from src.config import settings


def is_smtp_configured() -> bool:
    """A host is enough for local relays; hosted SMTP can also use credentials."""
    return bool(settings.smtp_host.strip())


def send_email(to_email: str, subject: str, body_html: str, body_text: str) -> bool:
    """Send an email using STARTTLS when enabled by configuration."""
    if not is_smtp_configured():
        print(f"[UYARI] SMTP ayarlı değil; '{to_email}' adresine e-posta gönderilmedi.")
        return False

    if bool(settings.smtp_username) != bool(settings.smtp_password):
        print("[HATA] SMTP kullanıcı adı ve parolası birlikte tanımlanmalıdır.")
        return False

    from_address = settings.mail_from.strip() or settings.smtp_username.strip()
    if not from_address:
        print("[HATA] MAIL_FROM veya SMTP_USERNAME tanımlanmalıdır.")
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.mail_from_name} <{from_address}>"
    message["To"] = to_email
    message["Message-ID"] = make_msgid(
        domain=from_address.split("@")[-1] if "@" in from_address else None
    )
    message["Date"] = formatdate(localtime=True)
    message.set_content(body_text)
    message.add_alternative(body_html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.ehlo()
            if settings.smtp_use_tls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
        return True
    except Exception as exc:
        print(f"[HATA] E-posta gönderme hatası: {exc}")
        return False


def send_verification_email(to_email: str, token: str) -> bool:
    verify_url = f"{settings.app_base_url.rstrip('/')}/verify-email?token={token}"
    subject = "ContextLite - E-posta Adresini Doğrula"
    body_text = f"""ContextLite'a hoş geldin!

E-posta adresini doğrulamak için aşağıdaki bağlantıyı aç:
{verify_url}

Bu bağlantı 24 saat geçerlidir. Hesabı sen oluşturmadıysan bu iletiyi yok sayabilirsin.

ContextLite
"""
    body_html = f"""<!doctype html>
<html lang="tr"><body style="font-family:Arial,sans-serif;line-height:1.6;color:#111827;max-width:600px;margin:auto;padding:24px">
  <h1 style="color:#4f46e5;font-size:24px">ContextLite</h1>
  <h2 style="font-size:20px">E-posta adresini doğrula</h2>
  <p>Hesabını etkinleştirmek için aşağıdaki düğmeye tıkla.</p>
  <p style="margin:28px 0"><a href="{verify_url}" style="background:#4f46e5;color:#fff;text-decoration:none;padding:12px 20px;border-radius:7px">E-postamı doğrula</a></p>
  <p style="font-size:13px;color:#6b7280">Düğme çalışmazsa bu bağlantıyı tarayıcıya yapıştır:</p>
  <p style="font-size:12px;word-break:break-all;background:#f3f4f6;padding:10px">{verify_url}</p>
  <p style="font-size:12px;color:#6b7280">Bağlantı 24 saat geçerlidir.</p>
</body></html>"""
    return send_email(to_email, subject, body_html, body_text)


def send_password_reset_email(to_email: str, token: str) -> bool:
    reset_url = f"{settings.app_base_url.rstrip('/')}/reset-password?token={token}"
    subject = "ContextLite - Parola Sıfırlama"
    body_text = f"""Parolanı sıfırlamak için aşağıdaki bağlantıyı aç:
{reset_url}

Bu bağlantı 1 saat geçerlidir. İsteği sen yapmadıysan bu iletiyi yok sayabilirsin.

ContextLite
"""
    body_html = f"""<!doctype html>
<html lang="tr"><body style="font-family:Arial,sans-serif;line-height:1.6;color:#111827;max-width:600px;margin:auto;padding:24px">
  <h1 style="color:#4f46e5;font-size:24px">ContextLite</h1>
  <h2 style="font-size:20px">Parolanı sıfırla</h2>
  <p>Yeni parola belirlemek için aşağıdaki düğmeye tıkla.</p>
  <p style="margin:28px 0"><a href="{reset_url}" style="background:#4f46e5;color:#fff;text-decoration:none;padding:12px 20px;border-radius:7px">Parolamı sıfırla</a></p>
  <p style="font-size:13px;color:#6b7280">Bağlantı 1 saat geçerlidir.</p>
  <p style="font-size:12px;color:#9ca3af">© {datetime.now().year} ContextLite</p>
</body></html>"""
    return send_email(to_email, subject, body_html, body_text)
