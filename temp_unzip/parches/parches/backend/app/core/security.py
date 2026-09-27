"""app/core/security.py  —  CORREGIDO

Hueco de seguridad: el access token no declaraba "type", asi que un refresh token
(valido 30 dias) se aceptaba como bearer en cualquier endpoint. Ahora cada token
declara su tipo y decode_token() lo valida.
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def _encode(subject: Union[str, Any], token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    return _encode(subject, ACCESS_TOKEN_TYPE,
                   expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    return _encode(subject, REFRESH_TOKEN_TYPE,
                   expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))


def decode_token(token: str, expected_type: str) -> Optional[dict]:
    """Devuelve el payload si firma, expiracion y tipo son correctos; si no, None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != expected_type or not payload.get("sub"):
        return None
    return payload


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
