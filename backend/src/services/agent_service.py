"""Agent service orchestrating parser and generator agents."""

import asyncio
import json
from logging import getLogger
from typing import Dict, List, Optional, Tuple

from google.adk.sessions import InMemorySessionService

from ..agents.form_value_generator_agent import FormValueGeneratorAgent
from ..agents.html_form_parser_agent import HtmlFormParserAgent
from ..config import settings

logger = getLogger(__name__)


MODEL_CONFIG: Dict[str, Tuple[str, str, bool]] = {
    "fast": ("gemini-2.0-flash", "gemini-2.0-flash", False),
    "fast-ultra": ("gemini-2.0-flash", "gemini-2.0-flash", True),
    "medium": ("gemini-2.0-flash", "gemini-2.5-pro", False),
    "medium-ultra": ("gemini-2.0-flash", "gemini-2.5-pro", True),
    "exact": ("gemini-2.5-pro", "gemini-2.5-pro", False),
    "exact-ultra": ("gemini-2.5-pro", "gemini-2.5-pro", True),
}


class AgentService:
    def __init__(self) -> None:
        self.session_service = InMemorySessionService()
        self.app_name = "EasyForm"

        logger.info("Initializing parser and generator agents")
        self.parser_flash = HtmlFormParserAgent(self.app_name, self.session_service, model="gemini-2.0-flash")
        self.parser_pro = HtmlFormParserAgent(self.app_name, self.session_service, model="gemini-2.5-pro")
        self.generator_flash = FormValueGeneratorAgent(self.app_name, self.session_service, model="gemini-2.0-flash")
        self.generator_pro = FormValueGeneratorAgent(self.app_name, self.session_service, model="gemini-2.5-pro")
        logger.info("Agents initialized successfully")

    async def parse_form_structure(
        self,
        user_id: str,
        html: str,
        dom_text: str,
        clipboard_text: Optional[str] = None,
        screenshots: Optional[List[bytes]] = None,
        quality: str = "medium",
        personal_instructions: Optional[str] = None,
    ) -> dict:
        """Parse HTML form structure using the parser agent."""

        from ..agents.utils import create_multipart_query

        step1_model, _, _ = MODEL_CONFIG.get(quality, MODEL_CONFIG["medium"])
        parser_agent = self.parser_flash if step1_model == "gemini-2.0-flash" else self.parser_pro

        instructions_text = personal_instructions or "No personal instructions provided."

        query = f"""Please analyze the following HTML and extract all form fields.
Group related fields together when appropriate (e.g., address fields, name fields).

HTML Code:
```html
{html}
```

Visible Text Content:
{dom_text}

Clipboard Content:
{clipboard_text if clipboard_text else 'No clipboard content provided'}

Personal Instructions:
{instructions_text}
"""

        content = create_multipart_query(
            query=query,
            screenshots=screenshots if screenshots else None,
        )

        result = await parser_agent.run(
            user_id=user_id,
            state={},
            content=content,
            debug=False,
            max_retries=settings.AGENT_MAX_RETRIES,
            retry_delay=settings.AGENT_RETRY_DELAY_SECONDS,
        )
        return result

    async def generate_form_values(
        self,
        user_id: str,
        fields: list,
        visible_text: str,
        clipboard_text: str | None = None,
        user_files: list | None = None,
        quality: str = "medium",
        personal_instructions: Optional[str] = None,
    ) -> dict:
        """Generate values for form fields using the Form Value Generator Agent."""
        from ..agents.utils import create_multipart_query

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
            logger.info(f"Using ultra processing mode with {step2_model} for {len(fields)} field groups")
            return await self._generate_form_values_ultra(
                user_id=user_id,
                field_groups=fields,
                visible_text=visible_text,
                clipboard_text=clipboard_text,
                pdf_files=pdf_files,
                images=images,
                model=step2_model,
                personal_instructions=personal_instructions,
            )

        logger.info(f"Using regular processing mode with {step2_model} for {len(fields)} field groups")
        return await self._generate_form_values_batch(
            user_id=user_id,
            fields=fields,
            visible_text=visible_text,
            clipboard_text=clipboard_text,
            pdf_files=pdf_files,
            images=images,
            model=step2_model,
            personal_instructions=personal_instructions,
        )

    async def _generate_form_values_batch(
        self,
        user_id: str,
        fields: list,
        visible_text: str,
        clipboard_text: str | None,
        pdf_files: list,
        images: list,
        model: str,
        personal_instructions: Optional[str] = None,
    ) -> dict:
        """Generate values for all fields in a single batch (regular mode)."""
        from ..agents.utils import create_multipart_query

        generator_agent = self.generator_flash if model == "gemini-2.0-flash" else self.generator_pro

        instructions_text = personal_instructions or "No personal instructions provided."

        query = f"""Please generate appropriate values for the following form fields.
Follow these directives strictly:
- Treat clipboard content as authoritative instructions.
- Blend the user's personal instructions with any other context when deciding on values.
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

Personal Instructions:
{instructions_text}

User has uploaded {len(pdf_files)} PDF(s) and {len(images)} image(s) that may contain relevant information.

When information is missing, infer realistic sample data that fits the context of the form. Return null only when explicitly instructed to leave a field empty.
Please analyze all provided context and generate appropriate values for each field while keeping answers fluent and human-sounding.
"""

        content = create_multipart_query(
            query=query,
            pdf_files=pdf_files if pdf_files else None,
            images=images if images else None
        )

        result = await generator_agent.run(
            user_id=user_id,
            state={},
            content=content,
            debug=False,
            max_retries=settings.AGENT_MAX_RETRIES,
            retry_delay=settings.AGENT_RETRY_DELAY_SECONDS,
        )

        return result

    async def _generate_form_values_ultra(
        self,
        user_id: str,
        field_groups: list,
        visible_text: str,
        clipboard_text: str | None,
        pdf_files: list,
        images: list,
        model: str,
        personal_instructions: Optional[str] = None,
    ) -> dict:
        """Generate values for field groups individually with parallel execution (ultra mode)."""
        from ..agents.utils import create_multipart_query

        logger.info(f"Starting ultra processing for {len(field_groups)} field groups")

        generator_agent = self.generator_flash if model == "gemini-2.0-flash" else self.generator_pro

        instructions_text = personal_instructions or "No personal instructions provided."

        semaphore = asyncio.Semaphore(10)

        async def process_group(group_idx: int, group_fields: list):
            async with semaphore:
                try:
                    logger.info(f"Processing field group {group_idx + 1}/{len(field_groups)}")

                    query = f"""Please generate appropriate values for the following form field group.
Follow these directives strictly:
- Treat clipboard content as authoritative instructions.
- Blend the user's personal instructions with any other context when deciding on values.
- Provide a best-effort value for every field; only return null when the user explicitly requests a blank or when no responsible inference is possible.
- Keep values consistent with each other and respect validation hints or dependencies.

Form Fields:
```json
{json.dumps(group_fields, indent=2)}
```

Page Visible Text:
{visible_text}

Clipboard Content:
{clipboard_text if clipboard_text else 'No clipboard content provided'}

Personal Instructions:
{instructions_text}

User has uploaded {len(pdf_files)} PDF(s) and {len(images)} image(s) that may contain relevant information.

When information is missing, infer realistic sample data that fits the context of the form. Return null only when explicitly instructed to leave a field empty.
Please analyze all provided context and generate appropriate values for each field in this group while keeping answers fluent and human-sounding.
"""

                    content = create_multipart_query(
                        query=query,
                        pdf_files=pdf_files if pdf_files else None,
                        images=images if images else None
                    )

                    result = await generator_agent.run(
                        user_id=user_id,
                        state={},
                        content=content,
                        debug=False,
                        max_retries=settings.AGENT_MAX_RETRIES,
                        retry_delay=settings.AGENT_RETRY_DELAY_SECONDS,
                    )

                    logger.info(f"Completed field group {group_idx + 1}/{len(field_groups)}")
                    return result

                except Exception as e:
                    logger.error(f"Error processing field group {group_idx}: {e}")
                    return {"actions": [{"action_type": "fillText", "selector": "", "value": None, "label": f"Error in group {group_idx}"}]}

        tasks = [process_group(idx, group) for idx, group in enumerate(field_groups)]
        results = await asyncio.gather(*tasks)

        combined_actions = []
        for result in results:
            if result and "actions" in result:
                combined_actions.extend(result["actions"])

        logger.info(f"Ultra processing complete: {len(combined_actions)} total actions from {len(field_groups)} groups")

        return {"actions": combined_actions}

