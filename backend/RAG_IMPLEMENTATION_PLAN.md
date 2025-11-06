# RAG Implementation Plan for EasyForm Backend

**Date:** 2025-11-07
**Objective:** Implement Retrieval-Augmented Generation (RAG) using ChromaDB and Google's multimodal embeddings to improve form-filling context retrieval.

---

## Architecture Overview

### Current Flow
```
File Upload → Store in DB (BLOB) → Form Analysis → Pass ALL files to Agent → Generate values
```

### New RAG Flow
```
File Upload → Store in DB → Background: Process & Chunk → Embed & Store in Chroma
                                                                ↓
Form Analysis → Build query from fields → Retrieve top-K relevant chunks → Pass to Agent → Generate values
```

### Key Design Decisions
1. **Storage Strategy:** Hybrid - Keep files table, add document_chunks table
2. **Collection Strategy:** Single shared collection with user_id metadata filtering
3. **Processing Strategy:** Asynchronous background processing after upload
4. **Retrieval Strategy:** Smart - Use RAG if >5 files OR >50K chars OR any file >10 pages
5. **Embedding Models:**
   - Text: `text-embedding-004` (768 dimensions)
   - Images: `multimodalembedding@001` (1408 dimensions)

---

## Phase 1: Database Schema & Models

### 1.1 Create Document Chunks Model

**File:** `backend/src/db/models/db_document_chunk.py`

```python
"""
Database model for document chunks extracted from files.
Used for RAG (Retrieval-Augmented Generation) context storage.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, JSON, LargeBinary, Enum
from sqlalchemy.orm import relationship
from ..database import Base
import enum


class ChunkType(str, enum.Enum):
    """Types of content chunks"""
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"


class DocumentChunk(Base):
    """Model for storing processed document chunks for RAG retrieval."""

    __tablename__ = "document_chunks"

    id = Column(String(50), primary_key=True, index=True)  # UUID
    file_id = Column(String(50), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    chunk_index = Column(Integer, nullable=False)  # Order within document (0, 1, 2...)
    chunk_type = Column(Enum(ChunkType), nullable=False, default=ChunkType.TEXT)

    # Extracted content
    content = Column(Text, nullable=True)  # Text content or OCR result
    raw_content = Column(LargeBinary, nullable=True)  # For images (optional, can reference file)

    # Metadata for traceability
    metadata_json = Column(JSON, nullable=True)  # {page: 5, bbox: [...], etc.}

    # Chroma reference
    chroma_id = Column(String(255), nullable=True, index=True)  # ID in Chroma DB

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    # file = relationship("File", back_populates="chunks")
```

**Pattern:** Follows existing model pattern (db_file.py, db_form_request.py)

### 1.2 Update File Model

**File:** `backend/src/db/models/db_file.py`

**Add:**
```python
page_count = Column(Integer, nullable=True)  # For PDFs, calculated during processing
processing_status = Column(String(50), nullable=True, default="pending")  # pending, processing, completed, failed
```

**Update imports in:** `backend/src/db/models/__init__.py`
```python
from .db_document_chunk import DocumentChunk, ChunkType
```

### 1.3 Update Database Initialization

**File:** `backend/src/core/lifespan.py`

No changes needed - `Base.metadata.create_all` will auto-create new tables.

---

## Phase 2: Install Dependencies

### 2.1 Update requirements.txt

**File:** `backend/requirements.txt`

**Add:**
```txt
# RAG & Vector Database
chromadb>=0.4.22
chromadb-client>=0.4.22

# PDF Processing (upgrade from PyPDF2)
pymupdf>=1.23.0  # Better than PyPDF2 for chunking + images
pytesseract>=0.3.10  # OCR for images in PDFs

# Text Processing
tiktoken>=0.5.0  # Token counting for chunking
langchain-text-splitters>=0.0.1  # Optional: Advanced chunking

# Google Embeddings (already have google-adk)
# google-generativeai  # If needed separately
```

