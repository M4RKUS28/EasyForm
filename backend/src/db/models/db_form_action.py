"""
Database model for form actions.
Stores individual actions generated for a form request.
"""
from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base


class FormAction(Base):
    """Model for individual form actions."""

    __tablename__ = "form_actions"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to request
    request_id = Column(
        String(50),
        ForeignKey("form_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Action details
    action_type = Column(String(50), nullable=False)  # fillText, selectDropdown, etc.
    selector = Column(Text, nullable=False)  # CSS selector
    value = Column(Text, nullable=True)  # JSON or plain text value
    label = Column(String(255), nullable=True)  # Human-readable label

    # Order of execution
    order_index = Column(Integer, nullable=False, default=0)

    # Relationship back to request
    request = relationship("FormRequest", back_populates="actions")
