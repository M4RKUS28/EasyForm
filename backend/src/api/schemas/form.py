"""Pydantic schemas for form analysis."""
from typing import Optional, List, Any, Literal, Dict
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
    quality: Literal["fast", "fast-pro", "exact", "exact-pro"] = Field(
        "fast",
        description=(
            "Analysis quality controlling parser and generator models. "
            "fast=Flash/Flash per-question, fast-pro=Pro/Flash per-question, "
            "exact=Flash/Pro per-question, exact-pro=Pro/Pro per-question."
        )
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
    question: Optional[str] = Field(
        None,
        description="The original form question text this action answers"
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


class FormRequestProgressEntry(BaseModel):
    """Structured progress log entry for frontend consumption."""

    stage: str = Field(..., description="Machine-friendly stage identifier")
    message: str = Field(..., description="Human-readable progress description")
    progress: Optional[int] = Field(
        None,
        description="Optional percentage indicator (0-100)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional structured metadata for the frontend"
    )
    created_at: datetime = Field(..., description="Timestamp when the update was recorded")


class FormRequestStatusResponse(BaseModel):
    """Schema for form request status check response."""
    request_id: str = Field(..., description="Request ID")
    status: Literal["pending", "processing", "processing_step_1", "processing_step_2", "completed", "failed"] = Field(
        ...,
        description="Current status of the request"
    )
    progress: List[FormRequestProgressEntry] = Field(
        default_factory=list,
        description="Chronological list of fine-grained progress updates"
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
