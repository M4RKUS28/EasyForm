from typing import Optional, Literal
from pydantic import BaseModel, Field

AnimationFileName = Literal[
    "boil_water.json",
    "fire_in_pan.json",
    "fry_in_pan.json",
    "let_cook_and_stir.json",
    "microwave.json",
    "oven_convect.json",
    "steaming_with_lid.json",
]

class InstructionStep(BaseModel):
    """Schema representing one instruction step."""
    heading: str = Field(
        description="Heading of the current instruction step"
    )
    description: str = Field(
        description="Detailed description of what to do in the current instruction step (3-4 lines)"
    )
    animation: AnimationFileName = Field(
        description="The animation used for this step"
    )
    timer: Optional[int] = Field(
        description="If a timer is needed for this step, specify its duration in seconds."
    )


class Instructions(BaseModel):
    """Schema representing a list of instruction steps."""
    steps: list[InstructionStep] = Field(
        description="The instructions for cooking the recipe"
    )
