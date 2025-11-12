"""Schemas describing the structured output for the HTML form parser agent."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class GridStructure(BaseModel):
    """Structure for grid/matrix questions."""
    rows: List[str] = Field(default_factory=list, description="Row labels for grid/matrix questions")
    columns: List[str] = Field(default_factory=list, description="Column labels for grid/matrix questions")


class ScaleRange(BaseModel):
    """Range configuration for scale/slider questions."""
    min: str = Field(..., description="Minimum value for the scale")
    max: str = Field(..., description="Maximum value for the scale")
    step: Optional[str] = Field(None, description="Step value for numeric scales")


class InteractionTarget(BaseModel):
    """Technical details for a single interactable element (radio/checkbox option, dropdown item, etc.)."""

    selector: str = Field(
        ...,
        description="Precise CSS selector pointing to this input element."
    )
    value: Optional[str] = Field(
        None,
        description="The value attribute or canonical choice associated with this input."
    )
    label: Optional[str] = Field(
        None,
        description="Human readable label for this specific option/input."
    )

class InteractionData(BaseModel):
    """Technical interaction details for Agent 3 (Action Generator)."""

    primary_selector: str = Field(
        ...,
        description="Primary CSS selector for the main input element (for text inputs, single select, etc.)."
    )
    action_type: str = Field(
        ...,
        description="Type of action required: input_text, select_option, check_box, click_radio, click_button, upload_file, select_date, custom."
    )
    targets: List[InteractionTarget] = Field(
        default_factory=list,
        description="Multiple targets for radio/checkbox groups or dropdown options. Empty for simple text inputs."
    )
    current_value: Optional[str] = Field(
        None,
        description="Currently filled/selected value visible in the DOM (for pre-filled inputs)."
    )


class QuestionData(BaseModel):
    """Semantic question data for Agent 2 (Solution Generator)."""

    question: str = Field(
        ...,
        description="Exact wording of the question as it appears in the form (minimal cleanup, preserve original intent)."
    )
    additional_information: Optional[str] = Field(
        None,
        description="Supplemental context to aid downstream RAG/solution steps (e.g., section headers, hints, validation rules, examples, detected prefilled values)."
    )
    selection_mode: str = Field(
        "none",
        description="Selection mode: 'single' (radio/dropdown), 'multiple' (checkbox), 'none' (text/date/file)."
    )
    available_options: Optional[List[str]] = Field(
        None,
        description="List of available options for selection fields (radio/dropdown/checkbox). Always populated for selection questions."
    )
    grid_structure: Optional[GridStructure] = Field(
        None,
        description="For grid/matrix questions: row and column labels for Agent 2 to understand the structure."
    )
    scale_range: Optional[ScaleRange] = Field(
        None,
        description="For scale questions: min/max/step values to guide Agent 2's answer generation."
    )


class FormQuestion(BaseModel):
    """Logical form question with separated semantic and interaction data."""

    id: str = Field(
        ...,
        description="Stable identifier for the question (e.g., name/id from the DOM)."
    )
    type: str = Field(
        ...,
        description="Normalized question type: text, textarea, email, tel, number, dropdown, radio, checkbox, date, time, file, scale, grid, custom."
    )
    question_data: QuestionData = Field(
        ...,
        description="Semantic data for Agent 2 (Solution Generator) to understand what answer is needed."
    )
    interaction_data: InteractionData = Field(
        ...,
        description="Technical data for Agent 3 (Action Generator) to execute the interactions."
    )


class HtmlFormParserOutput(BaseModel):
    """Top-level structured response returned by the HTML form parser."""

    questions: List[FormQuestion] = Field(
        default_factory=list,
        description="Ordered list of logical questions detected in the form.",
    )
