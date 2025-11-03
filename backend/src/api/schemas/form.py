"""Pydantic schemas for form analysis."""
from typing import Optional, List, Any, Literal

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
