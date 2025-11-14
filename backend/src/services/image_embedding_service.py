"""
Service for generating multimodal image embeddings using Vertex AI.
Handles visual image embeddings separate from text embeddings.
"""
import base64
import io
import logging
import asyncio
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from PIL import Image

from ..config import settings as app_settings

logger = logging.getLogger(__name__)

# Lazy import Vertex AI (only if configured)
_vertexai = None
_MultiModalEmbeddingModel = None
_ImageBytesInput = None

def _get_vertex_ai():
    """Lazy load Vertex AI modules."""
    global _vertexai, _MultiModalEmbeddingModel, _ImageBytesInput
    if _vertexai is None:
        try:
            import vertexai
            from vertexai.vision_models import MultiModalEmbeddingModel, Image as VertexImage
            _vertexai = vertexai
            _MultiModalEmbeddingModel = MultiModalEmbeddingModel
            _ImageBytesInput = VertexImage

            # Initialize Vertex AI
            if app_settings.VERTEX_AI_PROJECT:
                _vertexai.init(
                    project=app_settings.VERTEX_AI_PROJECT,
                    location=app_settings.VERTEX_AI_LOCATION
                )
                logger.info(
                    f"Vertex AI initialized: project={app_settings.VERTEX_AI_PROJECT}, "
                    f"location={app_settings.VERTEX_AI_LOCATION}"
                )
            else:
                logger.warning("VERTEX_AI_PROJECT not configured, image embeddings will be disabled")
                _vertexai = False
                _MultiModalEmbeddingModel = False
                _ImageBytesInput = False
        except ImportError as e:
            logger.warning(f"google-cloud-aiplatform not installed: {e}")
            _vertexai = False
            _MultiModalEmbeddingModel = False
            _ImageBytesInput = False
    return _vertexai, _MultiModalEmbeddingModel, _ImageBytesInput


