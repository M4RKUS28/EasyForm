"""
Service for file upload, validation, and processing.
"""
import base64
import uuid
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import file as file_schema
from ..db.crud import files_crud


# File size limit: 200MB in bytes
MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024  # 200MB

# Allowed MIME types
ALLOWED_MIME_TYPES = [
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/gif',
    'image/webp',
    'application/pdf'
]


async def upload_file(
    db: AsyncSession,
    user_id: str,
    file_upload: file_schema.FileUpload
) -> file_schema.FileResponse:
    """
    Upload a file for a user.

    Validates:
    - File size (max 200MB)
    - Content type (only images and PDFs)
    - Base64 encoding

    Stores file as BLOB in database.
    """
    # Validate content type
    if file_upload.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type. Allowed types: {', '.join(ALLOWED_MIME_TYPES)}"
        )

    # Decode base64 data
    try:
        file_data = base64.b64decode(file_upload.data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 encoding"
        ) from e

    # Check file size
    file_size = len(file_data)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES / (1024 * 1024)}MB"
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )

    # Generate unique file ID
    file_id = str(uuid.uuid4())

    # Create file in database
    new_file = await files_crud.create_file(
        db=db,
        file_id=file_id,
        user_id=user_id,
        filename=file_upload.filename,
        content_type=file_upload.content_type,
        file_size=file_size,
        data=file_data
    )

    return file_schema.FileResponse(
        id=new_file.id,
        filename=new_file.filename,
        content_type=new_file.content_type,
        file_size=new_file.file_size,
        created_at=new_file.created_at
    )


async def get_user_files(
    db: AsyncSession,
    user_id: str
) -> file_schema.FileListResponse:
    """
    Get all files for a user (metadata only, no file data).
    """
    files = await files_crud.get_user_files_metadata_only(db, user_id)
    total_storage = await files_crud.get_user_total_storage_size(db, user_id)

    return file_schema.FileListResponse(
        files=[
            file_schema.FileResponse(
                id=file.id,
                filename=file.filename,
                content_type=file.content_type,
                file_size=file.file_size,
                created_at=file.created_at
            )
            for file in files
        ],
        total_storage_bytes=total_storage
    )


async def get_file(
    db: AsyncSession,
    file_id: str,
    user_id: str
) -> file_schema.FileDownloadResponse:
    """
    Get a file by ID (includes file data).

    Users can only download their own files.
    """
    file = await files_crud.get_file_by_id(db, file_id)

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Verify ownership
    if file.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own files"
        )

    # Encode data to base64
    data_base64 = base64.b64encode(file.data).decode('utf-8')

    return file_schema.FileDownloadResponse(
        id=file.id,
        filename=file.filename,
        content_type=file.content_type,
        file_size=file.file_size,
        data=data_base64,
        created_at=file.created_at
    )


async def delete_file(
    db: AsyncSession,
    file_id: str,
    user_id: str
) -> bool:
    """
    Delete a file by ID.

    Users can only delete their own files.
    """
    file = await files_crud.get_file_by_id(db, file_id)

    if not file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    # Verify ownership
    if file.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own files"
        )

    # Delete file
    success = await files_crud.delete_file(db, file_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file"
        )

    return True
