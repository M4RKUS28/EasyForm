"""
User service for handling user-related business logic (registration, profile image update, etc).
"""
from typing import List, Optional, Any, Dict

from fastapi import HTTPException, status, Response
from sqlalchemy.ext.asyncio import AsyncSession


from ..db.crud import users_crud
from ..db.models import db_user as user_model
from ..core.security import get_password_hash, verify_password
from ..core.enums import UserRole, ThemePreference

from . import auth_service


async def get_users(db: AsyncSession, skip: int = 0, limit: int = 999) -> List[user_model.User]:
    """Retrieve a list of users."""
    users = await users_crud.get_users(db, skip=skip, limit=limit)
    return users

async def update_user(db: AsyncSession, user_id: str, user_update, current_user_token_data: Dict[str, Any]) -> user_model.User:
    """ 
    Update a user's profile. Admins can update any user, regular users can only update their own profile. 
    user_id is the user that is being updated.
    current_user is the one who performs the update.
    user_update is the data that is being updated.
    """

    # Get the user to be updated
    db_user = await users_crud.get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    current_user_id = current_user_token_data.get("user_id")
    current_user_role = current_user_token_data.get("role")
    
    # Check if the current user is authorized to update this user
    if str(db_user.id) != str(current_user_id) and current_user_role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this user")

    update_data = user_update.model_dump(exclude_unset=True)
    
    # Check if username is being updated and if it already exists
    if "username" in update_data and update_data["username"]:
        existing_user = await users_crud.get_user_by_username(db, update_data["username"])
        if existing_user and str(existing_user.id) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Username '{update_data['username']}' is already taken. Please choose a different username."
            )
    if "password" in update_data and update_data["password"]:
        if str(db_user.id) == str(current_user_id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use /change_password to update your password.")
        elif current_user_role == UserRole.ADMIN:
            hashed_password = get_password_hash(update_data["password"])
            update_data["hashed_password"] = hashed_password
        del update_data["password"]
    elif "password" in update_data:
        del update_data["password"]
    if "theme" in update_data and isinstance(update_data["theme"], ThemePreference):
        update_data["theme"] = update_data["theme"].value
    if "language" in update_data and update_data["language"]:
        normalized_language = str(update_data["language"]).strip().lower()
        primary_tag = normalized_language.split("-")[0]
        update_data["language"] = primary_tag[:10]
    if current_user_role != UserRole.ADMIN:
        update_data.pop("is_active", None)
        update_data.pop("role", None)
    return await users_crud.update_user(db, db_user, update_data)


async def change_password(db: AsyncSession, user_id: str, password_data, current_user_token_data: Dict[str, Any]) -> user_model.User:
    """ Change a user's password. """

    current_user_id = current_user_token_data.get("user_id")
    current_user_role = current_user_token_data.get("role")

    if str(user_id) != str(current_user_id) and current_user_role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to change this user's password")
    db_user = users_crud.get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    if not password_data.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password not provided")
    if current_user_role != UserRole.ADMIN and password_data.old_password:
        if not verify_password(password_data.old_password, db_user.hashed_password):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect old password")
    elif current_user_role != UserRole.ADMIN and not password_data.old_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Old password is required")
    hashed_password = get_password_hash(password_data.new_password)
    return users_crud.change_user_password(db, db_user, hashed_password)


async def delete_user(db: AsyncSession, user_id: str, current_user_token_data: Dict[str, Any], response: Response) -> user_model.User:
    """ Delete a user. Admins can delete any user, regular users can only delete their own profile. """

    current_user_id = current_user_token_data.get("user_id")
    current_user_role = current_user_token_data.get("role")

    if current_user_role == UserRole.ADMIN and str(user_id) == str(current_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins cannot delete themselves.")
    
    db_user = await users_crud.get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    await auth_service.logout_user(response)
    return await users_crud.delete_user(db, db_user)

