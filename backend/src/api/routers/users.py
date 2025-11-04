from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Response

from sqlalchemy.ext.asyncio import AsyncSession
from ...db.database import get_db, get_async_db_context

from ...db.models import db_user as user_model
from ...api.schemas import user as user_schemas

from ...services import user_service
from ...db.crud import users_crud
from ...utils import auth

from ...utils.auth import (
    get_user_id_optional,
    get_read_write_user_token_data,
    get_admin_token_data,
)
from ...config.settings import PERSONAL_INSTRUCTIONS_MAX_LENGTH




router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)


@router.get("/me",
            response_model=Optional[user_schemas.User],
            summary="Get current logged-in user's profile")
async def read_current_user(
    current_user_id: Optional[str] = Depends(get_user_id_optional)
):
    """
    Retrieve the profile of the currently authenticated user.
    Returns user data if a valid session (cookie) is present, otherwise returns null.
    """
    if current_user_id is None:
        return None

    user: Optional[user_model.User] = None
    async with get_async_db_context() as db:
        user: Optional[user_model.User] = await users_crud.get_user_by_id(db, current_user_id)
        if user is None or not user.is_active:
            return None
    return user_schemas.User.from_orm(user)

@router.get(
    "/",
    response_model=List[user_schemas.User],
    dependencies=[Depends(auth.get_admin_user_id)],
)
async def read_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _ = Depends(auth.get_admin_user_id)
):
    """
    Retrieve all users. Only accessible by admin users.
    """
    return await user_service.get_users(db, skip=skip, limit=limit)


@router.put("/{user_id:str}", response_model=user_schemas.User)
async def update_user(
    user_id: str,
    user_update: user_schemas.UserUpdate,
    db: AsyncSession = Depends(get_db),
    token_data: Dict[str, Any] = Depends(get_read_write_user_token_data)
):
    """
    Update a user's profile. Admins can update any user,
    regular users can only update their own profile.
    """
    return await user_service.update_user(db, user_id, user_update, token_data)

@router.delete("/me", response_model=user_schemas.User, dependencies=[Depends(get_read_write_user_token_data)])
async def delete_me(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user_token_data: Dict[str, Any] = Depends(get_read_write_user_token_data)
):
    """
    Delete a user. Only accessible by the user itself.
    """
    user_id = current_user_token_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token data: missing user_id")

    return await user_service.delete_user(db, user_id, current_user_token_data=current_user_token_data, response=response)


@router.delete(
    "/{user_id:str}",
    response_model=user_schemas.User,
    dependencies=[Depends(auth.get_admin_user_id)],
)
async def delete_user(
    user_id: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user_token_data: Dict[str, Any] = Depends(get_admin_token_data),
):
    """
    Delete a user. Only accessible by admin users.
    Admins cannot delete themselves.
    """
    return await user_service.delete_user(db, user_id, current_user_token_data=current_user_token_data, response=response)


@router.get(
    "/me/personal-instructions",
    response_model=user_schemas.PersonalInstructionsResponse,
    summary="Get current user's personal instructions",
)
async def get_personal_instructions(
    current_user_id: Optional[str] = Depends(get_user_id_optional),
):
    if current_user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    async with get_async_db_context() as db:
        instructions = await users_crud.get_user_personal_instructions(db, current_user_id)
    return user_schemas.PersonalInstructionsResponse(personal_instructions=instructions)


@router.put(
    "/me/personal-instructions",
    response_model=user_schemas.PersonalInstructionsResponse,
    summary="Update current user's personal instructions",
)
async def update_personal_instructions(
    update: user_schemas.PersonalInstructionsUpdate,
    current_user_token_data: Dict[str, Any] = Depends(get_read_write_user_token_data),
    db: AsyncSession = Depends(get_db),
):
    user_id = current_user_token_data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    instructions = update.personal_instructions
    if instructions is not None:
        instructions = instructions.strip()
        if not instructions:
            instructions = None
        elif len(instructions) > PERSONAL_INSTRUCTIONS_MAX_LENGTH:
            raise HTTPException(
                status_code=400,
                detail=f"Personal instructions must be at most {PERSONAL_INSTRUCTIONS_MAX_LENGTH} characters.",
            )

    updated_user = await users_crud.update_user_personal_instructions(
        db,
        user_id,
        instructions,
    )
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return user_schemas.PersonalInstructionsResponse(
        personal_instructions=updated_user.personal_instructions
    )