### 2.2 Install Tesseract OCR (Windows)

**Manual step:**
```bash
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# Or via chocolatey:
choco install tesseract

# Add to PATH: C:\Program Files\Tesseract-OCR
```

### 2.3 Setup ChromaDB (Docker)

**File:** `backend/docker-compose.yml` (if exists, otherwise create)

**Add service:**
```yaml
version: '3.8'
services:
  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - ./chroma_data:/chroma/chroma
    environment:
      - CHROMA_SERVER_AUTH_PROVIDER=chromadb.auth.token.TokenAuthenticationServerProvider
      - CHROMA_SERVER_AUTH_CREDENTIALS_FILE=/chroma/auth_credentials.txt
      - CHROMA_SERVER_AUTH_CREDENTIALS=easyform_rag_token_2024
    restart: unless-stopped
```

**Or standalone Docker:**
```bash
docker run -d -p 8000:8000 -v $(pwd)/chroma_data:/chroma/chroma chromadb/chroma
```

---

## Phase 3: Core RAG Services

### 3.1 Document Processing Service

**File:** `backend/src/services/document_processing_service.py`

```python
"""
Service for processing uploaded documents into chunks for RAG.
Handles PDFs and images with text extraction, OCR, and chunking.
"""
import asyncio
import base64
import io
import logging
import uuid
from typing import List, Dict, Optional, Tuple
from PIL import Image
import fitz  # PyMuPDF
import pytesseract

from ..db.models.db_document_chunk import ChunkType

logger = logging.getLogger(__name__)

# Chunking configuration
CHUNK_SIZE_TOKENS = 1000
CHUNK_OVERLAP_TOKENS = 200
MAX_IMAGE_SIZE = (1024, 1024)  # Resize images for embedding


class DocumentProcessingService:
    """Process documents into chunks for RAG retrieval."""

    def __init__(self):
        """Initialize document processor."""
        logger.info("DocumentProcessingService initialized")

    async def process_pdf(
        self,
        file_id: str,
        user_id: str,
        pdf_bytes: bytes
    ) -> Tuple[List[Dict], int]:
        """
        Process PDF into text and image chunks.

        Args:
            file_id: File ID from database
            user_id: User ID for ownership
            pdf_bytes: Raw PDF bytes

        Returns:
            Tuple of (chunks list, page_count)
        """
        chunks = []

        try:
            # Open PDF with PyMuPDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            page_count = len(doc)

            logger.info(f"Processing PDF {file_id}: {page_count} pages")

            chunk_index = 0

            for page_num in range(page_count):
                page = doc[page_num]

                # Extract text
                text = page.get_text("text")
                if text.strip():
                    # Chunk text with overlap
                    text_chunks = self._chunk_text(text, CHUNK_SIZE_TOKENS, CHUNK_OVERLAP_TOKENS)

                    for i, chunk_text in enumerate(text_chunks):
                        chunks.append({
                            "id": str(uuid.uuid4()),
                            "file_id": file_id,
                            "user_id": user_id,
                            "chunk_index": chunk_index,
                            "chunk_type": ChunkType.TEXT,
                            "content": chunk_text,
                            "raw_content": None,
                            "metadata_json": {
                                "page": page_num + 1,
                                "chunk_in_page": i,
                                "total_pages": page_count
                            }
                        })
                        chunk_index += 1

                # Extract images
                images = page.get_images()
                for img_index, img in enumerate(images):
                    try:
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        image_bytes = base_image["image"]

                        # OCR the image
                        ocr_text = await self._ocr_image(image_bytes)

                        # Resize image for embedding
                        resized_image = self._resize_image(image_bytes)

                        chunks.append({
                            "id": str(uuid.uuid4()),
                            "file_id": file_id,
                            "user_id": user_id,
                            "chunk_index": chunk_index,
                            "chunk_type": ChunkType.IMAGE,
                            "content": ocr_text,  # OCR text
                            "raw_content": resized_image,  # Resized image bytes
                            "metadata_json": {
                                "page": page_num + 1,
                                "image_index": img_index,
                                "total_pages": page_count,
                                "original_format": base_image.get("ext", "png")
                            }
                        })
                        chunk_index += 1

                    except Exception as e:
                        logger.warning(f"Failed to extract image {img_index} from page {page_num}: {e}")

            doc.close()
            logger.info(f"PDF {file_id} processed: {len(chunks)} chunks extracted")
            return chunks, page_count

        except Exception as e:
            logger.error(f"Error processing PDF {file_id}: {e}", exc_info=True)
            raise

    async def process_image(
        self,
        file_id: str,
        user_id: str,
        image_bytes: bytes,
        content_type: str
    ) -> List[Dict]:
        """
        Process standalone image file.

        Args:
            file_id: File ID from database
            user_id: User ID for ownership
            image_bytes: Raw image bytes
            content_type: MIME type

        Returns:
            List with single chunk
        """
        chunks = []

        try:
            # OCR the image
            ocr_text = await self._ocr_image(image_bytes)

            # Resize image for embedding
            resized_image = self._resize_image(image_bytes)

            chunks.append({
                "id": str(uuid.uuid4()),
                "file_id": file_id,
                "user_id": user_id,
                "chunk_index": 0,
                "chunk_type": ChunkType.IMAGE,
                "content": ocr_text,
                "raw_content": resized_image,
                "metadata_json": {
                    "content_type": content_type,
                    "is_standalone": True
                }
            })

            logger.info(f"Image {file_id} processed: 1 chunk extracted")
            return chunks

        except Exception as e:
            logger.error(f"Error processing image {file_id}: {e}", exc_info=True)
            raise

    def _chunk_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """
        Split text into overlapping chunks by token count.

        Args:
            text: Text to chunk
            chunk_size: Target tokens per chunk
            overlap: Overlap tokens between chunks

        Returns:
            List of text chunks
        """
        # Simple word-based chunking (can upgrade to tiktoken later)
        words = text.split()
        chunks = []

        # Approximate: 1 token ≈ 0.75 words
        words_per_chunk = int(chunk_size * 0.75)
        words_overlap = int(overlap * 0.75)

        start = 0
        while start < len(words):
            end = min(start + words_per_chunk, len(words))
            chunk = " ".join(words[start:end])
            chunks.append(chunk)
            start += (words_per_chunk - words_overlap)

        return chunks if chunks else [text]

    async def _ocr_image(self, image_bytes: bytes) -> Optional[str]:
        """
        Extract text from image using Tesseract OCR.

        Args:
            image_bytes: Raw image bytes

        Returns:
            Extracted text or None
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))

            # Run OCR in thread pool (blocking operation)
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None,
                pytesseract.image_to_string,
                img
            )

            return text.strip() if text.strip() else None

        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return None

    def _resize_image(self, image_bytes: bytes) -> bytes:
        """
        Resize image to max dimensions for embedding.

        Args:
            image_bytes: Original image bytes

        Returns:
            Resized image bytes
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)

            # Convert to bytes
            output = io.BytesIO()
            img.save(output, format="PNG")
            return output.getvalue()

        except Exception as e:
            logger.warning(f"Image resize failed: {e}, returning original")
            return image_bytes


# Singleton instance
_document_processing_service = None

def get_document_processing_service() -> DocumentProcessingService:
    """Get or create singleton DocumentProcessingService."""
    global _document_processing_service
    if _document_processing_service is None:
        _document_processing_service = DocumentProcessingService()
    return _document_processing_service
```

