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
        self.parser_flash = HtmlFormParserAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.0-flash",
        )
        self.parser_pro = HtmlFormParserAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.5-pro",
        )
        self.generator_flash = FormValueGeneratorAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.0-flash",
        )
        self.generator_pro = FormValueGeneratorAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.5-pro",
        )
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
        """Parse HTML to extract structured form questions for downstream processing."""

        from ..agents.utils import create_multipart_query

        step1_model, _, _ = MODEL_CONFIG.get(quality, MODEL_CONFIG["medium"])
        parser_agent = self.parser_flash if step1_model == "gemini-2.0-flash" else self.parser_pro

        instructions_text = personal_instructions or "No personal instructions provided."

        query = f"""Please analyze the following HTML and describe every form question with its inputs and context.
Follow these directives:
- Group inputs into a single question when they belong together (e.g., name, address, date ranges).
- Capture helpful metadata such as labels, hints, validation cues, dependencies, and any detected existing values.
- Use the JSON structure specified in your system instructions and avoid inventing fields not grounded in the HTML.

HTML Code:
```html
{html}
```

Visible Text Content:
{dom_text}

Session Instructions:
{clipboard_text if clipboard_text else 'No session instructions provided'}

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
        questions: list,
        visible_text: str,
        clipboard_text: str | None = None,
        user_files: list | None = None,
        quality: str = "medium",
        personal_instructions: Optional[str] = None,
    ) -> dict:
        """Generate actions for form questions using the Form Value Generator Agent."""

        _, step2_model, is_ultra = MODEL_CONFIG.get(quality, MODEL_CONFIG["medium"])

        pdf_files: List[bytes] = []
        images: List[bytes] = []

        if user_files:
            for file in user_files:
                if file.content_type == "application/pdf":
                    pdf_files.append(file.data)
                elif file.content_type.startswith("image/"):
                    images.append(file.data)

        total_inputs = sum(len(question.get("inputs") or []) for question in questions)

        if is_ultra:
            logger.info(
                "Using ultra processing mode with %s for %d questions (%d inputs)",
                step2_model,
                len(questions),
                total_inputs,
            )
            return await self._generate_form_values_ultra_questions(
                user_id=user_id,
                questions=questions,
                visible_text=visible_text,
                clipboard_text=clipboard_text,
                pdf_files=pdf_files,
                images=images,
                model=step2_model,
                personal_instructions=personal_instructions,
            )

        logger.info(
            "Using regular processing mode with %s for %d questions (%d inputs)",
            step2_model,
            len(questions),
            total_inputs,
        )

        return await self._generate_form_values_batch_questions(
            user_id=user_id,
            questions=questions,
            visible_text=visible_text,
            clipboard_text=clipboard_text,
            pdf_files=pdf_files,
            images=images,
            model=step2_model,
            personal_instructions=personal_instructions,
        )

    async def _generate_form_values_batch_questions(
        self,
        user_id: str,
        questions: list,
        visible_text: str,
        clipboard_text: str | None,
        pdf_files: List[bytes],
        images: List[bytes],
        model: str,
        personal_instructions: Optional[str] = None,
    ) -> dict:
        """Generate actions for all questions in a single batch (regular mode)."""

        from ..agents.utils import create_multipart_query

        generator_agent = self.generator_flash if model == "gemini-2.0-flash" else self.generator_pro

        instructions_text = personal_instructions or "No personal instructions provided."

        max_question_log = 25
        for idx, question in enumerate(questions[:max_question_log]):
            logger.info(
                "Generator batch question[%d]: id=%s | type=%s | title=%s | inputs=%d",
                idx,
                question.get("question_id"),
                question.get("question_type"),
                question.get("title"),
                len(question.get("inputs") or []),
            )

        if len(questions) > max_question_log:
            logger.info(
                "Generator batch question log truncated at %d of %d entries",
                max_question_log,
                len(questions),
            )

        query = f"""Please generate appropriate actions for the following form questions.
