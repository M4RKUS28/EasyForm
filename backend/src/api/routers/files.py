# app/routes/files_deprecated.py
import os
import tempfile
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Form
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.bucket_session import get_bucket_session, BucketSession
from ...db.crud.bucket_base_repo import (
    upload_file, make_file_public, generate_signed_get_url,
    generate_signed_put_url, delete_file, file_exists, list_files, verify_user_access,
)
from ...db.database import get_db
from ...utils.auth import get_read_write_user_id, get_read_only_user_id
from ...db.crud.bucket_base_repo import get_file_info
from ...db.crud import recipe_crud

from fastapi.responses import Response
from ...db.crud.bucket_base_repo import get_file, get_file_info


router = APIRouter(prefix="/files", tags=["files"])

@router.post("/upload")
async def upload(
    user_id: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    sess: BucketSession = Depends(get_bucket_session),
    current_user_id: str = Depends(get_read_write_user_id)
):
    """
    Upload a file to GCS bucket.
    
    Args:
        user_id: User ID
        category: File category (e.g., "recipes", "images", "documents")
        file: File to upload
        
    Returns:
        File info including key, original_filename, size, etc.
    """
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot upload files for other users.")

    # tempfile.gettempdir() works cross-platform (Windows: C:\Users\...\AppData\Local\Temp, Linux: /tmp)
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        body = await file.read()
        tmp.write(body)
        tmp.flush()
        tmp_path = tmp.name
    try:
        file_info = await upload_file(
            sess, 
            user_id, 
            category,
            tmp_path, 
            file.filename, 
            file.content_type
        )
        return file_info['key']
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass



@router.post("/public-upload")
async def upload_public(
    user_id: str = Form(...),
    category: str = Form(...),
    file: UploadFile = File(...),
    sess: BucketSession = Depends(get_bucket_session),
    current_user_id: str = Depends(get_read_write_user_id)
):
    """
    Upload a file to GCS bucket.

    Args:
        user_id: User ID
        category: File category (e.g., "recipes", "images", "documents")
        file: File to upload

    Returns:
        public URL of the uploaded file.
    """
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot upload files for other users.")

    # tempfile.gettempdir() works cross-platform (Windows: C:\Users\...\AppData\Local\Temp, Linux: /tmp)
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        body = await file.read()
        tmp.write(body)
        tmp.flush()
        tmp_path = tmp.name
    try:
        file_info = await upload_file( sess, user_id, category, tmp_path, file.filename, file.content_type)
        public_meta = await make_file_public(sess, file_info['key'])
        return public_meta['public_url']
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


@router.get("/serve/{key:path}")
async def serve_file(key: str,
        sess: BucketSession = Depends(get_bucket_session),
        user_id: str = Depends(get_read_write_user_id)):
    """Serve file content directly with proper content type."""

    # Verify user access
    verify_user_access(key, user_id)

    # Get file info to determine content type
    file_info = await get_file_info(sess, key)

    # Get file bytes
    file_bytes = await get_file(sess, key)

    # Return file with proper content type
    return Response(
        content=file_bytes,
        media_type=file_info.get('content_type', 'application/octet-stream'),
        headers={
            'Cache-Control': 'public, max-age=3600',  # Cache for 1 hour
        }
    )


@router.get("/info/{key:path}")
async def get_info(key: str, sess: BucketSession = Depends(get_bucket_session),
        user_id: str = Depends(get_read_only_user_id)):
    """Get file information by key."""
    # Verify user access
    verify_user_access(key, user_id)

    return await get_file_info(sess, key)


@router.post("/public-url")
async def public_url(key: str,
    sess: BucketSession = Depends(get_bucket_session),
    user_id: str = Depends(get_read_write_user_id)):
    """Make file public and get public URL."""

    # Verify user access
    verify_user_access(key, user_id)
    return await make_file_public(sess, key)


@router.post("/signed-url")
async def signed_get(key: str, minutes: int = 60,
    sess: BucketSession = Depends(get_bucket_session),
    user_id: str = Depends(get_read_only_user_id)):
    """Generate signed GET URL for private file access."""

    # Verify user access
    verify_user_access(key, user_id)
    return await generate_signed_get_url(sess, key, minutes)


@router.post("/signed-put")
async def signed_put(
    user_id: str,
    category: str,
    filename: str,
    content_type: str,
    minutes: int = 15,
    sess: BucketSession = Depends(get_bucket_session)
):
    """Generate signed PUT URL for direct upload from client."""

    return await generate_signed_put_url(sess, user_id, category, filename, content_type, minutes)


@router.get("/exists/{key:path}")
async def exists(key: str,
    sess: BucketSession = Depends(get_bucket_session),
    user_id: str = Depends(get_read_only_user_id)):
    """Check if file exists and get info."""

    # Verify user access
    verify_user_access(key, user_id)
    return await file_exists(sess, key)


@router.get("/list")
async def list_(
    user_id: str, 
    category: str = None,
    date_prefix: str = None,
    max_results: int = 1000,
    sess: BucketSession = Depends(get_bucket_session)
):
    """
    List files for a user.
    
    Args:
        user_id: User ID
        category: Optional filter by category (e.g., "recipes")
        date_prefix: Optional filter by date (e.g., "01-10-2025" or "01-10")
        max_results: Max number of results
    """
    items = await list_files(sess, user_id, category, date_prefix, max_results)
    return {"files": items, "count": len(items)}


@router.delete("/{key:path}")
async def delete_(key: str, sess: BucketSession = Depends(get_bucket_session),
    user_id: str = Depends(get_read_write_user_id)):

    """Delete file by key."""
    # Verify user access
    verify_user_access(key, user_id)
    return await delete_file(sess, key)


@router.get("/recipe-image/{recipe_id}")
async def get_image_by_recipe_id(
    recipe_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_read_only_user_id)
):
    """
    Get the image URL for a specific recipe by recipe ID.
    Returns null if the image is not yet generated.

    Args:
        recipe_id: The recipe ID

    Returns:
        dict: {"image_url": str | null}
    """
    recipe = await recipe_crud.get_recipe_by_id(db, recipe_id)

    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    # Verify the recipe belongs to the user
    if recipe.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden: Recipe does not belong to the authenticated user")

    return {"image_url": recipe.image_url}



