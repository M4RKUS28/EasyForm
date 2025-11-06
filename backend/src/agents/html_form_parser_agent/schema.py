"""Schemas describing the structured output for the HTML form parser agent."""
from __future__ import annotations

from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field


FieldValue = Union[str, int, float, bool, None, List[str]]


class FormField(BaseModel):
    """Structured description of a single form field detected in the page."""

    selector: str = Field(..., description="Unique CSS selector pointing to the field element.")
    type: str = Field(..., description="Normalized field type such as text, email, select, checkbox, etc.")
    group_id: Optional[str] = Field(
        None,
        description="Stable identifier shared by all controls belonging to the same logical question (e.g., radio options in one group).",
    )
    label: Optional[str] = Field(
        None,
        description="Human readable label associated with the field if available.",
    )
    description: Optional[str] = Field(
        None,
        description="Additional hints or help text describing the field, e.g. information from surrounding context, placeholder text, default value or field validation rules.",
    )

    options: Optional[List[str]] = Field(
        None,
        description="Selectable options for dropdowns, radios, or grouped checkboxes.",
    )


class HtmlFormParserOutput(BaseModel):
    """Top-level structured response returned by the HTML form parser."""

    fields: List[FormField] = Field(
        default_factory=list,
        description="List of detected form fields with their metadata.",
    )
