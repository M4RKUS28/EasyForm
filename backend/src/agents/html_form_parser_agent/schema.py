"""Schemas describing the structured output for the HTML form parser agent."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class QuestionMetadata(BaseModel):
    """Structured metadata for advanced form controls like grids and scales."""

    rows: Optional[List[str]] = Field(
        None,
        description="Row labels for grid/matrix questions.",
    )
    columns: Optional[List[str]] = Field(
        None,
        description="Column labels for grid/matrix questions.",
    )
    scale_min: Optional[str] = Field(
        None,
        description="Minimum value for scale questions.",
    )
    scale_max: Optional[str] = Field(
        None,
        description="Maximum value for scale questions.",
    )
    step: Optional[str] = Field(
        None,
        description="Step value for numeric inputs or sliders.",
    )
    format: Optional[str] = Field(
        None,
        description="Expected format for special input types (e.g., 'MM/DD/YYYY' for dates).",
    )
    options: Optional[List[str]] = Field(
        None,
        description="Available options for custom widgets not captured elsewhere.",
    )


class FormInput(BaseModel):
    """Concrete interactable element belonging to a logical question."""

    input_id: str = Field(
        ..., description="Stable identifier unique within the question (e.g. question_id::option)."
    )
    selector: str = Field(
        ..., description="Precise CSS selector pointing to this input element so the extension can act on it."
    )
    input_type: str = Field(
        ..., description="Specific control type such as text, textarea, radio_option, checkbox_option, dropdown_option, date_part, etc."
    )
    option_label: Optional[str] = Field(
        None,
        description="Human readable label for this specific option/input when applicable.",
    )
    value_hint: Optional[str] = Field(
        None,
        description="The value attribute or canonical choice associated with the input if known.",
    )
    current_value: Optional[str] = Field(
        None,
        description="Currently filled/selected value for this control when visible in the DOM.",
    )
    is_default: Optional[bool] = Field(
        None,
        description="True if this option is pre-selected or represents the default state.",
    )
    constraints: Optional[str] = Field(
        None,
        description="Summary of validation constraints specific to this input (e.g., min/max, format hints).",
    )
    notes: Optional[str] = Field(
        None,
        description="Additional clarifications that apply only to this input (kept concise).",
    )


class FormQuestion(BaseModel):
    """Logical form question containing one or more concrete inputs."""

    question_id: str = Field(
        ..., description="Stable identifier for the question derived from the DOM (e.g. name/id of the group)."
    )
    question_type: str = Field(
        ..., description="Normalized question type such as text, textarea, radio_scale, checkbox_grid, date, time, etc."
    )
    title: Optional[str] = Field(
        None,
        description="Primary label or prompt shown to the user.",
    )
    description: Optional[str] = Field(
        None,
        description="Additional help text, validation hints, or contextual instructions for the question.",
    )
    context: Optional[str] = Field(
        None,
        description="Concise surrounding context such as section headers or preceding text when relevant.",
    )
    hints: Optional[List[str]] = Field(
        None,
        description="Optional short bullet-like hints to retain extra guidance without bloating descriptions.",
    )
    inputs: List[FormInput] = Field(
        default_factory=list,
        description="All interactable inputs/options associated with this question.",
    )
    metadata: Optional[QuestionMetadata] = Field(
        None,
        description="Structured metadata for advanced clients (e.g., row/column labels for grids).",
    )


class HtmlFormParserOutput(BaseModel):
    """Top-level structured response returned by the HTML form parser."""

    questions: List[FormQuestion] = Field(
        default_factory=list,
        description="Ordered list of logical questions detected in the form.",
    )
