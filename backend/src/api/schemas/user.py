# app/schemas.py
from pydantic import BaseModel, EmailStr, Field, field_validator # Make sure field_validator is imported
from typing import Optional, List
from datetime import datetime
import re
from ...config.settings import (
    PASSWORD_MIN_LENGTH,
    PASSWORD_REQUIRE_DIGIT,
    PASSWORD_REQUIRE_LOWERCASE,
    PASSWORD_REQUIRE_SPECIAL_CHAR,
    PASSWORD_REQUIRE_UPPERCASE,
    PASSWORD_SPECIAL_CHARACTERS_REGEX_PATTERN,
)
from ...core.enums import UserRole, ThemePreference # Import enums




class UserBase(BaseModel):
    """Base model for user data, used for both creation and updates."""
    username: str
    email: EmailStr
    profile_image_url: Optional[str] = None
    theme: Optional[ThemePreference] = Field(default=ThemePreference.LIGHT)
    language: Optional[str] = Field(default="en", min_length=2, max_length=10)

    @field_validator('language', mode='before')
    @classmethod
    def normalize_language(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return "en"
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return "en"
            primary_tag = normalized.split("-")[0]
            return primary_tag[:10]
        raise ValueError("Invalid language code")

class UserCreate(UserBase):
    """Model for creating a new user."""
    password: str = Field(
        ..., # Ellipsis means the field is required
        # min_length enforced via validator for unified messaging
        description=(
            "Password must be long enough and meet configured complexity requirements."
        )
    )

    @field_validator('password')
    @classmethod
    def password_complexity_checks(cls, v: str) -> str:
        """Validate password complexity requirements."""
        # Pydantic's Field(min_length=...) would handle this,
        # but we include it here for a unified error message if preferred.
        min_length = PASSWORD_MIN_LENGTH

        if len(v) < min_length:
            raise ValueError(f"Password must be at least {min_length} characters long.")

        errors: List[str] = []
        if PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", v):
            errors.append("must contain at least one uppercase letter")
        if PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", v):
            errors.append("must contain at least one lowercase letter")
        if PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", v):
            errors.append("must contain at least one digit")
        pattern = PASSWORD_SPECIAL_CHARACTERS_REGEX_PATTERN
        if PASSWORD_REQUIRE_SPECIAL_CHAR and not re.search(pattern, v):
            errors.append("must contain at least one special character (e.g., !@#$%)")
        
        if errors:
            # Pydantic expects a ValueError to be raised for validation failures
            # The message will be part of the 422 response detail.
            error_summary = "; ".join(errors)
            raise ValueError(f"Password does not meet complexity requirements: {error_summary}.")
        return v

class UserUpdate(BaseModel):
    """Model for updating an existing user."""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image_url: Optional[str] = None
    password: Optional[str] = Field(
        default=None, # Password is optional on update
        description="New password (if changing) must meet complexity requirements."
    )
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None # Only updatable by admins
    theme: Optional[ThemePreference] = None
    language: Optional[str] = Field(default=None, min_length=2, max_length=10)

    @field_validator('language', mode='before')
    @classmethod
    def normalize_update_language(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return None
            primary_tag = normalized.split("-")[0]
            return primary_tag[:10]
        raise ValueError("Invalid language code")

    @field_validator('password')
    @classmethod
    def update_password_complexity_checks(cls, v: Optional[str]) -> Optional[str]:
        """Validate new password complexity requirements."""
        if v is None: # If password is not being updated, skip validation
            return v
        
        # If password is provided (not None), it must meet all complexity rules.
        min_length = PASSWORD_MIN_LENGTH

        if len(v) < min_length:
            raise ValueError(f"New password must be at least {min_length} characters long.")

        errors: List[str] = []
        if PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", v):
            errors.append("must contain at least one uppercase letter")
        if PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", v):
            errors.append("must contain at least one lowercase letter")
        if PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", v):
            errors.append("must contain at least one digit")
        pattern = PASSWORD_SPECIAL_CHARACTERS_REGEX_PATTERN
        if PASSWORD_REQUIRE_SPECIAL_CHAR and not re.search(pattern, v):
            errors.append("must contain at least one special character (e.g., !@#$%)")
        
        if errors:
            error_summary = "; ".join(errors)
            raise ValueError(f"New password does not meet complexity requirements: {error_summary}.")
        return v

      
class UserPasswordUpdate(BaseModel):
    """Model for updating a user's password."""
    old_password: Optional[str] = None # Required for non-admins
    new_password: str = Field(
        ...,
        description=(
            "New password must be long enough and meet configured complexity requirements."
        )
    )

    @field_validator('new_password')
    @classmethod
    def password_complexity_checks(cls, v: str) -> str:
        """Validate new password complexity requirements."""
        min_length = PASSWORD_MIN_LENGTH

        if len(v) < min_length:
            raise ValueError(f"Password must be at least {min_length} characters long")
        if PASSWORD_REQUIRE_UPPERCASE and not any(char.isupper() for char in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if PASSWORD_REQUIRE_LOWERCASE and not any(char.islower() for char in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if PASSWORD_REQUIRE_DIGIT and not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        pattern = PASSWORD_SPECIAL_CHARACTERS_REGEX_PATTERN
        if PASSWORD_REQUIRE_SPECIAL_CHAR and not re.search(pattern, v):
            raise ValueError('Password must contain at least one special character')
        return v


class User(UserBase):
    """Model representing a user in the system."""
    id: str
    is_active: bool
    role: UserRole
    profile_image_url: Optional[str] = None # Added for profile image
    created_at: datetime
    last_login: datetime
    login_streak: int

    class Config:
        from_attributes = True