**Pattern:** Follows `agent_service.py` singleton pattern

### 3.2 Embedding Service

**File:** `backend/src/services/embedding_service.py`

```python
"""
Service for generating embeddings and managing ChromaDB vector store.
"""
import logging
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
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

        Args:
            image_bytes: Image bytes
            caption: Optional text caption (OCR text)

        Returns:
            Embedding vector (1408 dimensions)
        """
        try:
            # For multimodal embedding, combine image + text
            import base64
            image_b64 = base64.b64encode(image_bytes).decode()

            # TODO: Implement multimodal embedding via Google API
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
                if chunk["chunk_type"].value == "text":
                    embedding = await self.embed_text(chunk["content"])
                elif chunk["chunk_type"].value == "image":
                    embedding = await self.embed_image(
                        chunk["raw_content"],
                        caption=chunk.get("content")
                    )
                else:
                    logger.warning(f"Unknown chunk type: {chunk['chunk_type']}")
                    continue

                embeddings.append(embedding)
                documents.append(chunk.get("content", ""))  # Store text for retrieval

                # Store metadata for filtering
                metadatas.append({
                    "user_id": chunk["user_id"],
                    "file_id": chunk["file_id"],
                    "chunk_id": chunk["id"],
                    "chunk_type": chunk["chunk_type"].value,
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
```

