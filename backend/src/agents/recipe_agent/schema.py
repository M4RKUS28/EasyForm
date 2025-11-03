"""
Defines the output schema for the structured output of the recipe agent
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class Ingredient(BaseModel):
    """Schema representing an ingredient."""
    name: str = (
        Field(description="Name of the ingredient"))
    unit: Optional[str] =(
        Field(description="Unit the ingredient is measured in e.g. Gramms, Cups, Tbs"))
    quantity: Optional[float] = (
        Field(description="Quantity of the ingredient in the given unit"))

class Recipe(BaseModel):
    title: str = (
        Field(description="Name of the recipe, e.g. 'Spaghetti Bolognese'"))
    description: str = (
        Field(description="Short description of the recipe, e.g. 'A classic Italian ragu, simmered to perfection for a rich flavor.'"))
    ingredients: List[Ingredient] = (
        Field(description="List of needed ingredients for the recipe"))
    servings: int = (
        Field(description="Number of servings that the given ingredients produce"))
    total_time_minutes: int = (
        Field(description="Total time in minutes to prepare and cook the recipe, e.g. 45"))
    difficulty: Literal["easy", "medium", "hard"] = (
        Field(description="Difficulty level of the recipe. Must be one of: 'easy', 'medium', or 'hard'"))
    food_category: Literal["vegan", "vegetarian", "beef", "pork", "chicken", "lamb", "fish", "seafood", "mixed-meat", "alcoholic", "non-alcoholic"] = (
        Field(description="Food category based on ingredients. 'vegan' if no animal products, 'vegetarian' if contains dairy/eggs but no meat, or specify the exact type of meat: 'beef', 'pork', 'chicken', 'lamb', 'fish', 'seafood', or 'mixed-meat' if contains multiple types of meat. For Drinks alcoholic if the drink contains alcohol otherwise non-alcoholic"))
    important_notes: str = (
        Field(description="Critical preparation notes, required tools, or cautions expressed as a short paragraph."))
    cooking_overview: str = (
        Field(description="Brief high-level summary of the cooking flow in 3-4 steps."))

class Recipes(BaseModel):
    recipes: List[Recipe] = (
        Field(description="List of recipes")
    )
