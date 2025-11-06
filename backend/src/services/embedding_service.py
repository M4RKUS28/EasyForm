"""
Service for generating embeddings and managing ChromaDB vector store.
"""
import logging
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
import google.generativeai as genai

from ..config import settings as app_settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Manage embeddings and ChromaDB vector store."""

    def __init__(self):
        """Initialize ChromaDB client and embedding functions."""
        logger.info("Initializing EmbeddingService with ChromaDB")

        # Initialize ChromaDB client
        self.chroma_client = chromadb.HttpClient(
            host=app_settings.CHROMA_HOST,
            port=app_settings.CHROMA_PORT,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False  # Safety: Don't allow reset in production
            )
        )

        # Get or create collection
        # Note: Using cosine similarity for embeddings
        self.collection = self.chroma_client.get_or_create_collection(
            name="easyform_documents",
            metadata={"hnsw:space": "cosine"},  # Cosine similarity
        )

        logger.info(f"ChromaDB collection 'easyform_documents' initialized with {self.collection.count()} existing documents")

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for text using Google's text-embedding-004.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (768 dimensions)
        """
        try:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']

        except Exception as e:
            logger.error(f"Text embedding failed: {e}", exc_info=True)
            raise

    async def embed_image(self, image_bytes: bytes, caption: Optional[str] = None) -> List[float]:
        """
        Generate embedding for image using Google's multimodal embedding.

        For now, we'll use the OCR text caption. In the future, this can be
        upgraded to use true multimodal embeddings.

        Args:
            image_bytes: Image bytes
            caption: Optional text caption (OCR text)

        Returns:
            Embedding vector (768 dimensions)
        """
        try:
            # For now, use OCR text if available
            if caption:
                return await self.embed_text(caption)
            else:
                # Return zero vector or skip
                logger.warning("Image embedding without caption not yet implemented")
                return [0.0] * 768  # Match text embedding dimensions

        except Exception as e:
            logger.error(f"Image embedding failed: {e}", exc_info=True)
            raise

    async def add_chunks(self, chunks: List[Dict]) -> int:
        """
        Add document chunks to ChromaDB.

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
                    embedding = await self.embed_image(
                        chunk["raw_content"],
                        caption=chunk.get("content")
                    )
                else:
                    logger.warning(f"Unknown chunk type: {chunk_type}")
                    continue

                embeddings.append(embedding)
                documents.append(chunk.get("content", ""))  # Store text for retrieval

                # Store metadata for filtering
                metadatas.append({
                    "user_id": chunk["user_id"],
                    "file_id": chunk["file_id"],
                    "chunk_id": chunk["id"],
                    "chunk_type": chunk_type_str,
                    "page": chunk.get("metadata_json", {}).get("page"),
                    **chunk.get("metadata_json", {})
                })

                ids.append(chunk["id"])  # Use chunk ID as Chroma ID

            # Batch add to ChromaDB
            self.collection.add(
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

            logger.info(f"Added {len(chunks)} chunks to ChromaDB")
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
        Search for relevant chunks using semantic similarity.

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
            where_filter = {"user_id": user_id}
            if file_ids:
                where_filter["file_id"] = {"$in": file_ids}

            # Query ChromaDB
            results = self.collection.query(
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

            logger.info(f"Search for '{query_text[:50]}...' returned {len(chunks)} results")
            return chunks

        except Exception as e:
            logger.error(f"Search failed: {e}", exc_info=True)
            return []

    async def delete_file_chunks(self, file_id: str) -> bool:
        """
        Delete all chunks for a file from ChromaDB.

        Args:
            file_id: File ID

        Returns:
            Success status
        """
        try:
            # Delete by file_id metadata
            self.collection.delete(
                where={"file_id": file_id}
            )
            logger.info(f"Deleted chunks for file {file_id} from ChromaDB")
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
