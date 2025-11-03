"""
File Management Router
Endpoints for uploading, listing, downloading, and deleting files.
"""
from typing import Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...services import file_service
from ...utils.auth import get_read_write_user_token_data, get_user_id_from_api_token_or_cookie
from ..schemas import file as file_schema
from ..schemas import auth as auth_schema


router = APIRouter(
    prefix="/files",
    tags=["files"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/upload",
    response_model=file_schema.FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file"
)
async def upload_file(
    file_upload: file_schema.FileUpload,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a file (image or PDF) as base64.

    Supports authentication via:
    - Cookie (web app)
    - Authorization header with API token (browser extension)

    Maximum file size: 200MB
    Allowed types: PNG, JPEG, JPG, GIF, WEBP, PDF
    """
    # Get user_id from either API token or cookie
    user_id = await get_user_id_from_api_token_or_cookie(request)

    return await file_service.upload_file(db, user_id, file_upload)


@router.get(
    "/",
    response_model=file_schema.FileListResponse,
    summary="Get all files for current user"
)
async def get_user_files(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all files for the authenticated user.

    Returns metadata only (no file data) for performance.
    """
    # Get user_id from either API token or cookie
    user_id = await get_user_id_from_api_token_or_cookie(request)

    return await file_service.get_user_files(db, user_id)


@router.get(
    "/{file_id}",
    response_model=file_schema.FileDownloadResponse,
    summary="Download a file"
)
async def download_file(
    file_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Download a file by ID.

    Returns the file data as base64.
    Users can only download their own files.
    """
    # Get user_id from either API token or cookie
    user_id = await get_user_id_from_api_token_or_cookie(request)

    return await file_service.get_file(db, file_id, user_id)


@router.delete(
    "/{file_id}",
    response_model=auth_schema.APIResponseStatus,
    summary="Delete a file"
)
async def delete_file(
    file_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a file by ID.

    Users can only delete their own files.
    """
    # Get user_id from either API token or cookie
    user_id = await get_user_id_from_api_token_or_cookie(request)

    success = await file_service.delete_file(db, file_id, user_id)

    if success:
        return auth_schema.APIResponseStatus(
            status="success",
            msg="File deleted successfully"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )
