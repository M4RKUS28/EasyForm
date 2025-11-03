"""
Database model for API tokens.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from ..database import Base


class APIToken(Base):
    """Model for API tokens used for browser extension authentication."""

    __tablename__ = "api_tokens"

    id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(500), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)  # Optional name like "Chrome Extension", "Firefox Extension"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)  # Minimum 1 year from creation
    last_used_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationship to user
    # user = relationship("User", back_populates="api_tokens")