Follow these directives strictly:
- Treat session instructions as authoritative guidance.
- Respect existing answers noted via `current_value` fields and avoid redundant actions.
- Provide best-effort answers when required; only return null when explicitly instructed to leave a question blank or when no responsible answer exists.
- Keep responses mutually consistent and honor validation hints and constraints.

Form Questions (structured data from HTML analysis):
```json
{json.dumps(questions, indent=2)}
```

Page Visible Text:
{visible_text}

Session Instructions:
{clipboard_text if clipboard_text else 'No session instructions provided'}

Personal Instructions:
{instructions_text}

User has uploaded {len(pdf_files)} PDF(s) and {len(images)} image(s) that may contain relevant information.

When information is missing, infer realistic sample data that fits the context of the form. Return null only when explicitly instructed to leave a question blank or when no responsible answer exists.
Analyze every question, decide whether an action is required, and produce concise, human-sounding answers.
"""

        content = create_multipart_query(
            query=query,
            pdf_files=pdf_files if pdf_files else None,
            images=images if images else None,
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

    async def _generate_form_values_ultra_questions(
        self,
        user_id: str,
        questions: list,
        visible_text: str,
        clipboard_text: str | None,
        pdf_files: List[bytes],
        images: List[bytes],
        model: str,
        personal_instructions: Optional[str] = None,
    ) -> dict:
        """Generate actions question-by-question with parallel execution (ultra mode)."""

        from ..agents.utils import create_multipart_query

        logger.info("Starting ultra processing for %d questions", len(questions))

        generator_agent = self.generator_flash if model == "gemini-2.0-flash" else self.generator_pro

        instructions_text = personal_instructions or "No personal instructions provided."

        semaphore = asyncio.Semaphore(10)

        async def process_question(question_idx: int, question: dict):
            async with semaphore:
                try:
                    logger.info(
                        "Processing question %d/%d -> id=%s | type=%s | title=%s | inputs=%d",
                        question_idx + 1,
                        len(questions),
                        question.get("question_id"),
                        question.get("question_type"),
                        question.get("title"),
                        len(question.get("inputs") or []),
                    )

                    question_query = f"""Please generate appropriate actions for the following form question.
Follow these directives strictly:
- Treat session instructions as authoritative guidance.
- Respect existing answers noted via `current_value` fields and avoid redundant work.
- Provide the best possible answer consistent with all hints and constraints.

Form Question:
```json
{json.dumps(question, indent=2)}
```

Page Visible Text:
{visible_text}

Session Instructions:
{clipboard_text if clipboard_text else 'No session instructions provided'}

Personal Instructions:
{instructions_text}

User has uploaded {len(pdf_files)} PDF(s) and {len(images)} image(s) that may contain relevant information.

When information is missing, infer realistic sample data that fits the context of the form. Return null only when explicitly instructed to leave the input unchanged.
Generate concise, human-sounding answers for the required inputs.
"""

                    content = create_multipart_query(
                        query=question_query,
                        pdf_files=pdf_files if pdf_files else None,
                        images=images if images else None,
                    )

                    result = await generator_agent.run(
                        user_id=user_id,
                        state={},
                        content=content,
                        debug=False,
                        max_retries=settings.AGENT_MAX_RETRIES,
                        retry_delay=settings.AGENT_RETRY_DELAY_SECONDS,
                    )

                    logger.info(
                        "Completed question %d/%d",
                        question_idx + 1,
                        len(questions),
                    )
                    return result

                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Error processing question %d/%d: %s",
                        question_idx + 1,
                        len(questions),
                        exc,
                    )
                    return {
                        "actions": [
                            {
                                "action_type": "fillText",
                                "selector": "",
                                "value": None,
                                "label": f"Error in question {question_idx}",
                            }
                        ]
                    }

        tasks = [process_question(idx, question) for idx, question in enumerate(questions)]
        results = await asyncio.gather(*tasks)

        combined_actions: List[dict] = []
        for result in results:
            if result and "actions" in result:
                combined_actions.extend(result["actions"])

        logger.info(
            "Ultra processing complete: %d total actions generated from %d questions",
            len(combined_actions),
            len(questions),
        )

        return {"actions": combined_actions}