class ImageEmbeddingService:
    """Manage multimodal image embeddings and ChromaDB vector store for images."""

    def __init__(self):
        """Initialize ChromaDB client and image embedding model."""
        logger.info("Initializing ImageEmbeddingService for multimodal embeddings")

        # Initialize ChromaDB client
        self.chroma_client = chromadb.HttpClient(
            host=app_settings.CHROMA_HOST,
            port=app_settings.CHROMA_PORT,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False
            ),
            ssl=True
        )

        # Get or create IMAGE collection (for visual embeddings)
        self.image_collection = self.chroma_client.get_or_create_collection(
            name=app_settings.CHROMA_IMAGE_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        logger.info(
            f"ChromaDB image collection '{app_settings.CHROMA_IMAGE_COLLECTION_NAME}' initialized with "
            f"{self.image_collection.count()} existing images"
        )
        logger.info(
            f"Using image embedding model: {app_settings.IMAGE_EMBEDDING_MODEL} "
            f"with {app_settings.IMAGE_EMBEDDING_DIMENSIONS} dimensions"
        )

        # Initialize Vertex AI model
        vertexai_module, model_class, _ = _get_vertex_ai()
        self.vertex_available = bool(vertexai_module and app_settings.VERTEX_AI_PROJECT)

        if self.vertex_available:
            try:
                self.model = model_class.from_pretrained(app_settings.IMAGE_EMBEDDING_MODEL)
                logger.info(f"Multimodal embedding model loaded: {app_settings.IMAGE_EMBEDDING_MODEL}")
            except Exception as e:
                logger.error(f"Failed to load multimodal model: {e}")
                self.vertex_available = False
                self.model = None
        else:
            self.model = None
            logger.warning("Vertex AI not available, image embeddings disabled")

    async def embed_image(self, image_bytes: bytes) -> Optional[List[float]]:
        """
        Generate embedding for image using Vertex AI multimodalembedding@001.

        Args:
            image_bytes: Raw image bytes

        Returns:
            Embedding vector (1408 dimensions) or None if disabled
        """
        if not self.vertex_available or not self.model:
            logger.warning("Image embedding skipped: Vertex AI not available")
            return None

        try:
            _, _, ImageBytesInput = _get_vertex_ai()

            # Create image input from bytes
            image = ImageBytesInput(image_bytes=image_bytes)

            # Generate embedding (run in thread as it's CPU/GPU intensive and blocking)
            embeddings = await asyncio.to_thread(
                self.model.get_embeddings,
                image=image,
                dimension=app_settings.IMAGE_EMBEDDING_DIMENSIONS
            )

            return embeddings.image_embedding

        except Exception as e:
            logger.error(f"Image embedding failed: {e}", exc_info=True)
            return None

    async def add_image_chunks(self, chunks: List[Dict]) -> int:
        """
        Add image chunks to ChromaDB using visual embeddings.

        Args:
            chunks: List of chunk dicts with keys: id, raw_content (image bytes), content (OCR), metadata_json, user_id

        Returns:
            Number of chunks added
        """
        if not chunks:
            return 0

        if not self.vertex_available:
            logger.warning("Image embedding disabled, skipping image chunks")
            return 0

        try:
            embeddings = []
            documents = []
            metadatas = []
            ids = []

            for chunk in chunks:
                # Only process image chunks
                chunk_type = chunk.get("chunk_type")
                if hasattr(chunk_type, 'value'):
                    chunk_type_str = chunk_type.value
                else:
                    chunk_type_str = str(chunk_type)

                if chunk_type_str != "image":
                    continue

                # Get image bytes
                image_bytes = chunk.get("raw_content")
                if not image_bytes:
                    logger.warning(f"Image chunk {chunk['id']} has no raw_content")
                    continue

                # Generate visual embedding
                embedding = await self.embed_image(image_bytes)
                if embedding is None:
                    logger.warning(f"Failed to embed image chunk {chunk['id']}")
                    continue

                embeddings.append(embedding)
                documents.append(chunk.get("content", ""))  # Store OCR text for reference

                # Store metadata
                metadata_json = chunk.get("metadata_json", {}) or {}
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

                ids.append(chunk["id"])

            if not embeddings:
                logger.warning("No valid image embeddings generated")
                return 0

            # Batch add to ChromaDB (run in thread as it's blocking I/O)
            await asyncio.to_thread(
                self.image_collection.add,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )

            logger.info(f"Added {len(embeddings)} image chunks to ChromaDB with visual embeddings")
            return len(embeddings)

        except Exception as e:
            logger.error(f"Failed to add image chunks to ChromaDB: {e}", exc_info=True)
            raise

    async def search_images(
        self,
        query_text: str,
        user_id: str,
        top_k: int = 5,
        file_ids: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Search for images using text query (via multimodal embeddings).

        Args:
            query_text: Search query
            user_id: User ID for filtering
            top_k: Number of results to return
            file_ids: Optional list of file IDs to filter by

        Returns:
            List of matching image chunks with metadata and similarity scores
        """
        if not self.vertex_available or not self.model:
            logger.warning("Image search skipped: Vertex AI not available")
            return []

        try:
            # Generate text query embedding using multimodal model (run in thread as it's blocking)
            embeddings = await asyncio.to_thread(
                self.model.get_embeddings,
                contextual_text=query_text,
                dimension=app_settings.IMAGE_EMBEDDING_DIMENSIONS
            )
            query_embedding = embeddings.text_embedding

            # Build where filter with $and operator for multiple conditions
            where_conditions = [
                {"user_id": user_id},
                {"chunk_type": "image"}
            ]
            if file_ids:
                where_conditions.append({"file_id": {"$in": file_ids}})

            where_filter = {"$and": where_conditions}

            # Query ChromaDB (run in thread as it's blocking I/O)
            results = await asyncio.to_thread(
                self.image_collection.query,
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
                        "ocr_text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "similarity": 1 - results["distances"][0][i],
                    })

            logger.info(f"Image search for '{query_text[:50]}...' returned {len(chunks)} results")
            return chunks

        except Exception as e:
            logger.error(f"Image search failed: {e}", exc_info=True)
            return []

    async def delete_file_images(self, file_id: str) -> bool:
        """
        Delete all image chunks for a file from ChromaDB.

        Args:
            file_id: File ID

        Returns:
            Success status
        """
        try:
            # Delete image chunks (run in thread as it's blocking I/O)
            await asyncio.to_thread(
                self.image_collection.delete,
                where={"file_id": file_id}
            )
            logger.info(f"Deleted image chunks for file {file_id} from ChromaDB")
            return True

        except Exception as e:
            logger.error(f"Failed to delete image chunks: {e}", exc_info=True)
            return False


# Singleton instance
_image_embedding_service = None

def get_image_embedding_service() -> ImageEmbeddingService:
    """Get or create singleton ImageEmbeddingService."""
    global _image_embedding_service
    if _image_embedding_service is None:
        _image_embedding_service = ImageEmbeddingService()
    return _image_embedding_service
