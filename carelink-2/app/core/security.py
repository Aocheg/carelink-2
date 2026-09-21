"""Authentication and role authorization for CARELINK.

This module deliberately keeps authentication self-contained: passwords are hashed with
scrypt and short-lived signed bearer tokens are issued with HMAC-SHA256. For production,
replace the secret with a managed secret and consider an external identity provider.
"""
import base64, hashlib, hmac, json, os, secrets
from datetime import datetime, timedelta, timezone
from typing import Callable

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.connection import get_db
from app.database import models as m

bearer = HTTPBearer(auto_error=False)
ROLES = {"ADMIN", "DOCTOR", "NURSE", "LAB", "STAFF"}

def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("password must contain at least 8 characters")
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"

def verify_password(password: str, encoded: str) -> bool:
    try:
        if encoded.startswith("scrypt$"):
            _, n, r, p, salt_hex, digest_hex = encoded.split("$")
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
            actual = hashlib.scrypt(password.encode(), salt=salt, n=int(n), r=int(r), p=int(p))
            return hmac.compare_digest(actual, expected)
        # Compatibility with the pre-authentication CARELINK-2 hash format.
        if ":" in encoded:
            salt_hex, digest_hex = encoded.split(":", 1)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(digest_hex)
            actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
            return hmac.compare_digest(actual, expected)
        return False
    except (ValueError, TypeError):
        return False

def _secret() -> bytes:
    return get_settings().secret_key.encode()

def create_access_token(user_id: int, role: str, expires_minutes: int = 60) -> str:
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"

def decode_access_token(token: str) -> dict:
    try:
        body, encoded_sig = token.split(".", 1)
        expected = hmac.new(_secret(), body.encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(encoded_sig + "=" * (-len(encoded_sig) % 4))
        if not hmac.compare_digest(expected, supplied):
            raise ValueError
        raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        payload = json.loads(raw)
        if int(payload["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=401, detail="invalid or expired access token")

def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> m.User:
    if not credentials:
        raise HTTPException(status_code=401, detail="bearer authentication required")
    payload = decode_access_token(credentials.credentials)
    user = db.get(m.User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="user is inactive or does not exist")
    return user

def require_roles(*roles: str) -> Callable:
    allowed = set(roles)
    def dependency(user: m.User = Depends(current_user)) -> m.User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail=f"required role: {', '.join(sorted(allowed))}")
        return user
    return dependency
