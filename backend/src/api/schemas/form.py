"""Pydantic schemas for form analysis."""
from typing import Optional, List, Any, Literal
from datetime import datetime

from pydantic import BaseModel, Field


class FormAnalyzeRequest(BaseModel):
    """Schema for form analysis request."""
    html: str = Field(..., description="Complete HTML code of the page")
    visible_text: str = Field(..., description="Visible text content of the page")
    clipboard_text: Optional[str] = Field(
        None,
        description="Contents of the user's clipboard at analysis time"
    )
    screenshots: Optional[List[str]] = Field(
        None,
        description="Optional list of base64-encoded screenshots (for extended mode)"
    )
    mode: Literal["basic", "extended"] = Field(
        "basic",
        description="Analysis mode: 'basic' (HTML + text only) or 'extended' (includes screenshots)"
    )
    quality: Literal["fast", "fast-ultra", "medium", "medium-ultra", "exact", "exact-ultra"] = Field(
        "medium",
        description="Analysis quality: determines models and processing method. "
                    "fast=Flash/Flash, medium=Flash/Pro, exact=Pro/Pro. "
                    "Ultra variants use per-group parallel processing in step 2."
    )


class FormAction(BaseModel):
    """Schema for a single form action."""
    action_type: str = Field(
        ...,
        description="Type of action: 'setValue', 'click', 'select', 'radio', 'checkbox', etc."
    )
    selector: str = Field(
        ...,
        description="CSS selector or XPath to identify the element"
    )
    value: Optional[Any] = Field(
        None,
        description="Value to set (for input fields, selects, etc.)"
    )
    label: Optional[str] = Field(
        None,
        description="Human-readable label or description of the field"
    )


class FormAnalyzeResponse(BaseModel):
    """Schema for form analysis response."""
    status: Literal["success", "error"]
    message: Optional[str] = Field(
        None,
        description="Optional message (e.g., error description or info)"
    )
    actions: List[FormAction] = Field(
        default_factory=list,
        description="List of actions to perform on the form"
    )
    fields_detected: int = Field(
        0,
        description="Number of form fields detected"
    )


# ===== NEW: Async API Schemas =====


class FormAnalyzeAsyncResponse(BaseModel):
    """Schema for async form analysis response - returns request ID immediately."""
    request_id: str = Field(..., description="Unique ID to track the analysis request")
    status: Literal["pending"] = Field(
        default="pending",
        description="Initial status is always 'pending'"
    )


class FormRequestStatusResponse(BaseModel):
    """Schema for form request status check response."""
    request_id: str = Field(..., description="Request ID")
    status: Literal["pending", "processing", "processing_step_1", "processing_step_2", "completed", "failed"] = Field(
        ...,
        description="Current status of the request"
    )
    fields_detected: Optional[int] = Field(
        None,
        description="Number of form fields detected (only available when completed)"
    )
    error_message: Optional[str] = Field(
        None,
        description="Error message if status is 'failed'"
    )
    created_at: datetime = Field(..., description="When the request was created")
    started_at: Optional[datetime] = Field(None, description="When processing started")
    completed_at: Optional[datetime] = Field(None, description="When processing completed")


class FormRequestActionsResponse(BaseModel):
    """Schema for form request actions response."""
    request_id: str = Field(..., description="Request ID")
    status: Literal["pending", "processing", "processing_step_1", "processing_step_2", "completed", "failed"] = Field(
        ...,
        description="Current status of the request"
    )
    actions: List[FormAction] = Field(
        default_factory=list,
        description="List of actions (only available when status is 'completed')"
    )
