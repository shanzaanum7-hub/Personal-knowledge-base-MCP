"""Authentication helpers and FastAPI dependencies."""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend.app.core.config import Settings, get_settings

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _jwt_secret(settings: Settings) -> str:
    """Return a configured JWT secret or fail closed for authentication use."""
    if not settings.jwt_secret_key or settings.jwt_secret_key == "change-me-before-production":
        raise RuntimeError("JWT_SECRET_KEY must be configured before authentication is used")
    return settings.jwt_secret_key


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Return whether a plaintext password matches its stored hash."""
    return password_context.verify(plain_password, password_hash)


def create_access_token(user_id: str, settings: Settings) -> str:
    """Create a short-lived JWT whose subject is the authenticated user ID."""
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": user_id, "exp": expires_at}
    return jwt.encode(payload, _jwt_secret(settings), algorithm=settings.jwt_algorithm)


def get_user_id_from_token(
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Extract and validate the user ID from a bearer token.

    The ID comes only from the signed token, never from a request body or query
    parameter, so callers can safely use it for Qdrant payload filtering.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, _jwt_secret(settings), algorithms=[settings.jwt_algorithm]
        )
        user_id = payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise credentials_error
        return user_id
    except (JWTError, TypeError, ValueError) as error:
        raise credentials_error from error


CurrentUserId = Annotated[str, Depends(get_user_id_from_token)]