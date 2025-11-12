"""
Progress/event tracking for long-running form analysis jobs.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Index,
)

from ..database import Base


class FormRequestProgress(Base):
    """Stores fine-grained progress updates for a form request."""

    __tablename__ = "form_request_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(
        String(50),
        ForeignKey("form_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage = Column(String(64), nullable=False)
    message = Column(Text, nullable=False)
    progress = Column(Integer, nullable=True)  # Percentage 0-100
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("idx_form_request_progress_request_id", "request_id"),
    )