**Pattern:** Follows `agent_service.py` singleton pattern

### 3.3 RAG Service (Orchestrator)

**File:** `backend/src/services/rag_service.py`

```python
"""
RAG Service - Orchestrates document processing, embedding, and retrieval.
"""
import logging
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.crud import files_crud, document_chunks_crud
from .document_processing_service import get_document_processing_service
from .embedding_service import get_embedding_service

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
        self.embedding_service = get_embedding_service()
        logger.info("RAGService initialized")

    async def process_and_index_file(
        self,
        db: AsyncSession,
        file_id: str,
        user_id: str
    ) -> bool:
        """
        Process a file and index it in ChromaDB.

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
            await document_chunks_crud.create_chunks(db, chunks)

            # Generate embeddings and add to ChromaDB
            await self.embedding_service.add_chunks(chunks)

            # Update file metadata
            if page_count:
                await files_crud.update_file_page_count(db, file_id, page_count)
            await files_crud.update_file_status(db, file_id, "completed")

            logger.info(f"Successfully processed file {file_id}: {len(chunks)} chunks indexed")
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
        Retrieve relevant text and image chunks for a query.

        Args:
            db: Database session
            query: Search query (e.g., form field labels)
            user_id: User ID for filtering
            top_k: Number of chunks to retrieve

        Returns:
            Dict with 'text_chunks' and 'image_chunks' lists
        """
        try:
            # Search in ChromaDB
            results = await self.embedding_service.search(
                query_text=query,
                user_id=user_id,
                top_k=top_k
            )

            # Fetch full chunk data from database
            chunk_ids = [r["chunk_id"] for r in results]
            chunks = await document_chunks_crud.get_chunks_by_ids(db, chunk_ids)

            # Separate by type
            text_chunks = []
            image_chunks = []

            for chunk in chunks:
                # Get file info for source attribution
                file = await files_crud.get_file_by_id(db, chunk.file_id)

                if chunk.chunk_type.value == "text":
                    text_chunks.append({
                        "content": chunk.content,
                        "source": f"{file.filename} (page {chunk.metadata_json.get('page', '?')})",
                        "file_id": chunk.file_id,
                        "similarity": next(r["similarity"] for r in results if r["chunk_id"] == chunk.id)
                    })
                elif chunk.chunk_type.value == "image":
                    image_chunks.append({
                        "image_bytes": chunk.raw_content,
                        "description": chunk.content,  # OCR text
                        "source": f"{file.filename} (page {chunk.metadata_json.get('page', '?')})",
                        "file_id": chunk.file_id,
                        "similarity": next(r["similarity"] for r in results if r["chunk_id"] == chunk.id)
                    })

            logger.info(f"Retrieved {len(text_chunks)} text chunks and {len(image_chunks)} image chunks")
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
```

