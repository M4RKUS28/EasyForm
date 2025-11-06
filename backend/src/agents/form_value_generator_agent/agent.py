"""
The Form Value Generator Agent generates appropriate values for form fields
based on user context and field information.
"""

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types

from ..agent import StructuredAgent
from ..utils import load_instruction_from_file
from .schema import FormValueGeneratorOutput


class FormValueGeneratorAgent(StructuredAgent):
    def __init__(self, app_name: str, session_service, model: str = "gemini-2.5-pro"):
        self.full_instructions = load_instruction_from_file("form_value_generator_agent/instructions.txt")

        # Use provided model or default to Gemini 2.5 Pro
        self.model = model
        self.output_model = FormValueGeneratorOutput
        self._response_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=65535,
        )

        generator_agent = LlmAgent(
            name="form_value_generator_agent",
            model=self.model,
            description="Agent for generating appropriate values for form fields based on user context.",
            instruction=self.full_instructions,
            output_schema=FormValueGeneratorOutput,
            generate_content_config=self._response_config,
        )

        # Store references
        self.app_name = app_name
        self.session_service = session_service
        self.runner = Runner(
            agent=generator_agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )
