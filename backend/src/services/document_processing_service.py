"""
Service for processing uploaded documents into chunks for RAG.
Handles PDFs and images with text extraction, OCR, and chunking.
"""
import asyncio
import io
import logging
import os
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
        # Set Tesseract path from environment (for Windows dev) or use system default (Docker)
        tesseract_cmd = os.getenv("TESSERACT_CMD", "tesseract")
        if tesseract_cmd != "tesseract":
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        logger.info(f"DocumentProcessingService initialized with Tesseract at: {tesseract_cmd}")

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
                            },
                            "chroma_id": None
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
                            },
                            "chroma_id": None
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
                },
                "chroma_id": None
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
