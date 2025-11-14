"""
RAG Service - Orchestrates document processing, embedding, and retrieval.
Handles both text embeddings (Gemini) and visual image embeddings (Vertex AI).
"""
import logging
from typing import List, Dict, Optional, Any
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

    async def retrieve_relevant_context(
        self,
        db: AsyncSession,
        query: str,
        user_id: str,
        top_k: int = 10,
        file_logger = None,
        question_subdir: Optional[str] = None
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
            file_logger: Optional FileLogger instance for logging RAG images
            question_subdir: Optional subdirectory name for per-question logging (e.g., "question_0")

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

            # Log text collection search results
            if file_logger:
                text_search_summary = {
                    "search_type": "text_collection",
                    "results_count": len(text_results),
                    "chunk_ids": [r["chunk_id"] for r in text_results],
                    "similarities": [r["similarity"] for r in text_results]
                }
                file_logger.log_rag_response({"text_search_results": text_search_summary}, subdir=question_subdir)

            # Search image collection (visual image search)
            image_results = await self.image_embedding_service.search_images(
                query_text=query,
                user_id=user_id,
                top_k=max(5, top_k // 2)  # Get fewer images since they're more expensive
            )

            # Log image collection search results
            if file_logger:
                image_search_summary = {
                    "search_type": "image_collection",
                    "results_count": len(image_results),
                    "chunk_ids": [r["chunk_id"] for r in image_results],
                    "similarities": [r["similarity"] for r in image_results]
                }
                file_logger.log_rag_response({"image_search_results": image_search_summary}, subdir=question_subdir)

            # Collect all unique chunk IDs from both searches
            text_chunk_ids = [r["chunk_id"] for r in text_results]
            image_chunk_ids = [r["chunk_id"] for r in image_results]
            all_chunk_ids = list(set(text_chunk_ids + image_chunk_ids))

            logger.info(
                f"Collected {len(all_chunk_ids)} unique chunk IDs from search results "
                f"(text: {len(text_chunk_ids)}, image: {len(image_chunk_ids)})"
            )

            # Fetch full chunk data from database
            from ..db.crud import document_chunks_crud
            chunks = await document_chunks_crud.get_chunks_by_ids(db, all_chunk_ids)

            logger.info(f"Fetched {len(chunks)} chunks from database for {len(all_chunk_ids)} IDs")

            # Create similarity maps from both searches
            text_similarity_map = {r["chunk_id"]: r["similarity"] for r in text_results}
            image_similarity_map = {r["chunk_id"]: r["similarity"] for r in image_results}

            # Separate by type and merge similarities
            text_chunks = []
            image_chunks = []

            file_cache: Dict[str, Optional[Any]] = {}

            for chunk in chunks:
                # Normalize file_id to a string key for caching
                raw_file_id = getattr(chunk, "file_id", None)
                file_id = str(raw_file_id) if raw_file_id is not None else ""
                if not file_id:
                    filename = "unknown file"
                    file = None
                else:
                    if file_id not in file_cache:
                        file_cache[file_id] = await files_crud.get_file_by_id(db, file_id)

                    file = file_cache[file_id]
                    filename = file.filename if file and getattr(file, "filename", None) else f"file:{file_id}"

                chunk_type_str = chunk.chunk_type.value if hasattr(chunk.chunk_type, 'value') else str(chunk.chunk_type)

                logger.info(f"Processing chunk {chunk.id}: type={chunk_type_str}, file={filename}")

                # Use max similarity from either search
                text_sim = text_similarity_map.get(chunk.id, 0.0)
                img_sim = image_similarity_map.get(chunk.id, 0.0)
                combined_similarity = max(text_sim, img_sim)

                # Safely get metadata
                metadata = chunk.metadata_json if chunk.metadata_json else {}
                page_num = metadata.get('page', '?')

                if chunk_type_str == "text":
                    text_chunks.append({
                        "content": chunk.content,
                        "source": f"{filename} (page {page_num})",
                        "file_id": file_id,
                        "similarity": combined_similarity
                    })
                elif chunk_type_str == "image":
                    # Save RAG image if file_logger enabled
                    if file_logger and chunk.raw_content:
                        file_logger.save_rag_image(
                            chunk.raw_content,
                            source_name=filename,
                            index=len(image_chunks),
                            subdir=question_subdir
                        )

                    image_chunks.append({
                        "image_bytes": chunk.raw_content,
                        "description": chunk.content,  # OCR text
                        "source": f"{filename} (page {page_num})",
                        "file_id": file_id,
                        "similarity": combined_similarity,
                        "visual_match": img_sim > 0,  # Flag if found by visual search
                    })
                else:
                    logger.warning(
                        f"Chunk {chunk.id} has unknown type '{chunk_type_str}' (expected 'text' or 'image'), skipping"
                    )

            # Sort by similarity (descending)
            text_chunks.sort(key=lambda x: x["similarity"], reverse=True)
            image_chunks.sort(key=lambda x: x["similarity"], reverse=True)

            logger.info(
                f"Retrieved {len(text_chunks)} text chunks and {len(image_chunks)} image chunks "
                f"(text search: {len(text_results)}, visual search: {len(image_results)})"
            )

            # Log final chunk breakdown
            if file_logger:
                final_summary = {
                    "final_retrieval": {
                        "text_chunks_count": len(text_chunks),
                        "image_chunks_count": len(image_chunks),
                        "total_db_chunks_fetched": len(chunks),
                        "unique_search_chunk_ids": len(all_chunk_ids)
                    }
                }
                file_logger.log_rag_response(final_summary, subdir=question_subdir)

            return {
                "text_chunks": text_chunks,
                "image_chunks": image_chunks
            }

        except Exception as e:
            logger.error(
                f"Context retrieval failed with exception: {type(e).__name__}: {e}",
                exc_info=True
            )
            # Log the error to file logger if available
            if file_logger and question_subdir:
                file_logger.log_rag_response(
                    {"error": f"{type(e).__name__}: {str(e)}"},
                    subdir=question_subdir
                )
            return {"text_chunks": [], "image_chunks": []}


# Singleton instance
_rag_service = None

def get_rag_service() -> RAGService:
    """Get or create singleton RAGService."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
