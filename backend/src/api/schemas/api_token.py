"""Pydantic schemas for API token management."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class APITokenCreate(BaseModel):
    """Schema for creating a new API token."""
    name: Optional[str] = Field(None, max_length=100, description="Optional name for the token (e.g., 'Chrome Extension')")


class APITokenResponse(BaseModel):
    """Schema for API token response (without the actual token string)."""
    id: str
    name: Optional[str]
    created_at: datetime
    expires_at: datetime
    last_used_at: Optional[datetime]
    is_active: bool

    class Config:
        from_attributes = True


class APITokenCreateResponse(BaseModel):
    """Schema for API token creation response (includes the token string only once)."""
    id: str
    name: Optional[str]
    token: str  # Only returned on creation!
    created_at: datetime
    expires_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class APITokenListResponse(BaseModel):
    """Schema for listing API tokens."""
    tokens: list[APITokenResponse]
