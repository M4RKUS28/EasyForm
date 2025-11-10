"""Agent service orchestrating parser and generator agents."""

import asyncio
import json
from dataclasses import dataclass
from logging import getLogger
from typing import Dict, List, Optional

from google.adk.sessions import InMemorySessionService

from ..agents.action_generator_agent import ActionGeneratorAgent
from ..agents.form_value_generator_agent import FormValueGeneratorAgent
from ..agents.html_form_parser_agent import HtmlFormParserAgent
from ..agents.solution_generator_agent import SolutionGeneratorAgent
from ..config import settings

logger = getLogger(__name__)


@dataclass(frozen=True)
class QualityProfile:
    parser_model: str
    solution_model: str  # Used for solution generation (step 2)
    action_model: str    # Used for action generation (step 3, matches parser for consistency)

    @property
    def generator_model(self) -> str:
        """Backward-compatible accessor for legacy generator agent."""
        return self.solution_model


DEFAULT_QUALITY = "fast"

MODEL_CONFIG: Dict[str, QualityProfile] = {
    "fast": QualityProfile(
        parser_model="gemini-2.5-flash",
        solution_model="gemini-2.5-flash",
        action_model="gemini-2.5-flash",
    ),
    "fast-pro": QualityProfile(
        parser_model="gemini-2.5-pro",
        solution_model="gemini-2.5-flash",
        action_model="gemini-2.5-pro",
    ),
    "exact": QualityProfile(
        parser_model="gemini-2.5-flash",
        solution_model="gemini-2.5-pro",
        action_model="gemini-2.5-flash",
    ),
    "exact-pro": QualityProfile(
        parser_model="gemini-2.5-pro",
        solution_model="gemini-2.5-pro",
        action_model="gemini-2.5-pro",
    ),
}


