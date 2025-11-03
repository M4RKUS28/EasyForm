"""
Database model for file storage.
Files are stored as BLOBs in the database.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, LargeBinary
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.orm import relationship

from ..database import Base


class File(Base):
    """Model for file storage (images and PDFs) with BLOB storage."""

    __tablename__ = "files"

    id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    content_type = Column(String(100), nullable=False)  # e.g., "image/png", "application/pdf"
    file_size = Column(Integer, nullable=False)  # Size in bytes
    # Use LONGBLOB for MySQL to support files up to 4GB (we limit to 200MB in application)
    data = Column(LONGBLOB, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship to user
    # user = relationship("User", back_populates="files")