**Pattern:** Follows `agent_service.py` and `form_service.py` patterns

---

## Phase 4: CRUD Operations

### 4.1 Document Chunks CRUD

**File:** `backend/src/db/crud/document_chunks_crud.py`

```python
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


async def delete_chunks_by_file_id(db: AsyncSession, file_id: str) -> int:
    """Delete all chunks for a file."""
    chunks = await get_chunks_by_file_id(db, file_id)
    count = len(chunks)
    for chunk in chunks:
        await db.delete(chunk)
    await db.commit()
    return count
```

**Pattern:** Follows `files_crud.py` pattern

### 4.2 Update Files CRUD

**File:** `backend/src/db/crud/files_crud.py`

**Add functions:**
```python
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
```

### 4.3 Update CRUD __init__

**File:** `backend/src/db/crud/__init__.py`

**Add:**
```python
from . import document_chunks_crud
```

---

## Phase 5: Integration with Existing Services

### 5.1 Update File Upload Flow

**File:** `backend/src/api/routers/files.py`

**Modify upload endpoint:**
```python
from fastapi import BackgroundTasks
from ...services.rag_service import get_rag_service

@router.post("/upload", response_model=file_schema.FileResponse)
async def upload_file(
    file_upload: file_schema.FileUpload,
    background_tasks: BackgroundTasks,  # Add this
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Upload a file and process it for RAG."""

    # Existing upload logic
    file_response = await file_service.upload_file(
        db=db,
        user_id=current_user.id,
        file_upload=file_upload
    )

    # NEW: Schedule RAG processing in background
    rag_service = get_rag_service()
    background_tasks.add_task(
        rag_service.process_and_index_file,
        db=db,
        file_id=file_response.id,
        user_id=current_user.id
    )

    return file_response
```

**Note:** Background processing means user gets immediate response while file is processed asynchronously.

### 5.2 Update Form Service to Use RAG

**File:** `backend/src/services/form_service.py`

**Modify `analyze_form` function (around line 261):**

```python
# OLD (line 261-276):
# Get user's uploaded files
logger.info("Fetching user files from database...")
user_files = await files_crud.get_user_files(db, user_id)
logger.info("Found %d user files for context", len(user_files))

# NEW:
from .rag_service import get_rag_service

logger.info("Fetching user context...")
rag_service = get_rag_service()

# Decide: RAG or direct?
use_rag = await rag_service.should_use_rag(db, user_id)

if use_rag:
    logger.info("Using RAG for context retrieval")

    # Build search query from field labels
    query = build_search_query_from_fields(normalized_fields)

    # Retrieve relevant chunks
    context = await rag_service.retrieve_relevant_context(
        db=db,
        query=query,
        user_id=user_id,
        top_k=10
    )

    text_context = context["text_chunks"]
    image_context = context["image_chunks"]

    logger.info(f"Retrieved {len(text_context)} text chunks and {len(image_context)} image chunks")
else:
    logger.info("Using direct context (all files)")

    # Fetch all files (current approach)
    user_files = await files_crud.get_user_files(db, user_id)

    # Extract content from all files
    text_context = []
    image_context = []

    for file in user_files:
        if file.content_type == "application/pdf":
            # Get chunks from DB if already processed
            chunks = await document_chunks_crud.get_chunks_by_file_id(db, file.id)
            for chunk in chunks:
                if chunk.chunk_type.value == "text":
                    text_context.append({"content": chunk.content, "source": file.filename})
                elif chunk.chunk_type.value == "image":
                    image_context.append({"image_bytes": chunk.raw_content, "description": chunk.content, "source": file.filename})
        elif file.content_type.startswith("image/"):
            image_context.append({"image_bytes": file.data, "source": file.filename})

    logger.info(f"Direct context: {len(text_context)} text chunks and {len(image_context)} image chunks")
```

