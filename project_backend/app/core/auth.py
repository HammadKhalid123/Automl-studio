from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import config
from app.db.models import RevokedToken, User
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)


def create_access_token(user_id: int):
    if not config.JWT_SECRET:
        raise RuntimeError("Authentication signing key is not configured.")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expires_at, "jti": uuid4().hex}, config.JWT_SECRET, algorithm="HS256")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer" or not config.JWT_SECRET:
        raise unauthorized
    try:
        claims = jwt.decode(credentials.credentials, config.JWT_SECRET, algorithms=["HS256"])
        user_id = int(claims["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise unauthorized
    if not claims.get("jti") or db.scalar(select(RevokedToken.id).where(RevokedToken.jti == claims["jti"])) is not None:
        raise unauthorized
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_verified:
        raise unauthorized
    return user
