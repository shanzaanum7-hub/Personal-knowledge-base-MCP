"""Authentication routes."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from backend.app.core.config import Settings, get_settings
from backend.app.core.security import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenResponse(BaseModel):
    """OAuth2 bearer token response."""

    access_token: str
    token_type: str = "bearer"


def _configured_users(settings: Settings) -> dict[str, dict[str, str]]:
    """Load username records from the JSON authentication setting."""
    try:
        users = json.loads(settings.auth_users_json)
    except json.JSONDecodeError as error:
        raise RuntimeError("AUTH_USERS_JSON must contain valid JSON") from error
    if not isinstance(users, dict):
        raise RuntimeError("AUTH_USERS_JSON must be a JSON object")
    return users


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Verify credentials and issue a JWT containing the user's `user_id`.

    `AUTH_USERS_JSON` stores records as `{username: {user_id, password_hash}}`.
    The client supplies only credentials; it cannot choose the token subject.
    """
    user = _configured_users(settings).get(form_data.username)
    if (
        not isinstance(user, dict)
        or not isinstance(user.get("user_id"), str)
        or not isinstance(user.get("password_hash"), str)
        or not verify_password(form_data.password, user["password_hash"])
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(access_token=create_access_token(user["user_id"], settings))