"""
The HTML Form Parser Agent analyzes HTML and extracts form fields with context.
"""

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types

from ..agent import StructuredAgent
from ..utils import load_instruction_from_file
from .schema import HtmlFormParserOutput


class HtmlFormParserAgent(StructuredAgent):
    def __init__(self, app_name: str, session_service, model: str = "gemini-2.5-pro"):
        self.full_instructions = load_instruction_from_file("html_form_parser_agent/instructions.txt")

        # Use provided model or default to Gemini 2.5 Pro
        self.model = model
        self.output_model = HtmlFormParserOutput
        self._response_config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=8192,
        )

        parser_agent = LlmAgent(
            name="html_form_parser_agent",
            model=self.model,
            description="Agent for parsing HTML forms and extracting field information with context.",
            instruction=self.full_instructions,
            output_schema=HtmlFormParserOutput,
            generate_content_config=self._response_config,
        )

        # Store references
        self.app_name = app_name
        self.session_service = session_service
        self.runner = Runner(
            agent=parser_agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )
