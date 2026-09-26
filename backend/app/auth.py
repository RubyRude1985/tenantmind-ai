import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException
from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .models import User


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, rounds, salt_b64, digest_b64 = encoded.split("$", 3)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt_b64), int(rounds)
        )
        return hmac.compare_digest(actual, base64.b64decode(digest_b64))
    except (ValueError, TypeError):
        return False


def create_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user.id,
            "workspace_id": user.workspace_id,
            "email": user.email,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def current_user(authorization: str = Header(...)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer ").strip(),
            get_settings().jwt_secret,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.id == payload.get("sub")))
        if user is None or user.workspace_id != payload.get("workspace_id"):
            raise HTTPException(status_code=401, detail="User not found")
        db.expunge(user)
        return user