**Add helper function:**
```python
def build_search_query_from_fields(fields: List[dict]) -> str:
    """Build search query from form field labels."""
    labels = [f.get("label", "") for f in fields if f.get("label")]
    return " ".join(labels[:10])  # Use first 10 labels
```

### 5.3 Update Agent Service to Accept New Context Format

**File:** `backend/src/services/agent_service.py`

**Modify `generate_form_values` signature (line 91):**

```python
async def generate_form_values(
    self,
    user_id: str,
    field_groups: list,
    visible_text: str,
    clipboard_text: str | None = None,
    text_context: List[Dict] | None = None,  # NEW: Replaces user_files
    image_context: List[Dict] | None = None,  # NEW
    quality: str = "medium",
    personal_instructions: Optional[str] = None,
) -> dict:
```

**Update `_generate_form_values_batch` (line 156):**

```python
async def _generate_form_values_batch(
    self,
    user_id: str,
    fields: list,
    visible_text: str,
    clipboard_text: str | None,
    text_context: List[Dict],  # NEW
    image_context: List[Dict],  # NEW
    model: str,
    personal_instructions: Optional[str] = None,
) -> dict:
    """Generate values with RAG context."""
    from ..agents.utils import create_multipart_query

    generator_agent = self.generator_flash if model == "gemini-2.0-flash" else self.generator_pro

    instructions_text = personal_instructions or "No personal instructions provided."

    # Build context string from text chunks
    context_texts = []
    for i, chunk in enumerate(text_context or []):
        context_texts.append(
            f"Document excerpt {i+1} from {chunk.get('source', 'unknown')}:\n{chunk['content']}\n"
        )

    query = f"""Please generate appropriate values for the following form fields.
Follow these directives strictly:
- Treat session instructions as authoritative guidance.
- Blend the user's personal instructions with any other context when deciding on values.
- Provide a best-effort value for every field; only return null when the user explicitly requests a blank or when no responsible inference is possible.

Retrieved Context from User Documents:
{chr(10).join(context_texts) if context_texts else "No document context available."}

Form Fields (structured data from HTML analysis):
```json
{json.dumps(fields, indent=2)}
```

Page Visible Text:
{visible_text}

Session Instructions:
{clipboard_text if clipboard_text else 'No session instructions provided'}

Personal Instructions:
{instructions_text}

Additional context: User has uploaded {len(image_context or [])} image(s) which are provided below.

Please analyze all provided context and generate appropriate values for each field.
"""

    # Prepare multimodal content with images
    content = create_multipart_query(
        query=query,
        images=[img["image_bytes"] for img in (image_context or [])]
    )

    result = await generator_agent.run(
        user_id=user_id,
        state={},
        content=content,
        debug=False,
        max_retries=settings.AGENT_MAX_RETRIES,
        retry_delay=settings.AGENT_RETRY_DELAY_SECONDS,
    )

    return result
```

**Similar updates for `_generate_form_values_ultra`**

---

## Phase 6: Configuration

### 6.1 Update Settings

**File:** `backend/src/config/settings.py`

**Add:**
```python
# ChromaDB Configuration
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_AUTH_TOKEN = os.getenv("CHROMA_AUTH_TOKEN", "")

# RAG Configuration
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1000"))  # tokens
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))  # tokens
RAG_TOP_K_RESULTS = int(os.getenv("RAG_TOP_K_RESULTS", "10"))

# Tesseract OCR Path (Windows)
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
```

### 6.2 Update .env.example

**File:** `backend/.env.example`

**Add:**
```bash
# ChromaDB
CHROMA_HOST=localhost
CHROMA_PORT=8000
CHROMA_AUTH_TOKEN=easyform_rag_token_2024

# RAG Settings
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
RAG_TOP_K_RESULTS=10

# Tesseract OCR (Windows)
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

---

## Phase 7: Testing & Optimization

### 7.1 Testing Plan

**Create test file:** `backend/tests/test_rag_service.py`

```python
"""Tests for RAG service."""
import pytest
from src.services.rag_service import get_rag_service


