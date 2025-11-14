"""Schemas describing the structured output for the action generator agent."""
from __future__ import annotations

from typing import List, Optional, Union, Literal

from pydantic import BaseModel, Field

ActionValue = Optional[Union[str, int, float, bool]]
ActionType = Literal["fillText", "selectDropdown", "selectRadio", "selectCheckbox", "click"]


class GeneratedAction(BaseModel):
    """Single action that the extension should perform on the target page."""

    action_type: ActionType = Field(
        ...,
        description="One of fillText, selectDropdown, selectRadio, selectCheckbox, or click.",
    )
    selector: str = Field(..., description="CSS selector identifying the target element.")
    value: ActionValue = Field(
        None,
        description="Value to apply for the action; null when no value can be determined.",
    )
    question: Optional[str] = Field(
        None,
        description="The original form question text from the form (e.g., '1) 18 + 27 = ?').",
    )


class ActionGeneratorOutput(BaseModel):
    """Top-level structured response returned by the action generator."""

    actions: List[GeneratedAction] = Field(
        default_factory=list,
        description="Ordered list of actions required to complete the form questions.",
    )
