"""
The image analyzer agents is used to analyze what food items are seen in an image
"""
import json
from typing import Dict, Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types

from ..agent import StructuredAgent, StandardAgent
from ..utils import load_instruction_from_file



class ImageAnalyzerAgent(StandardAgent):
    def __init__(self, app_name: str, session_service):
        self.full_instructions = load_instruction_from_file("image_analyzer_agent/instructions.txt")
        # Create the planner agent
        self.model = "gemini-2.5-flash"
        recipe_agent = LlmAgent(
            name="image_analyzer_agent",
            model=self.model,
            description="Agent for extracting food items from an image.",
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