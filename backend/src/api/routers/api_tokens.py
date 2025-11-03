"""
API Token Router
Endpoints for managing API tokens for browser extension authentication.
"""
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.crud import api_tokens_crud
from ...utils.auth import get_read_write_user_token_data
from ..schemas import api_token as api_token_schema
from ..schemas import auth as auth_schema


router = APIRouter(
    prefix="/api-tokens",
    tags=["api-tokens"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/",
    response_model=api_token_schema.APITokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API token"
)
async def create_api_token(
    token_data: api_token_schema.APITokenCreate,
    db: AsyncSession = Depends(get_db),
    current_user_token_data: Dict[str, Any] = Depends(get_read_write_user_token_data)
):
    """
    Create a new API token for the authenticated user.

    The token will be valid for at least 1 year.
    The token is only returned once during creation - store it securely!
    """
    user_id = current_user_token_data.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token data: missing user_id"
        )

    # Generate unique token ID
    token_id = str(uuid.uuid4())

    # Generate secure token (64 bytes = 128 hex characters)
    token_string = f"easyform_{secrets.token_hex(64)}"

    # Set expiration to 1 year from now
    expires_at = datetime.now(timezone.utc) + timedelta(days=365)

    # Create token in database
    new_token = await api_tokens_crud.create_api_token(
        db=db,
        token_id=token_id,
        user_id=user_id,
        token=token_string,
        expires_at=expires_at,
        name=token_data.name
    )

    return api_token_schema.APITokenCreateResponse(
        id=new_token.id,
        name=new_token.name,
        token=new_token.token,
        created_at=new_token.created_at,
        expires_at=new_token.expires_at,
        is_active=new_token.is_active
    )


@router.get(
    "/",
    response_model=api_token_schema.APITokenListResponse,
    summary="Get all API tokens for current user"
)
async def get_user_api_tokens(
    db: AsyncSession = Depends(get_db),
    current_user_token_data: Dict[str, Any] = Depends(get_read_write_user_token_data)
):
    """
    Retrieve all API tokens for the authenticated user.

    Note: The actual token strings are not returned for security reasons.
    """
    user_id = current_user_token_data.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token data: missing user_id"
        )

    tokens = await api_tokens_crud.get_user_api_tokens(db, user_id)

    return api_token_schema.APITokenListResponse(
        tokens=[
            api_token_schema.APITokenResponse(
                id=token.id,
                name=token.name,
                created_at=token.created_at,
                expires_at=token.expires_at,
                last_used_at=token.last_used_at,
                is_active=token.is_active
            )
            for token in tokens
        ]
    )


@router.delete(
    "/{token_id}",
    response_model=auth_schema.APIResponseStatus,
    summary="Delete an API token"
)
async def delete_api_token(
    token_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_token_data: Dict[str, Any] = Depends(get_read_write_user_token_data)
):
    """
    Delete an API token by its ID.

    Users can only delete their own tokens.
    """
    user_id = current_user_token_data.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token data: missing user_id"
        )

    # Verify token belongs to user
    token = await api_tokens_crud.get_api_token_by_id(db, token_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found"
        )

    if token.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own tokens"
        )

    # Delete token
    success = await api_tokens_crud.delete_api_token(db, token_id)

    if success:
        return auth_schema.APIResponseStatus(
            status="success",
            msg="Token deleted successfully"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete token"
        )
