"""
Database model for user accounts.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Enum, Integer, String, DateTime, Text
from sqlalchemy.orm import relationship

from ..database import Base
from ...core.enums import UserRole, ThemePreference

class User(Base):
    """Model for user accounts in the system."""
    
    __tablename__ = "users"
    id = Column(String(50), primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(100), nullable=False) # Später true, oaut = NULL
    is_active = Column(Boolean, default=True)
    role = Column(
        Enum(
            UserRole,
            name="user_roles",
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=UserRole.USER.value,
    )

    theme = Column(
        Enum(
            ThemePreference,
            name="user_theme_preferences",
            native_enum=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ThemePreference.LIGHT.value,
    )

    language = Column(String(10), nullable=False, default="en")


    #später hier oauth accs erkennen: open_id = Column(String(50), unique=True, index=True, nullable=True) # New field for OpenID
    # Use generic Text so it maps to PostgreSQL 'text' type instead of MySQL LONGTEXT
    profile_image_url = Column(Text, nullable=True)  # New field for profile image
    personal_instructions = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=True)
    last_login = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=True) # Will be updated manually on login

    login_streak = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)  # New field for email verification status
    verification_token = Column(String(100), nullable=True)  # Token for email verification
    is_subscribed = Column(Boolean, default=False)  # New field for subscription status
