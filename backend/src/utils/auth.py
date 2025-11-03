"""
Utility functions for authentication and authorization.
"""

from typing import Any, Dict, Optional, Set
from fastapi import Depends, HTTPException, status
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
