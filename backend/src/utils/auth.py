"""
Utility functions for authentication and authorization.
"""

from typing import Any, Dict, Optional, Set
from fastapi import Depends, HTTPException, status, Request
from pydantic import BaseModel

from ..db.models import db_user as user_model
from ..core import security, enums
from ..core.enums import AccessLevel
from ..core.security import get_access_token_from_cookie

READ_ACCESS_LEVELS: Set[AccessLevel] = {
    AccessLevel.READ_ONLY,
    AccessLevel.READ_WRITE,
}

WRITE_ACCESS_LEVELS: Set[AccessLevel] = {
    AccessLevel.WRITE_ONLY,
    AccessLevel.READ_WRITE,
}

class TokenData(BaseModel):
    """Schema for the token data."""
    username: Optional[str] = None
    user_id: Optional[str] = None
    email: Optional[str] = None # Added email
    role: Optional[enums.UserRole] = None


def _ensure_access_level(payload: Dict[str, Any], allowed_levels: Set[AccessLevel]) -> None:
    """Check if the token has the required access level."""
    raw_value = payload.get("access_level")
    try:
        access_level = AccessLevel(raw_value)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have the required access level",
        ) from exc

    if access_level not in allowed_levels:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have the required access level",
        )


async def get_user_id(
    access_token: Optional[str] = Depends(get_access_token_from_cookie),
) -> str:
    """
    Return the user_id from the access token with write permissions (requires access_level='rw' or 'w').
    """
    # Check if the access token is provided and valid and contains user_id
    payload = security.verify_token(access_token)
    # check access level
    _ensure_access_level(payload, WRITE_ACCESS_LEVELS)
    return payload.get("user_id")


async def get_read_only_user_id(
    access_token: Optional[str] = Depends(get_access_token_from_cookie),
) -> str:
    """Return the user_id from the access token with read permissions (requires access_level='r' or 'rw').
    
    Does not fetch the user from the database.
    """
    # Check if the access token is provided and valid and contains user_id
    payload = security.verify_token(access_token)
    # check access level
    _ensure_access_level(payload, READ_ACCESS_LEVELS)
    return payload.get("user_id")


async def get_read_write_user_token_data(
    access_token: Optional[str] = Depends(get_access_token_from_cookie),
) -> Dict[str, Any]:
    """Return the token data from the access token with read and write permissions."""
    # Check if the access token is provided and valid and contains user_id
    payload = security.verify_token(access_token)
    # check access level
    _ensure_access_level(payload, WRITE_ACCESS_LEVELS)
    return payload

async def get_user_id_optional(
    access_token: Optional[str] = Depends(get_access_token_from_cookie),
) -> Optional[str]:
    """Return the user_id from the access token if present, otherwise None.
    
    Does not fetch the user from the database.
    This is useful for endpoints where the user may not be required to be logged in.
    """
    if not access_token:
        return None

    try:
        payload = security.verify_token(access_token)
        user_id = payload.get("user_id")
        return user_id
    except HTTPException:
        return None


async def get_admin_user_id(
    access_token: Optional[str] = Depends(get_access_token_from_cookie),
) -> str:
    """Return the user_id from the access token if the user is an admin.
    
    Does not fetch the user from the database, checks the role from the token.
    """
    # Check if the access token is provided and valid and contains user_id, role
    payload = security.verify_token(access_token)
    _ensure_access_level(payload, WRITE_ACCESS_LEVELS)

    if payload.get("role") != enums.UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    
    return payload.get("user_id")

async def get_admin_token_data(
    access_token: Optional[str] = Depends(get_access_token_from_cookie),
) -> Dict[str, Any]:
    """Return the token data if the user is an admin."""
    # Check if the access token is provided and valid and contains user_id, role
    payload = security.verify_token(access_token)
    _ensure_access_level(payload, WRITE_ACCESS_LEVELS)

    if payload.get("role") != enums.UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    
    return payload


async def get_read_write_user_id(
    access_token: Optional[str] = Depends(get_access_token_from_cookie)
) -> user_model.User:
    """Return the user ID with read and write permissions.
    """
    payload = security.verify_token(access_token)
    _ensure_access_level(payload, WRITE_ACCESS_LEVELS)

    return payload.get("user_id")


async def get_token_from_header_or_cookie(request: Request) -> Optional[str]:
    """
    Extract token from Authorization header (Bearer token) or cookie.

    Priority:
    1. Authorization header: "Bearer <api_token>"
    2. Cookie: "__session" (access token)

    Returns None if no token is found.
    """
    # Check Authorization header first (for API tokens)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1).strip()

    # Fallback to cookie (for web app)
    return await get_access_token_from_cookie(request)


async def get_user_id_from_api_token_or_cookie(
    request: Request,
) -> str:
    """
    Return the user_id from either an API token (Authorization header) or cookie.

    This function supports both:
    - Browser extension using API tokens in Authorization header
    - Web app using cookie-based authentication

    Requires write access level.
    """
    from ..db.database import get_async_db_context
    from ..db.crud import api_tokens_crud, users_crud
    from datetime import datetime, timezone

    token = await get_token_from_header_or_cookie(request)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: token missing",
        )

    # Check if it's an API token (starts with "easyform_")
    if token.startswith("easyform_"):
        async with get_async_db_context() as db:
            api_token = await api_tokens_crud.get_api_token_by_token_string(db, token)

            if not api_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid API token",
                )

            # Check if token is expired
            # Make expires_at timezone-aware if it's naive
            expires_at = api_token.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)

            if expires_at < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API token expired",
                )

            # Check if token is active
            if not api_token.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API token is inactive",
                )

            # Update last_used_at (async, don't wait)
            await api_tokens_crud.update_last_used(db, api_token.id)

            # Verify user exists and is active
            user = await users_crud.get_active_user_by_id(db, api_token.user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found or inactive",
                )

            return api_token.user_id

    # Otherwise, it's a regular JWT access token from cookie
    payload = security.verify_token(token)
    _ensure_access_level(payload, WRITE_ACCESS_LEVELS)
    return payload.get("user_id")
