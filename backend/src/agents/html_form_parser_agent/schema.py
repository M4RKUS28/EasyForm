"""Schemas describing the structured output for the HTML form parser agent."""
from __future__ import annotations

from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field


FieldValue = Union[str, int, float, bool, None, List[str]]


class FormField(BaseModel):
    """Structured description of a single form field detected in the page."""

    selector: str = Field(..., description="Unique CSS selector pointing to the field element.")
    type: str = Field(..., description="Normalized field type such as text, email, select, checkbox, etc.")
    label: Optional[str] = Field(
        None,
        description="Human readable label associated with the field if available.",
    )
    description: Optional[str] = Field(
        None,
        description="Additional hints or help text describing the field. Or Information from surrounding context.",
    )

    options: Optional[List[str]] = Field(
        None,
        description="Selectable options for dropdowns, radios, or grouped checkboxes.",
    )
    default_value: Optional[FieldValue] = Field(
        None,
        description="Any detected default value populated in the field.",
    )


class HtmlFormParserOutput(BaseModel):
    """Top-level structured response returned by the HTML form parser."""

    fields: List[FormField] = Field(
        default_factory=list,
        description="List of detected form fields with their metadata.",
    )
