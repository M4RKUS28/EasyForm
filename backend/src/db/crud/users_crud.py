"""CRUD operations for user management in the database."""
from typing import Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.db_user import User
from ...core.enums import UserRole, ThemePreference



async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Retrieve a user by their ID."""
    result = await db.execute(select(User).filter(User.id == user_id))
    return result.scalar_one_or_none()

async def get_user_personal_instructions(db: AsyncSession, user_id: str) -> Optional[str]:
    """Return the personal instructions string for the given user."""
    result = await db.execute(select(User.personal_instructions).filter(User.id == user_id))
    return result.scalar_one_or_none()

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    """Retrieve a user by their username."""
    result = await db.execute(select(User).filter(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Retrieve a user by their email."""
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession,
                user_id: str,
                username: str,
                email: str, hashed_password: str,
                is_active=True,
                role=UserRole.USER.value,
                profile_image_url=None,
                theme: str = ThemePreference.LIGHT.value,
                language: str = "en"):
    """Create a new user in the database."""
    if isinstance(theme, ThemePreference):
        theme = theme.value
    normalized_language = (language or "en").strip().lower()
    primary_language = normalized_language.split("-")[0]
    sanitized_language = primary_language[:10] if primary_language else "en"

    user = User(
        id=user_id,
        username=username,
        email=email,
        hashed_password=hashed_password,
        is_active=is_active,
        role=role,
        theme=theme,
        language=sanitized_language or "en",
    )
    if profile_image_url:
        user.profile_image_url = profile_image_url
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def update_user_last_login(db: AsyncSession, user_id: str) -> Optional[User]:
    """Update the last_login time for a user."""
    user = await get_user_by_id(db, user_id)
    if user:
        # If last_login is not set, this is the first login - start streak at 1
        if not user.last_login:
            user.login_streak = 1
        else:
            # Calculate the difference in days using timedelta
            time_diff: timedelta = datetime.now(timezone.utc).date() - user.last_login.date()
            days_since_last_login = time_diff.days
            
            if days_since_last_login == 0:
                # Same day login - keep current streak
                pass
            elif days_since_last_login == 1:
                # Consecutive day - increment streak
                user.login_streak += 1
            else:
                # More than one day gap - reset streak to 1
                user.login_streak = 1

        user.last_login = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
    return user

async def update_user_personal_instructions(db: AsyncSession, user_id: str, instructions: Optional[str]) -> Optional[User]:
    """Update the stored personal instructions for a user."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None
    user.personal_instructions = instructions
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_profile_image(db: AsyncSession, user: User, profile_image_url: str):
    """Update the profile image of an existing user."""
    user.profile_image_url = profile_image_url # type: ignore
    await db.commit()
    await db.refresh(user)
    return user

async def get_users(db: AsyncSession, skip: int = 0, limit: int = 200):
    """Retrieve users with pagination."""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()

async def update_user(db: AsyncSession, db_user: User, update_data: dict):
    """Update an existing user's information."""
    for key, value in update_data.items():
        if isinstance(value, ThemePreference):
            value = value.value
        setattr(db_user, key, value)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def change_user_password(db: AsyncSession, db_user: User, hashed_password: str):
    """Change an existing user's password."""
    setattr(db_user, "hashed_password", hashed_password)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def get_active_user_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
    """Retrieve an active user by their ID."""
    result = await db.execute(select(User).filter(User.id == user_id, User.is_active))
    return result.scalar_one_or_none()

async def delete_user(db: AsyncSession, db_user: User):
    """
    Delete a user from the database, including all associated data:
    - Notes
    - Questions in course chapters
    - Courses 
    - Documents
    - Images
    
    This ensures no foreign key constraints are violated.
    """
    # 1. Delete all notes associated with the user
    
    # 11. Finally, delete the user
    await db.delete(db_user)
    await db.commit()
    return db_user


