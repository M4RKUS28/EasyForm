"""
The HTML Form Parser Agent analyzes HTML and extracts form fields with context.
"""
from typing import Dict, Any

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.genai import types

from ..agent import StructuredAgent
from ..utils import load_instruction_from_file


class HtmlFormParserAgent(StructuredAgent):
    def __init__(self, app_name: str, session_service):
        self.full_instructions = load_instruction_from_file("html_form_parser_agent/instructions.txt")

        # Using Gemini 2.0 Flash for better analysis capabilities
        self.model = "gemini-2.0-flash"

        parser_agent = LlmAgent(
            name="html_form_parser_agent",
            model=self.model,
            description="Agent for parsing HTML forms and extracting field information with context.",
            instruction=self.full_instructions
        )

        # Store references
        self.app_name = app_name
        self.session_service = session_service
        self.runner = Runner(
            agent=parser_agent,
            app_name=self.app_name,
            session_service=self.session_service,
        )
