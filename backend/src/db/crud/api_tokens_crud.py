"""CRUD operations for API token management in the database."""
from typing import Optional, List
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from ..models.db_api_token import APIToken


async def create_api_token(
    db: AsyncSession,
    token_id: str,
    user_id: str,
    token: str,
    expires_at: datetime,
    name: Optional[str] = None
) -> APIToken:
    """Create a new API token in the database."""
    api_token = APIToken(
        id=token_id,
        user_id=user_id,
        token=token,
        name=name,
        expires_at=expires_at,
        is_active=True
    )
    db.add(api_token)
    await db.commit()
    await db.refresh(api_token)
    return api_token


async def get_api_token_by_token_string(
    db: AsyncSession,
    token: str
) -> Optional[APIToken]:
    """Retrieve an API token by the token string."""
    result = await db.execute(
        select(APIToken).filter(
            and_(
                APIToken.token == token,
                APIToken.is_active == True
            )
        )
    )
    return result.scalar_one_or_none()


async def get_api_token_by_id(
    db: AsyncSession,
    token_id: str
) -> Optional[APIToken]:
    """Retrieve an API token by its ID."""
    result = await db.execute(
        select(APIToken).filter(APIToken.id == token_id)
    )
    return result.scalar_one_or_none()


async def get_user_api_tokens(
    db: AsyncSession,
    user_id: str
) -> List[APIToken]:
    """Retrieve all API tokens for a specific user."""
    result = await db.execute(
        select(APIToken).filter(APIToken.user_id == user_id).order_by(APIToken.created_at.desc())
    )
    return result.scalars().all()


async def delete_api_token(
    db: AsyncSession,
    token_id: str
) -> bool:
    """Delete an API token by its ID."""
    api_token = await get_api_token_by_id(db, token_id)
    if api_token:
        await db.delete(api_token)
        await db.commit()
        return True
    return False


async def update_last_used(
    db: AsyncSession,
    token_id: str
) -> Optional[APIToken]:
    """Update the last_used_at timestamp for an API token."""
    api_token = await get_api_token_by_id(db, token_id)
    if api_token:
        api_token.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(api_token)
    return api_token


async def deactivate_api_token(
    db: AsyncSession,
    token_id: str
) -> Optional[APIToken]:
    """Deactivate an API token (soft delete)."""
    api_token = await get_api_token_by_id(db, token_id)
    if api_token:
        api_token.is_active = False
        await db.commit()
        await db.refresh(api_token)
    return api_token
