"""Credential verification and access-token issuance for authentication routes."""

import json
from dataclasses import dataclass

from backend.app.core.config import Settings
from backend.app.core.security import create_access_token, verify_password


@dataclass(frozen=True)
class UserRecord:
    """The minimum server-side identity data needed for authentication."""

    user_id: str
    password_hash: str


def load_users(settings: Settings) -> dict[str, UserRecord]:
    """Parse configured users from ``AUTH_USERS_JSON``.

    The setting must contain ``{username: {user_id, password_hash}}``. Passwords
    are never accepted or persisted in plaintext, and the request cannot choose
    a user's ID.
    """
    try:
        raw_users = json.loads(settings.auth_users_json)
    except json.JSONDecodeError as error:
        raise ValueError("AUTH_USERS_JSON must contain valid JSON") from error

    if not isinstance(raw_users, dict):
        raise ValueError("AUTH_USERS_JSON must be a JSON object")

    users: dict[str, UserRecord] = {}
    for username, raw_user in raw_users.items():
        if not isinstance(username, str) or not isinstance(raw_user, dict):
            raise ValueError("Each configured user must be an object keyed by username")
        user_id = raw_user.get("user_id")
        password_hash = raw_user.get("password_hash")
        if not isinstance(user_id, str) or not user_id:
            raise ValueError(f"Configured user {username!r} needs a non-empty user_id")
        if not isinstance(password_hash, str) or not password_hash:
            raise ValueError(f"Configured user {username!r} needs a password_hash")
        users[username] = UserRecord(user_id=user_id, password_hash=password_hash)
    return users


def authenticate_user(
    username: str,
    password: str,
    settings: Settings,
) -> UserRecord | None:
    """Return the matching user for valid credentials, otherwise ``None``."""
    user = load_users(settings).get(username)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def issue_access_token(username: str, password: str, settings: Settings) -> str | None:
    """Verify credentials and issue a JWT containing the server-side user ID."""
    user = authenticate_user(username, password, settings)
    if user is None:
        return None
    return create_access_token(user.user_id, settings)