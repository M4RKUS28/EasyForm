"""
RAG Service - Orchestrates document processing, embedding, and retrieval.
Handles both text embeddings (Gemini) and visual image embeddings (Vertex AI).
"""
import logging
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.crud import files_crud
from .document_processing_service import get_document_processing_service
from .embedding_service import get_embedding_service
from .image_embedding_service import get_image_embedding_service

logger = logging.getLogger(__name__)

# Thresholds for RAG vs. direct context
MAX_DIRECT_CONTEXT_SIZE = 50000  # 50K chars
MAX_DIRECT_FILE_COUNT = 5
MAX_DIRECT_FILE_PAGES = 10


class RAGService:
    """Orchestrate RAG pipeline: processing, embedding, and retrieval."""

    def __init__(self):
        """Initialize RAG service."""
        self.doc_processor = get_document_processing_service()
        self.text_embedding_service = get_embedding_service()
        self.image_embedding_service = get_image_embedding_service()

        # Keep legacy reference for backward compatibility
        self.embedding_service = self.text_embedding_service

        logger.info("RAGService initialized with text and image embedding services")

    async def process_and_index_file(
        self,
        db: AsyncSession,
        file_id: str,
        user_id: str
    ) -> bool:
        """
        Process a file and index it in both text and image collections.

        Args:
            db: Database session
            file_id: File ID to process
            user_id: User ID for ownership

        Returns:
            Success status
        """
        try:
            logger.info(f"Starting RAG processing for file {file_id}")

            # Get file from database
            file = await files_crud.get_file_by_id(db, file_id)
            if not file:
                logger.error(f"File {file_id} not found")
                return False

            # Update status
            await files_crud.update_file_status(db, file_id, "processing")

            # Process based on content type
            chunks = []
            page_count = None

            if file.content_type == "application/pdf":
                chunks, page_count = await self.doc_processor.process_pdf(
                    file_id=file_id,
                    user_id=user_id,
                    pdf_bytes=file.data
                )
            elif file.content_type.startswith("image/"):
                chunks = await self.doc_processor.process_image(
                    file_id=file_id,
                    user_id=user_id,
                    image_bytes=file.data,
                    content_type=file.content_type
                )
            else:
                logger.warning(f"Unsupported content type: {file.content_type}")
                await files_crud.update_file_status(db, file_id, "completed")
                return False

            # Store chunks in database
            from ..db.crud import document_chunks_crud
            await document_chunks_crud.create_chunks(db, chunks)

            # Generate text embeddings (OCR for images) and add to text collection
            text_chunks_added = await self.text_embedding_service.add_chunks(chunks)

            # Generate visual image embeddings and add to image collection
            image_chunks_added = await self.image_embedding_service.add_image_chunks(chunks)

            # Update file metadata
            if page_count:
                await files_crud.update_file_page_count(db, file_id, page_count)
            await files_crud.update_file_status(db, file_id, "completed")

            logger.info(
                f"Successfully processed file {file_id}: "
                f"{text_chunks_added} chunks in text collection, "
                f"{image_chunks_added} chunks in image collection"
            )
            return True

        except Exception as e:
            logger.error(f"Error processing file {file_id}: {e}", exc_info=True)
            await files_crud.update_file_status(db, file_id, "failed")
            return False

    async def should_use_rag(self, db: AsyncSession, user_id: str) -> bool:
        """
        Decide whether to use RAG or direct context injection.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            True if RAG should be used
        """
        user_files = await files_crud.get_user_files(db, user_id)

        if not user_files:
            return False

        # Calculate total size and check thresholds
        total_size = 0
        for file in user_files:
            if file.content_type == "application/pdf":
                # Estimate: 1 page ≈ 2000 chars
                estimated_size = (file.page_count or 1) * 2000
                total_size += estimated_size

                # Large file threshold
                if file.page_count and file.page_count > MAX_DIRECT_FILE_PAGES:
                    logger.info(f"Using RAG: file {file.id} has {file.page_count} pages")
                    return True
            else:
                total_size += file.file_size

        # Too many files
        if len(user_files) > MAX_DIRECT_FILE_COUNT:
            logger.info(f"Using RAG: {len(user_files)} files exceeds threshold")
            return True

        # Too much total content
        if total_size > MAX_DIRECT_CONTEXT_SIZE:
            logger.info(f"Using RAG: total size {total_size} exceeds threshold")
            return True

        logger.info(f"Using direct context: {len(user_files)} files, {total_size} chars")
        return False

    async def retrieve_relevant_context(
        self,
        db: AsyncSession,
        query: str,
        user_id: str,
        top_k: int = 10
    ) -> Dict[str, List]:
        """
        Retrieve relevant text and image chunks for a query using dual retrieval.

        Searches both:
        1. Text collection (text chunks + OCR from images)
        2. Image collection (visual image embeddings)

        Args:
            db: Database session
            query: Search query (e.g., form field labels)
            user_id: User ID for filtering
            top_k: Number of chunks to retrieve

        Returns:
            Dict with 'text_chunks' and 'image_chunks' lists
        """
        try:
            # Search text collection (text chunks + OCR)
            text_results = await self.text_embedding_service.search(
                query_text=query,
                user_id=user_id,
                top_k=top_k
            )

            # Search image collection (visual image search)
            image_results = await self.image_embedding_service.search_images(
                query_text=query,
                user_id=user_id,
                top_k=max(5, top_k // 2)  # Get fewer images since they're more expensive
            )

            # Collect all unique chunk IDs from both searches
            text_chunk_ids = [r["chunk_id"] for r in text_results]
            image_chunk_ids = [r["chunk_id"] for r in image_results]
            all_chunk_ids = list(set(text_chunk_ids + image_chunk_ids))

            # Fetch full chunk data from database
            from ..db.crud import document_chunks_crud
            chunks = await document_chunks_crud.get_chunks_by_ids(db, all_chunk_ids)

            # Create similarity maps from both searches
            text_similarity_map = {r["chunk_id"]: r["similarity"] for r in text_results}
            image_similarity_map = {r["chunk_id"]: r["similarity"] for r in image_results}

            # Separate by type and merge similarities
            text_chunks = []
            image_chunks = []

            for chunk in chunks:
                # Get file info for source attribution
                file = await files_crud.get_file_by_id(db, chunk.file_id)

                chunk_type_str = chunk.chunk_type.value if hasattr(chunk.chunk_type, 'value') else str(chunk.chunk_type)

                # Use max similarity from either search
                text_sim = text_similarity_map.get(chunk.id, 0.0)
                img_sim = image_similarity_map.get(chunk.id, 0.0)
                combined_similarity = max(text_sim, img_sim)

                if chunk_type_str == "text":
                    text_chunks.append({
                        "content": chunk.content,
                        "source": f"{file.filename} (page {chunk.metadata_json.get('page', '?')})",
                        "file_id": chunk.file_id,
                        "similarity": combined_similarity
                    })
                elif chunk_type_str == "image":
                    image_chunks.append({
                        "image_bytes": chunk.raw_content,
                        "description": chunk.content,  # OCR text
                        "source": f"{file.filename} (page {chunk.metadata_json.get('page', '?')})",
                        "file_id": chunk.file_id,
                        "similarity": combined_similarity,
                        "visual_match": img_sim > 0,  # Flag if found by visual search
                    })

            # Sort by similarity (descending)
            text_chunks.sort(key=lambda x: x["similarity"], reverse=True)
            image_chunks.sort(key=lambda x: x["similarity"], reverse=True)

            logger.info(
                f"Retrieved {len(text_chunks)} text chunks and {len(image_chunks)} image chunks "
                f"(text search: {len(text_results)}, visual search: {len(image_results)})"
            )
            return {
                "text_chunks": text_chunks,
                "image_chunks": image_chunks
            }

        except Exception as e:
            logger.error(f"Context retrieval failed: {e}", exc_info=True)
            return {"text_chunks": [], "image_chunks": []}


# Singleton instance
_rag_service = None

def get_rag_service() -> RAGService:
    """Get or create singleton RAGService."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
