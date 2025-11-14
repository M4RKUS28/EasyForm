"""Pydantic schemas for file management."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class FileUpload(BaseModel):
    """Schema for uploading a file."""
    filename: str = Field(..., max_length=255, description="Name of the file")
    content_type: str = Field(..., max_length=100, description="MIME type (e.g., image/png, application/pdf)")
    data: str = Field(..., description="Base64 encoded file data")

    @field_validator('content_type')
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        """Validate that content type is allowed."""
        allowed_types = [
            'image/png',
            'image/jpeg',
            'image/jpg',
            'image/gif',
            'image/webp',
            'application/pdf'
        ]
        if v.lower() not in allowed_types:
            raise ValueError(f"Content type {v} not allowed. Allowed types: {', '.join(allowed_types)}")
        return v.lower()


class FileResponse(BaseModel):
    """Schema for file response (metadata only, no data)."""
    id: str
    filename: str
    content_type: str
    file_size: int
    created_at: datetime
    processing_status: Optional[str] = "pending"  # pending, processing, completed, failed
    page_count: Optional[int] = None

    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """Schema for listing files."""
    files: list[FileResponse]
    total_storage_bytes: int


class FileDownloadResponse(BaseModel):
    """Schema for downloading a file (includes data)."""
    id: str
    filename: str
    content_type: str
    file_size: int
    data: str  # Base64 encoded
    created_at: datetime
