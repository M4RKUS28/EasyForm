"""
This file defines the service that coordinates the interaction between all the agents
"""
import json
from logging import getLogger

from ..agents.html_form_parser_agent import HtmlFormParserAgent
from ..agents.form_value_generator_agent import FormValueGeneratorAgent

from google.adk.sessions import InMemorySessionService


logger = getLogger(__name__)


class AgentService:
    def __init__(self):
        self.session_service = InMemorySessionService()
        self.app_name = "EasyForm"

        # Initialize agents
        self.html_form_parser_agent = HtmlFormParserAgent(self.app_name, self.session_service)
        self.form_value_generator_agent = FormValueGeneratorAgent(self.app_name, self.session_service)

    async def parse_form_structure(
        self,
        user_id: str,
        html: str,
        dom_text: str,
        screenshots: list = None
    ) -> dict:
        """
        Parse HTML form structure using the HTML Form Parser Agent.

        Args:
            user_id: User ID for session management
            html: HTML code of the page
            dom_text: Visible text content
            screenshots: Optional list of screenshot bytes

        Returns:
            Dictionary with parsed field structure
        """
        from ..agents.utils import create_multipart_query

        # Build query
        query = f"""Please analyze the following HTML and extract all form fields.

HTML Code:
```html
{html}
```

Visible Text Content:
{dom_text}
"""

        # Create multi-part content with screenshots if provided
        content = create_multipart_query(
            query=query,
            screenshots=screenshots if screenshots else None
        )

        # Run agent
        result = await self.html_form_parser_agent.run(
            user_id=user_id,
            state={},
            content=content,
            debug=False
        )

        return result

    async def generate_form_values(
        self,
        user_id: str,
        fields: list,
        visible_text: str,
        user_files: list = None
    ) -> dict:
        """
        Generate values for form fields using the Form Value Generator Agent.

        Args:
            user_id: User ID for session management
            fields: List of field dictionaries from parser
            visible_text: Visible text from the page
            user_files: Optional list of user file objects (from DB)

        Returns:
            Dictionary with generated actions
        """
        from ..agents.utils import create_multipart_query
        import json

        # Prepare user files for context
        pdf_files = []
        images = []

        if user_files:
            for file in user_files:
                if file.content_type == "application/pdf":
                    pdf_files.append(file.data)
                elif file.content_type.startswith("image/"):
                    images.append(file.data)

        # Build query
        query = f"""Please generate appropriate values for the following form fields.

Form Fields (structured data from HTML analysis):
```json
{json.dumps(fields, indent=2)}
```

Page Visible Text:
{visible_text}

User has uploaded {len(pdf_files)} PDF(s) and {len(images)} image(s) that may contain relevant information.

Please analyze all provided context and generate appropriate values for each field.
"""

        # Create multi-part content with user files
        content = create_multipart_query(
            query=query,
            pdf_files=pdf_files if pdf_files else None,
            images=images if images else None
        )

        # Run agent
        result = await self.form_value_generator_agent.run(
            user_id=user_id,
            state={},
            content=content,
            debug=False
        )

        return result
