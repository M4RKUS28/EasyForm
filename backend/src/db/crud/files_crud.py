"""CRUD operations for file management in the database."""
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_

from ..models.db_file import File


async def create_file(
    db: AsyncSession,
    file_id: str,
    user_id: str,
    filename: str,
    content_type: str,
    file_size: int,
    data: bytes
) -> File:
    """Create a new file in the database."""
    file = File(
        id=file_id,
        user_id=user_id,
        filename=filename,
        content_type=content_type,
        file_size=file_size,
        data=data
    )
    db.add(file)
    await db.commit()
    await db.refresh(file)
    return file


async def get_file_by_id(
    db: AsyncSession,
    file_id: str
) -> Optional[File]:
    """Retrieve a file by its ID."""
    result = await db.execute(
        select(File).filter(File.id == file_id)
    )
    return result.scalar_one_or_none()


async def get_user_files(
    db: AsyncSession,
    user_id: str,
    skip: int = 0,
    limit: int = 100
) -> List[File]:
    """Retrieve all files for a specific user."""
    result = await db.execute(
        select(File)
        .filter(File.user_id == user_id)
        .order_by(File.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def get_user_files_metadata_only(
    db: AsyncSession,
    user_id: str,
    skip: int = 0,
    limit: int = 100
) -> List[File]:
    """
    Retrieve file metadata (without the BLOB data) for a specific user.
    This is more efficient for listing files without loading large BLOBs.
    """
    # Note: SQLAlchemy will still load all columns, but we can use .options(defer()) in the future
    result = await db.execute(
        select(File.id, File.user_id, File.filename, File.content_type, File.file_size, File.created_at)
        .filter(File.user_id == user_id)
        .order_by(File.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    # Convert rows to File-like objects for consistent API
    files = []
    for row in result.all():
        file_obj = File(
            id=row.id,
            user_id=row.user_id,
            filename=row.filename,
            content_type=row.content_type,
            file_size=row.file_size,
            created_at=row.created_at,
            data=b''  # Empty data for metadata-only queries
        )
        files.append(file_obj)
    return files


async def delete_file(
    db: AsyncSession,
    file_id: str
) -> bool:
    """Delete a file by its ID."""
    file = await get_file_by_id(db, file_id)
    if file:
        await db.delete(file)
        await db.commit()
        return True
    return False


async def get_user_total_storage_size(
    db: AsyncSession,
    user_id: str
) -> int:
    """Get the total storage size used by a user in bytes."""
    from sqlalchemy import func

    result = await db.execute(
        select(func.sum(File.file_size)).filter(File.user_id == user_id)
    )
    total_size = result.scalar()
    return total_size if total_size else 0


async def update_file_status(
    db: AsyncSession,
    file_id: str,
    status: str
) -> bool:
    """Update file processing status."""
    file = await get_file_by_id(db, file_id)
    if file:
        file.processing_status = status
        await db.commit()
        return True
    return False


async def update_file_page_count(
    db: AsyncSession,
    file_id: str,
    page_count: int
) -> bool:
    """Update PDF page count."""
    file = await get_file_by_id(db, file_id)
    if file:
        file.page_count = page_count
        await db.commit()
        return True
    return False
