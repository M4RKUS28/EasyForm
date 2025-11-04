"""
Database model for form analysis requests.
Stores async form analysis requests with status tracking.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base


class FormRequest(Base):
    """Model for async form analysis requests."""

    __tablename__ = "form_requests"

    # Primary key
    id = Column(String(50), primary_key=True, index=True)

    # Foreign key to user
    user_id = Column(String(50), ForeignKey("users.id"), nullable=False, index=True)

    # Status tracking
    status = Column(
        SQLEnum(
            "pending",
            "processing",
            "processing_step_1",
            "processing_step_2",
            "completed",
            "failed",
            name="form_request_status",
            create_type=True
        ),
        nullable=False,
        default="pending",
        index=True
    )

    # Optional: Hash of HTML to detect duplicates (not implemented yet)
    html_hash = Column(String(64), nullable=True)

    # Results
    fields_detected = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationship to actions
    actions = relationship(
        "FormAction",
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
