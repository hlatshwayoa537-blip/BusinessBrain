from datetime import datetime, timedelta, timezone
from uuid import UUID
from jose import JWTError, jwt
from pwdlib import PasswordHash
from app.core.config import settings

password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)

def create_access_token(user_id: str, business_id: str | None = None, token_version: int = 0) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    claims = {"sub": str(UUID(user_id)), "exp": expires, "ver": int(token_version)}
    if business_id:
        claims["business_id"] = str(UUID(business_id))
    return jwt.encode(claims, settings.jwt_secret_key, algorithm=ALGORITHM)

def decode_access_token_business_id(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        business_id = payload.get("business_id")
        return str(UUID(business_id)) if business_id else None
    except (JWTError, ValueError, TypeError):
        return None

def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        return str(UUID(subject)) if subject else None
    except (JWTError, ValueError, TypeError):
        return None



def decode_access_token_version(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        version = payload.get("ver", 0)
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            return None
        return version
    except (JWTError, ValueError, TypeError):
        return None
