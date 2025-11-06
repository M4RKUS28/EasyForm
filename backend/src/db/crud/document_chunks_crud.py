"""CRUD operations for document chunks."""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.db_document_chunk import DocumentChunk


async def create_chunk(db: AsyncSession, chunk_data: dict) -> DocumentChunk:
    """Create a single document chunk."""
    chunk = DocumentChunk(**chunk_data)
    db.add(chunk)
    await db.commit()
    await db.refresh(chunk)
    return chunk


async def create_chunks(db: AsyncSession, chunks_data: List[dict]) -> List[DocumentChunk]:
    """Batch create document chunks."""
    chunks = [DocumentChunk(**data) for data in chunks_data]
    db.add_all(chunks)
    await db.commit()
    return chunks


async def get_chunk_by_id(db: AsyncSession, chunk_id: str) -> Optional[DocumentChunk]:
    """Get a chunk by ID."""
    result = await db.execute(
        select(DocumentChunk).filter(DocumentChunk.id == chunk_id)
    )
    return result.scalar_one_or_none()


async def get_chunks_by_ids(db: AsyncSession, chunk_ids: List[str]) -> List[DocumentChunk]:
    """Get multiple chunks by IDs."""
    result = await db.execute(
        select(DocumentChunk).filter(DocumentChunk.id.in_(chunk_ids))
    )
    return result.scalars().all()


async def get_chunks_by_file_id(
    db: AsyncSession,
    file_id: str
) -> List[DocumentChunk]:
    """Get all chunks for a file."""
    result = await db.execute(
        select(DocumentChunk)
        .filter(DocumentChunk.file_id == file_id)
        .order_by(DocumentChunk.chunk_index)
    )
    return result.scalars().all()


async def get_chunks_by_user_id(
    db: AsyncSession,
    user_id: str,
    skip: int = 0,
    limit: int = 100
) -> List[DocumentChunk]:
    """Get all chunks for a user."""
    result = await db.execute(
        select(DocumentChunk)
        .filter(DocumentChunk.user_id == user_id)
        .order_by(DocumentChunk.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


async def delete_chunks_by_file_id(db: AsyncSession, file_id: str) -> int:
    """Delete all chunks for a file."""
    chunks = await get_chunks_by_file_id(db, file_id)
    count = len(chunks)
    for chunk in chunks:
        await db.delete(chunk)
    await db.commit()
    return count


async def delete_chunk(db: AsyncSession, chunk_id: str) -> bool:
    """Delete a single chunk by ID."""
    chunk = await get_chunk_by_id(db, chunk_id)
    if chunk:
        await db.delete(chunk)
        await db.commit()
        return True
    return False