@pytest.mark.asyncio
async def test_pdf_processing():
    """Test PDF chunking and embedding."""
    # TODO: Implement
    pass


@pytest.mark.asyncio
async def test_semantic_search():
    """Test ChromaDB retrieval."""
    # TODO: Implement
    pass


@pytest.mark.asyncio
async def test_rag_vs_direct_decision():
    """Test decision logic for RAG vs direct."""
    # TODO: Implement
    pass
```

### 7.2 Manual Testing Steps

1. **Start ChromaDB:**
   ```bash
   docker run -d -p 8000:8000 chromadb/chroma
   ```

2. **Upload a test PDF:**
   ```bash
   curl -X POST http://localhost:8000/api/files/upload \
     -H "Authorization: Bearer <token>" \
     -d '{
       "filename": "resume.pdf",
       "content_type": "application/pdf",
       "data": "<base64_data>"
     }'
   ```

3. **Check processing:**
   ```sql
   SELECT * FROM document_chunks WHERE file_id = '<file_id>';
   ```

4. **Test form analysis with RAG:**
   ```bash
   curl -X POST http://localhost:8000/api/form/analyze
   ```

5. **Verify ChromaDB:**
   ```python
   import chromadb
   client = chromadb.HttpClient(host="localhost", port=8000)
   collection = client.get_collection("easyform_documents")
   print(f"Total chunks: {collection.count()}")
   ```

### 7.3 Optimization Tasks

- [ ] Tune chunk size (test 512, 1000, 2000 tokens)
- [ ] Implement advanced chunking (semantic boundaries)
- [ ] Add caching for embeddings
- [ ] Monitor Chroma query latency
- [ ] Add re-ranking for better results
- [ ] Implement hybrid search (semantic + keyword)

---

## Implementation Timeline

| Phase | Estimated Time | Dependencies |
|-------|----------------|--------------|
| Phase 1: Database Schema | 2-3 hours | None |
| Phase 2: Dependencies | 1-2 hours | Phase 1 |
| Phase 3: Core Services | 6-8 hours | Phase 2 |
| Phase 4: CRUD Operations | 2-3 hours | Phase 1 |
| Phase 5: Integration | 4-6 hours | Phases 3, 4 |
| Phase 6: Configuration | 1 hour | None |
| Phase 7: Testing | 4-6 hours | All phases |
| **Total** | **20-29 hours** | ~3-4 days |

---

## Rollback Plan

If RAG causes issues:

1. **Feature flag:** Add `RAG_ENABLED=false` to `.env`
2. **Revert form_service.py:** Comment out RAG code, use direct file passing
3. **Keep infrastructure:** Leave tables and services for future use
4. **Monitor:** Check logs for errors before full rollback

---

## Monitoring & Metrics

After deployment, track:

1. **Processing Metrics:**
   - Files processed per day
   - Average processing time per file
   - Chunk count distribution

2. **Retrieval Metrics:**
   - Average search latency (<500ms target)
   - Top-K relevance scores (>0.7 target)
   - RAG vs. direct usage ratio

3. **Cost Metrics:**
   - Google embedding API costs
   - Chroma storage size
   - Total cost per form-fill

4. **Quality Metrics:**
   - Form fill accuracy (manual spot checks)
   - User feedback on suggestions
   - Null value rate (should decrease)

---

## Conclusion

This plan implements RAG following your existing architecture patterns:
- ✅ Modular services (DocumentProcessingService, EmbeddingService, RAGService)
- ✅ Singleton pattern like AgentService
- ✅ Async CRUD operations
- ✅ Background task processing
- ✅ Environment-based configuration
- ✅ ChromaDB HTTP client for scalability
- ✅ Smart hybrid approach (RAG only when beneficial)
- ✅ Multimodal support (text + images)

**Next Step:** Start with Phase 1 (Database Schema) and proceed sequentially.
