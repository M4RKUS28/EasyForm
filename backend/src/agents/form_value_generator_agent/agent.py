"""
The Form Value Generator Agent generates appropriate values for form fields
based on user context and field information.
"""
from typing import Dict, Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types

from ..agent import StructuredAgent
from ..utils import load_instruction_from_file


class FormValueGeneratorAgent(StructuredAgent):
    def __init__(self, app_name: str, session_service):
        self.full_instructions = load_instruction_from_file("form_value_generator_agent/instructions.txt")

        # Using Gemini 2.5 Pro for better reasoning about user context
        self.model = "gemini-2.5-pro"

        generator_agent = LlmAgent(
            name="form_value_generator_agent",
            model=self.model,
            description="Agent for generating appropriate values for form fields based on user context.",
            instruction=self.full_instructions
        )

        # Store references
        self.app_name = app_name
        self.session_service = session_service
        self.runner = Runner(
            agent=generator_agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )
