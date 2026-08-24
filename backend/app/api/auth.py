"""Authentication routes."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from backend.app.core.config import Settings, get_settings
from backend.app.core.security import create_access_token, verify_password
from backend.app.core.security import password_context
import uuid

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenResponse(BaseModel):
    """OAuth2 bearer token response."""

    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    username: str
    password: str


class RegisterResponse(BaseModel):
    username: str
    user_id: str


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


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RegisterResponse:
    """Create a new server-side user record.

    This minimal implementation stores users in the `AUTH_USERS_JSON` setting
    (in-memory for the running process). Passwords are hashed with bcrypt.
    """
    if not payload.username or not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username and password are required")

    try:
        users = json.loads(settings.auth_users_json)
    except json.JSONDecodeError:
        users = {}

    if payload.username in users:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username already exists")

    # Generate a stable user_id and store password hash
    user_id = str(uuid.uuid4())
    password_hash = password_context.hash(payload.password)

    users[payload.username] = {"user_id": user_id, "password_hash": password_hash}

    settings.auth_users_json = json.dumps(users)

    return RegisterResponse(username=payload.username, user_id=user_id)