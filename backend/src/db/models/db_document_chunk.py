"""
Database model for document chunks extracted from files.
Used for RAG (Retrieval-Augmented Generation) context storage.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, JSON, LargeBinary, Enum as SQLEnum
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
    chunk_type = Column(SQLEnum(ChunkType), nullable=False, default=ChunkType.TEXT)

    # Extracted content
    content = Column(Text, nullable=True)  # Text content or OCR result
    raw_content = Column(LargeBinary(length=2**30), nullable=True)  # For images (optional, can reference file)

    # Metadata for traceability
    metadata_json = Column(JSON, nullable=True)  # {page: 5, bbox: [...], etc.}

    # Chroma reference
    chroma_id = Column(String(255), nullable=True, index=True)  # ID in Chroma DB

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    # file = relationship("File", back_populates="chunks")
