"""
The recipe agents is used to come up with custom recipes
"""
import json
from typing import Dict, Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types

from ..agent import StructuredAgent
from ..utils import load_instruction_from_file
from .schema import Recipes



class RecipeAgent(StructuredAgent):
    def __init__(self, app_name: str, session_service):
        self.full_instructions = load_instruction_from_file("recipe_agent/instructions.txt")
        # Create the planner agent
        self.model = "gemini-2.5-flash-lite"
        recipe_agent = LlmAgent(
            name="recipe_agent",
            model=self.model,
            description="Agent for creating custom cooking recipes.",
            output_schema=Recipes,
            instruction=self.full_instructions
        )

        # Create necessary
        self.app_name = app_name
        self.session_service = session_service
        self.runner = Runner(
            agent=recipe_agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )
