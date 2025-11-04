"""
This file defines the service that coordinates the interaction between all the agents
"""
import asyncio
import json
from logging import getLogger
from typing import Literal

from ..agents.html_form_parser_agent import HtmlFormParserAgent
from ..agents.form_value_generator_agent import FormValueGeneratorAgent

from google.adk.sessions import InMemorySessionService


logger = getLogger(__name__)

# Quality mode configuration
# Maps quality levels to (step1_model, step2_model, is_ultra)
MODEL_CONFIG = {
    "fast": ("gemini-2.0-flash", "gemini-2.0-flash", False),
    "fast-ultra": ("gemini-2.0-flash", "gemini-2.0-flash", True),
    "medium": ("gemini-2.0-flash", "gemini-2.5-pro", False),
    "medium-ultra": ("gemini-2.0-flash", "gemini-2.5-pro", True),
    "exact": ("gemini-2.5-pro", "gemini-2.5-pro", False),
    "exact-ultra": ("gemini-2.5-pro", "gemini-2.5-pro", True),
}


class AgentService:
    def __init__(self):
        self.session_service = InMemorySessionService()
        self.app_name = "EasyForm"

        # Pre-initialize agents with both models for reuse
        logger.info("Initializing agents with both Flash and Pro models...")
        self.parser_flash = HtmlFormParserAgent(self.app_name, self.session_service, model="gemini-2.0-flash")
        self.parser_pro = HtmlFormParserAgent(self.app_name, self.session_service, model="gemini-2.5-pro")
        self.generator_flash = FormValueGeneratorAgent(self.app_name, self.session_service, model="gemini-2.0-flash")
        self.generator_pro = FormValueGeneratorAgent(self.app_name, self.session_service, model="gemini-2.5-pro")
        logger.info("All agents initialized successfully")

    async def parse_form_structure(
        self,
        user_id: str,
        html: str,
        dom_text: str,
        clipboard_text: str = None,
        screenshots: list = None,
        quality: str = "medium"
    ) -> dict:
        """
        Parse HTML form structure using the HTML Form Parser Agent.

        Args:
            user_id: User ID for session management
            html: HTML code of the page
            dom_text: Visible text content
            clipboard_text: Clipboard contents captured during analysis
            screenshots: Optional list of screenshot bytes
            quality: Quality mode (fast, fast-ultra, medium, medium-ultra, exact, exact-ultra)

        Returns:
            Dictionary with parsed field structure
        """
        from ..agents.utils import create_multipart_query

        # Get model configuration for this quality level
        step1_model, _, _ = MODEL_CONFIG.get(quality, MODEL_CONFIG["medium"])

        # Select pre-initialized agent based on model
        parser_agent = self.parser_flash if step1_model == "gemini-2.0-flash" else self.parser_pro

        # Build query
        query = f"""Please analyze the following HTML and extract all form fields.
Group related fields together when it makes sense (e.g., address fields, name fields).

HTML Code:
```html
{html}
```

Visible Text Content:
{dom_text}

Clipboard Content:
{clipboard_text if clipboard_text else 'No clipboard content provided'}
"""

        # Create multi-part content with screenshots if provided
        content = create_multipart_query(
            query=query,
            screenshots=screenshots if screenshots else None
        )

        # Run agent
        result = await parser_agent.run(
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
        clipboard_text: str = None,
        user_files: list = None,
        quality: str = "medium"
    ) -> dict:
        """
        Generate values for form fields using the Form Value Generator Agent.

        Args:
            user_id: User ID for session management
            fields: List of field dictionaries from parser
            visible_text: Visible text from the page
            clipboard_text: Clipboard contents captured during analysis
            user_files: Optional list of user file objects (from DB)
            quality: Quality mode (fast, fast-ultra, medium, medium-ultra, exact, exact-ultra)

        Returns:
            Dictionary with generated actions
        """
        from ..agents.utils import create_multipart_query
        import json

        # Get model configuration for this quality level
        _, step2_model, is_ultra = MODEL_CONFIG.get(quality, MODEL_CONFIG["medium"])

        # Prepare user files for context
        pdf_files = []
        images = []

        if user_files:
            for file in user_files:
                if file.content_type == "application/pdf":
                    pdf_files.append(file.data)
                elif file.content_type.startswith("image/"):
                    images.append(file.data)

        if is_ultra:
            # Ultra mode: Process each field group individually with parallel execution
            logger.info(f"Using ultra processing mode with {step2_model} for {len(fields)} field groups")
            return await self._generate_form_values_ultra(
                user_id=user_id,
                field_groups=fields,
                visible_text=visible_text,
                clipboard_text=clipboard_text,
                pdf_files=pdf_files,
                images=images,
                model=step2_model
            )
        else:
            # Regular mode: Process all fields together
            logger.info(f"Using regular processing mode with {step2_model} for {len(fields)} field groups")
            return await self._generate_form_values_batch(
                user_id=user_id,
                fields=fields,
                visible_text=visible_text,
                clipboard_text=clipboard_text,
                pdf_files=pdf_files,
                images=images,
                model=step2_model
            )

    async def _generate_form_values_batch(
        self,
        user_id: str,
        fields: list,
        visible_text: str,
        clipboard_text: str,
        pdf_files: list,
        images: list,
        model: str
    ) -> dict:
        """
        Generate values for all fields in a single batch (regular mode).
        """
        from ..agents.utils import create_multipart_query
        import json

        # Select pre-initialized agent based on model
        generator_agent = self.generator_flash if model == "gemini-2.0-flash" else self.generator_pro

        # Build query
        query = f"""Please generate appropriate values for the following form fields.
Follow these directives strictly:
- Treat clipboard content as authoritative instructions.
- Provide a best-effort value for every field; only return null when the user explicitly requests a blank or when no responsible inference is possible.
- For multiple-choice fields, select one of the provided options; for checkboxes output true/false for each required option.
- Keep values consistent with each other (e.g., same person details across fields) and respect validation hints.

Form Fields (structured data from HTML analysis):
```json
{json.dumps(fields, indent=2)}
```

Page Visible Text:
{visible_text}

Clipboard Content:
{clipboard_text if clipboard_text else 'No clipboard content provided'}

User has uploaded {len(pdf_files)} PDF(s) and {len(images)} image(s) that may contain relevant information.

When information is missing, infer realistic sample data that fits the context of the form. Return null only when explicitly instructed to leave a field empty.
Please analyze all provided context and generate appropriate values for each field while keeping answers fluent and human-sounding.
"""

        # Create multi-part content with user files
        content = create_multipart_query(
            query=query,
            pdf_files=pdf_files if pdf_files else None,
            images=images if images else None
        )

        # Run agent
        result = await generator_agent.run(
            user_id=user_id,
            state={},
            content=content,
            debug=False
        )

        return result

    async def _generate_form_values_ultra(
        self,
        user_id: str,
        field_groups: list,
        visible_text: str,
        clipboard_text: str,
        pdf_files: list,
        images: list,
        model: str
    ) -> dict:
        """
        Generate values for field groups individually with parallel execution (ultra mode).
        Processes each group separately with max 10 concurrent tasks.
        """
        from ..agents.utils import create_multipart_query
        import json

        logger.info(f"Starting ultra processing for {len(field_groups)} field groups")

        # Select pre-initialized agent based on model (reuse across all groups)
        generator_agent = self.generator_flash if model == "gemini-2.0-flash" else self.generator_pro

        # Create a semaphore to limit concurrent tasks to 10
        semaphore = asyncio.Semaphore(10)

        async def process_group(group_idx: int, group_fields: list):
            """Process a single field group."""
            async with semaphore:
                try:
                    logger.info(f"Processing field group {group_idx + 1}/{len(field_groups)}")

                    # Build query for this group
                    query = f"""Please generate appropriate values for the following form field group.
Follow these directives strictly:
- Treat clipboard content as authoritative instructions.
- Provide a best-effort value for every field; only return null when the user explicitly requests a blank or when no responsible inference is possible.
- For multiple-choice fields, select one of the provided options; for checkboxes output true/false for each required option.
- Keep values consistent with each other and respect validation hints or dependencies.

Form Fields:
```json
{json.dumps(group_fields, indent=2)}
```

Page Visible Text:
{visible_text}

Clipboard Content:
{clipboard_text if clipboard_text else 'No clipboard content provided'}

User has uploaded {len(pdf_files)} PDF(s) and {len(images)} image(s) that may contain relevant information.

When information is missing, infer realistic sample data that fits the context of the form. Return null only when explicitly instructed to leave a field empty.
Please analyze all provided context and generate appropriate values for each field in this group while keeping answers fluent and human-sounding.
"""

                    # Create multi-part content
                    content = create_multipart_query(
                        query=query,
                        pdf_files=pdf_files if pdf_files else None,
                        images=images if images else None
                    )

                    # Run agent for this group
                    result = await generator_agent.run(
                        user_id=user_id,
                        state={},
                        content=content,
                        debug=False
                    )

                    logger.info(f"Completed field group {group_idx + 1}/{len(field_groups)}")
                    return result

                except Exception as e:
                    logger.error(f"Error processing field group {group_idx}: {e}")
                    # Return null values for failed groups
                    return {"actions": [{"action_type": "fillText", "selector": "", "value": None, "label": f"Error in group {group_idx}"}]}

        # Process all groups in parallel with concurrency limit
        tasks = [process_group(idx, group) for idx, group in enumerate(field_groups)]
        results = await asyncio.gather(*tasks)

        # Combine all results into a single actions list
        combined_actions = []
        for result in results:
            if result and "actions" in result:
                combined_actions.extend(result["actions"])

        logger.info(f"Ultra processing complete: {len(combined_actions)} total actions from {len(field_groups)} groups")

        return {"actions": combined_actions}
