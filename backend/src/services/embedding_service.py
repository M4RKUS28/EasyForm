"""
Service for generating text embeddings and managing ChromaDB text vector store.
Uses Gemini embedding model for text chunks and OCR text from images.
"""
import logging
import asyncio
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
import google.generativeai as genai

from ..config import settings as app_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Manage text embeddings and ChromaDB vector store for text and OCR."""

    def __init__(self):
        """Initialize ChromaDB client and text embedding functions."""
        logger.info("Initializing EmbeddingService for text embeddings")

        # Initialize ChromaDB client
        self.chroma_client = chromadb.HttpClient(
            host=app_settings.CHROMA_HOST,
            port=app_settings.CHROMA_PORT,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False  # Safety: Don't allow reset in production
            ),
            ssl=True
        )

        # Get or create TEXT collection (for text chunks and OCR)
        self.text_collection = self.chroma_client.get_or_create_collection(
            name=app_settings.CHROMA_TEXT_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            f"ChromaDB text collection '{app_settings.CHROMA_TEXT_COLLECTION_NAME}' initialized with "
            f"{self.text_collection.count()} existing documents"
        )
        logger.info(
            f"Using text embedding model: {app_settings.TEXT_EMBEDDING_MODEL} "
            f"with {app_settings.TEXT_EMBEDDING_DIMENSIONS} dimensions"
        )

        # Keep legacy reference for backward compatibility
        self.collection = self.text_collection

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text using Google's gemini-embedding-001.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (configured dimensions, default 3072)
        """
        try:
            result = genai.embed_content(
                model=app_settings.TEXT_EMBEDDING_MODEL,
                content=text,
                task_type="retrieval_document",
                output_dimensionality=app_settings.TEXT_EMBEDDING_DIMENSIONS
            )
            return result['embedding']

        except Exception as e:
            logger.error(f"Text embedding failed: {e}", exc_info=True)
            raise

    async def embed_ocr_text(self, caption: Optional[str] = None) -> List[float]:
        """
        Generate text embedding for OCR caption from image.

        This embeds the OCR text (not the visual image) in the text collection
        for text-based search of image content.

        Args:
            caption: Text caption from OCR

        Returns:
            Embedding vector (configured dimensions, default 3072)
        """
        try:
            # Use OCR text caption for embedding
            if caption and caption.strip():
                return await self.embed_text(caption)
            else:
                # If no caption, create a generic image marker
                logger.warning("Image has no OCR caption, using generic marker")
                return await self.embed_text("[Image content]")

        except Exception as e:
            logger.error(f"OCR text embedding failed: {e}", exc_info=True)
            raise

    async def add_chunks(self, chunks: List[Dict]) -> int:
        """
        Add document chunks to ChromaDB text collection.

        Args:
            chunks: List of chunk dicts with keys: id, content, chunk_type, metadata_json, user_id

        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0

        try:
            embeddings = []
            documents = []
            metadatas = []
            ids = []

            for chunk in chunks:
                # Generate embedding based on type
                chunk_type = chunk["chunk_type"]
                if hasattr(chunk_type, 'value'):
                    chunk_type_str = chunk_type.value
                else:
                    chunk_type_str = str(chunk_type)

                if chunk_type_str == "text":
                    embedding = await self.embed_text(chunk["content"])
                elif chunk_type_str == "image":
                    # Embed OCR text in text collection
                    embedding = await self.embed_ocr_text(caption=chunk.get("content"))
                else:
                    logger.warning(f"Unknown chunk type: {chunk_type}")
                    continue

                embeddings.append(embedding)
                documents.append(chunk.get("content", ""))  # Store text for retrieval

                # Store metadata for filtering (prune unsupported/null values)
                metadata_json = chunk.get("metadata_json", {}) or {}

                # Filter out values that Chroma's metadata schema can't serialize
                filtered_metadata = {}
                for key, value in metadata_json.items():
                    if value is None:
                        continue
                    if isinstance(value, (str, int, float, bool)):
                        filtered_metadata[key] = value
                    elif isinstance(value, (list, tuple)):
                        filtered_metadata[key] = [
                            item for item in value
                            if isinstance(item, (str, int, float, bool))
                        ]
                        if not filtered_metadata[key]:
                            filtered_metadata.pop(key)
                    else:
                        filtered_metadata[key] = str(value)

                metadatas.append({
                    "user_id": chunk["user_id"],
                    "file_id": chunk["file_id"],
                    "chunk_id": chunk["id"],
                    "chunk_type": chunk_type_str,
                    **filtered_metadata
                })

                ids.append(chunk["id"])  # Use chunk ID as Chroma ID

            # Batch add to ChromaDB text collection (run in thread as it's blocking I/O)
            await asyncio.to_thread(
                self.text_collection.add,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

            logger.info(f"Added {len(chunks)} chunks to ChromaDB text collection")
            return len(chunks)

        except Exception as e:
            logger.error(f"Failed to add chunks to ChromaDB: {e}", exc_info=True)
            raise

    async def search(
        self,
        query_text: str,
        user_id: str,
        top_k: int = 10,
        file_ids: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search for relevant chunks using semantic similarity in text collection.

        Args:
            query_text: Search query
            user_id: User ID for filtering
            top_k: Number of results to return
            file_ids: Optional list of file IDs to filter by

        Returns:
            List of matching chunks with metadata and similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = await self.embed_text(query_text)

            # Build where filter for user isolation
            if file_ids:
                # Multiple conditions require $and operator
                where_filter = {
                    "$and": [
                        {"user_id": user_id},
                        {"file_id": {"$in": file_ids}}
                    ]
                }
            else:
                # Single condition can be used directly
                where_filter = {"user_id": user_id}

            # Query ChromaDB text collection (run in thread as it's blocking I/O)
            results = await asyncio.to_thread(
                self.text_collection.query,
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
                include=["metadatas", "documents", "distances"]
            )

            # Format results
            chunks = []
            if results and results["ids"]:
                for i, chunk_id in enumerate(results["ids"][0]):
                    chunks.append({
                        "chunk_id": chunk_id,
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity": 1 - results["distances"][0][i],  # Convert distance to similarity
                    })

            logger.info(f"Text search for '{query_text[:50]}...' returned {len(chunks)} results")
            return chunks

        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return []

    async def delete_file_chunks(self, file_id: str) -> bool:
        """
        Delete all chunks for a file from ChromaDB text collection.

        Args:
            file_id: File ID

        Returns:
            Success status
        """
        try:
            # Delete by file_id metadata (run in thread as it's blocking I/O)
            await asyncio.to_thread(
                self.text_collection.delete,
                where={"file_id": file_id}
            )
            logger.info(f"Deleted text chunks for file {file_id} from ChromaDB")
            return True

        except Exception as e:
            logger.error(f"Failed to delete chunks: {e}", exc_info=True)
            return False


# Singleton instance
_embedding_service = None

def get_embedding_service() -> EmbeddingService:
    """Get or create singleton EmbeddingService."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
