"""
The Solution Generator Agent analyzes form questions and provides appropriate solutions/answers
as plain text (without structured output).
"""

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types

from ..agent import StandardAgent
from ..utils import load_instruction_from_file


class SolutionGeneratorAgent(StandardAgent):
    def __init__(self, app_name: str, session_service, model: str = "gemini-2.5-pro"):
        self.full_instructions = load_instruction_from_file("solution_generator_agent/instructions.txt")

        # Use provided model or default to Gemini 2.5 Pro
        self.model = model
        self._response_config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
        )

        generator_agent = LlmAgent(
            name="solution_generator_agent",
            model=self.model,
            description="Agent for generating appropriate solutions/answers for form questions.",
            instruction=self.full_instructions,
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