class AgentService:
    def __init__(self) -> None:
        self.session_service = InMemorySessionService()
        self.app_name = "EasyForm"

        logger.info("Initializing parser, solution, and action generator agents")

        # Parser agents
        self.parser_flash = HtmlFormParserAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.5-flash",
        )
        self.parser_pro = HtmlFormParserAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.5-pro",
        )

        # Solution generator agents (step 2: generate solutions per question)
        self.solution_flash = SolutionGeneratorAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.5-flash",
        )
        self.solution_pro = SolutionGeneratorAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.5-pro",
        )

        # Action generator agents (step 3: convert solutions to actions)
        self.action_flash = ActionGeneratorAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.5-flash",
        )
        self.action_pro = ActionGeneratorAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.5-pro",
        )

        # Legacy generator agents (deprecated, will be removed)
        self.generator_flash = FormValueGeneratorAgent(
            self.app_name,
            self.session_service,
            model="gemini-2.5-flash",
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
        quality: str = DEFAULT_QUALITY,
        personal_instructions: Optional[str] = None,
    ) -> dict:
        """Parse HTML to extract structured form questions for downstream processing."""

        from ..agents.utils import create_multipart_query

        profile = MODEL_CONFIG.get(quality, MODEL_CONFIG[DEFAULT_QUALITY])
        parser_agent = self.parser_flash if profile.parser_model == "gemini-2.5-flash" else self.parser_pro

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
        quality: str = DEFAULT_QUALITY,
        personal_instructions: Optional[str] = None,
    ) -> dict:
        """Generate actions for form questions using the Form Value Generator Agent."""

        profile = MODEL_CONFIG.get(quality, MODEL_CONFIG[DEFAULT_QUALITY])
        generator_model = profile.generator_model

        pdf_files: List[bytes] = []
        images: List[bytes] = []

        if user_files:
            for file in user_files:
                if file.content_type == "application/pdf":
                    pdf_files.append(file.data)
                elif file.content_type.startswith("image/"):
                    images.append(file.data)

        total_inputs = sum(len(question.get("inputs") or []) for question in questions)

        logger.info(
            "Using per-question processing with %s for %d questions (%d inputs)",
            generator_model,
            len(questions),
            total_inputs,
        )

        return await self._generate_form_values_per_question(
            user_id=user_id,
            questions=questions,
            visible_text=visible_text,
            clipboard_text=clipboard_text,
            pdf_files=pdf_files,
            images=images,
            model=generator_model,
            personal_instructions=personal_instructions,
        )

    async def _generate_form_values_per_question(
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
        """Generate actions question-by-question with parallel execution."""

        from ..agents.utils import create_multipart_query

        logger.info("Starting per-question processing for %d questions", len(questions))

        generator_agent = self.generator_flash if model == "gemini-2.5-flash" else self.generator_pro

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
            "Per-question processing complete: %d total actions generated from %d questions",
            len(combined_actions),
            len(questions),
        )

        return {"actions": combined_actions}

    async def generate_solutions_per_question(
        self,
        user_id: str,
        questions: list,
        visible_text: str,
        clipboard_text: str | None = None,
    user_files: list | None = None,
    quality: str = DEFAULT_QUALITY,
    personal_instructions: Optional[str] = None,
    question_contexts: Optional[Dict[str, Dict[str, List]]] = None,
    screenshots: Optional[List[bytes]] = None,
    ) -> List[Dict]:
        """
        Generate solutions for each question using Solution Generator Agent.
        Returns a list of dicts with question_id and solution.

        Args:
            user_id: User ID
            questions: List of questions from parser
            visible_text: Visible page text
            clipboard_text: Session instructions
            user_files: User uploaded files (direct mode)
            quality: Quality profile
            personal_instructions: User personal instructions
            question_contexts: Optional mapping of question_id -> RAG context payload
            screenshots: Screenshots from browser (passed directly, not via RAG)
        """
        from ..agents.utils import create_multipart_query

        profile = MODEL_CONFIG.get(quality, MODEL_CONFIG[DEFAULT_QUALITY])
        solution_model = profile.solution_model

        # Collect context sources
        pdf_files: List[bytes] = []
        direct_images: List[bytes] = []

        # Option 1: Direct file context (when not using RAG)
        if user_files:
            for file in user_files:
                if file.content_type == "application/pdf":
                    pdf_files.append(file.data)
                elif file.content_type.startswith("image/"):
                    direct_images.append(file.data)

        logger.info(
            "Generating solutions for %d questions using %s",
            len(questions),
            solution_model,
        )

        solution_agent = self.solution_flash if solution_model == "gemini-2.5-flash" else self.solution_pro
        instructions_text = personal_instructions or "No personal instructions provided."

        semaphore = asyncio.Semaphore(10)

        async def process_question(question_idx: int, question: dict):
            async with semaphore:
                try:
                    logger.info(
                        "Generating solution for question %d/%d -> id=%s | type=%s | title=%s",
                        question_idx + 1,
                        len(questions),
                        question.get("question_id"),
                        question.get("question_type"),
                        question.get("title"),
                    )

                    # Build context section based on RAG or direct files
                    context_info: List[str] = []

                    # Prepare per-question assets
                    question_id = str(question.get("question_id") or question_idx)
                    per_question_context = (question_contexts or {}).get(question_id)

                    images: List[bytes] = list(direct_images)
                    if screenshots:
                        images.extend(screenshots)

                    if per_question_context:
                        text_chunks = per_question_context.get("text_chunks", [])
                        if text_chunks:
                            context_info.append(
                                f"Retrieved {len(text_chunks)} relevant text sections from your documents:"
                            )
                            for i, chunk in enumerate(text_chunks[:5], 1):
                                source = chunk.get("source", "Unknown")
                                content = chunk.get("content", "")[:500]
                                context_info.append(f"{i}. From {source}:\n{content}\n")

                        image_chunks = per_question_context.get("image_chunks", [])
                        if image_chunks:
                            context_info.append(
                                f"Retrieved {len(image_chunks)} relevant image(s) from your documents (shown below)."
                            )
                            for img_chunk in image_chunks:
                                image_bytes = img_chunk.get("image_bytes")
                                if image_bytes:
                                    images.append(image_bytes)
                        if not text_chunks and not image_chunks:
                            context_info.append("No relevant document excerpts were retrieved for this question.")
                    else:
                        if len(pdf_files) > 0 or len(direct_images) > 0:
                            context_info.append(
                                f"User has uploaded {len(pdf_files)} PDF(s) and {len(direct_images)} image(s) that may contain relevant information."
                            )

                    context_section = "\n".join(context_info) if context_info else "No uploaded documents available."

                    solution_query = f"""Analyze the following form question and provide an appropriate solution/answer.



Session Instructions (highest priority):
{clipboard_text if clipboard_text else 'No session instructions provided'}

Personal Instructions:
{instructions_text}

Document Context:
{context_section}


----------------------------------------


Form Question:
```json
{json.dumps(question, indent=2)}
```

Provide only the solution/answer as plain text. Do not include explanations unless necessary.
"""

                    content = create_multipart_query(
                        query=solution_query,
                        pdf_files=pdf_files if pdf_files else None,
                        images=images if images else None,
                    )

                    logger.info(
                        "Step 2 input payload for question_id=%s: %s",
                        question.get("question_id"),
                        solution_query,
                    )
                    logger.info(
                        "Step 2 attachment summary for question_id=%s: pdfs=%d | images=%d",
                        question.get("question_id"),
                        len(pdf_files),
                        len(images),
                    )

                    result = await solution_agent.run(
                        user_id=user_id,
                        state={},
                        content=content,
                        debug=False,
                        max_retries=settings.AGENT_MAX_RETRIES,
                        retry_delay=settings.AGENT_RETRY_DELAY_SECONDS,
                    )

                    logger.info(
                        "Step 2 output payload for question_id=%s: %s",
                        question.get("question_id"),
                        result,
                    )

                    logger.info(
                        "Solution generated for question %d/%d",
                        question_idx + 1,
                        len(questions),
                    )

                    # Extract solution from result
                    solution = None
                    if result.get("status") == "success":
                        solution = result.get("output", "")
                    elif "output" in result:
                        solution = result["output"]
                    else:
                        solution = "Error: Could not generate solution"

                    return {
                        "question_id": question.get("question_id"),
                        "question": question,
                        "solution": solution,
                    }

                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Error generating solution for question %d/%d: %s",
                        question_idx + 1,
                        len(questions),
                        exc,
                    )
                    return {
                        "question_id": question.get("question_id"),
                        "question": question,
                        "solution": "Error: Failed to generate solution",
                    }

        tasks = [process_question(idx, question) for idx, question in enumerate(questions)]
        results = await asyncio.gather(*tasks)

        logger.info("Solution generation complete for %d questions", len(results))
        return results

    async def generate_actions_from_solutions(
        self,
        user_id: str,
        question_solution_pairs: List[Dict],
        quality: str = DEFAULT_QUALITY,
        batch_size: int = 10,
    ) -> dict:
        """
        Generate actions from question-solution pairs using Action Generator Agent.
        Processes questions in batches to optimize API calls.

        Args:
            user_id: User ID
            question_solution_pairs: List of dicts with 'question' and 'solution' keys
            quality: Quality profile
            batch_size: Number of questions to process per batch (default: 10)

        Returns:
            Dict with 'actions' key containing list of all generated actions
        """
        profile = MODEL_CONFIG.get(quality, MODEL_CONFIG[DEFAULT_QUALITY])
        action_model = profile.action_model

        action_agent = self.action_flash if action_model == "gemini-2.5-flash" else self.action_pro

        logger.info(
            "Generating actions from %d question-solution pairs using %s (batch_size=%d)",
            len(question_solution_pairs),
            action_model,
            batch_size,
        )

        # Split into batches
        batches = [
            question_solution_pairs[i:i + batch_size]
            for i in range(0, len(question_solution_pairs), batch_size)
        ]

        logger.info("Processing %d batches", len(batches))

        async def process_batch(batch_idx: int, batch: List[Dict]):
            try:
                logger.info(
                    "Processing batch %d/%d with %d questions",
                    batch_idx + 1,
                    len(batches),
                    len(batch),
                )

                # Build the query with all questions and solutions
                questions_data = []
                for idx, item in enumerate(batch):
                    question = item["question"]
                    solution = item["solution"]
                    questions_data.append({
                        "index": idx + 1,
                        "question_id": question.get("question_id"),
                        "question_type": question.get("question_type"),
                        "title": question.get("title"),
                        "description": question.get("description"),
                        "context": question.get("context"),
                        "hints": question.get("hints"),
                        "inputs": question.get("inputs", []),
                        "metadata": question.get("metadata"),
                        "solution": solution,
                    })

                action_query = f"""Convert the following form questions and their solutions into precise browser actions.

Questions and Solutions:
```json
{json.dumps(questions_data, indent=2)}
```

For each question:
1. Read the solution
2. Match the solution to the appropriate inputs
3. Generate the correct actions using the exact selectors provided

Output a flat list of all actions across all questions.
"""

                from ..agents.utils import create_multipart_query
                content = create_multipart_query(query=action_query)

                logger.info(
                    "Step 3 input payload for batch %d: %s",
                    batch_idx + 1,
                    action_query,
                )

                result = await action_agent.run(
                    user_id=user_id,
                    state={},
                    content=content,
                    debug=False,
                    max_retries=settings.AGENT_MAX_RETRIES,
                    retry_delay=settings.AGENT_RETRY_DELAY_SECONDS,
                )

                logger.info(
                    "Step 3 output payload for batch %d: %s",
                    batch_idx + 1,
                    result,
                )

                logger.info(
                    "Batch %d/%d completed",
                    batch_idx + 1,
                    len(batches),
                )

                return result

            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Error processing batch %d/%d: %s",
                    batch_idx + 1,
                    len(batches),
                    exc,
                )
                return {"actions": []}

        tasks = [process_batch(idx, batch) for idx, batch in enumerate(batches)]
        batch_results = await asyncio.gather(*tasks)

        # Combine all actions from all batches
        combined_actions: List[dict] = []
        for result in batch_results:
            if result and "actions" in result:
                combined_actions.extend(result["actions"])

        logger.info(
            "Action generation complete: %d total actions from %d questions",
            len(combined_actions),
            len(question_solution_pairs),
        )

        return {"actions": combined_actions}

