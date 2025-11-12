"""Agent service orchestrating parser and generator agents."""

import asyncio
import json
from dataclasses import dataclass
from logging import getLogger
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

from google.adk.sessions import InMemorySessionService
from sqlalchemy.ext.asyncio import AsyncSession

from ..agents.action_generator_agent import ActionGeneratorAgent
from ..agents.html_form_parser_agent import HtmlFormParserAgent
from ..agents.solution_generator_agent import SolutionGeneratorAgent
from ..config import settings
from ..db.database import get_async_db_context
from .question_filter import extract_question_data_for_agent_2, filter_question_solution_pairs_for_agent_3
from .rag_service import RAGService
from ..agents.utils import create_multipart_query


logger = getLogger(__name__)


@dataclass(frozen=True)
class QualityProfile:
    parser_model: str
    solution_model: str  # Used for solution generation (step 2)
    action_model: str    # Used for action generation (step 3, matches parser for consistency)



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


def _build_search_query_for_question(question: dict, max_inputs: int = 10) -> str:
    """Compose a semantic RAG search query from structured Agent 1 output."""

    phrases: List[str] = []

    def add_text(value: Optional[str]) -> None:
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                phrases.append(trimmed)

    def add_iterable(values: Optional[List[Any]]) -> None:
        if isinstance(values, list):
            for entry in values[:max_inputs]:
                if isinstance(entry, str):
                    add_text(entry)

    question_data = question.get("question_data")
    if isinstance(question_data, dict):
        add_text(question_data.get("question"))
        add_text(question_data.get("additional_information"))
        add_iterable(question_data.get("available_options"))

    sanitized = [phrase for phrase in phrases if phrase]
    return " ".join(sanitized).strip() or "form question context"


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

    async def generate_solutions_per_question(
        self,
        user_id: str,
        questions: list,
        #visible_text: str,
        clipboard_text: str | None = None,
        quality: str = DEFAULT_QUALITY,
        personal_instructions: Optional[str] = None,
        rag_service: Optional[RAGService] = None,
        rag_top_k: int = 10,
        file_logger: Optional[Any] = None,
        progress_callback: Optional[Callable[[int, int, Dict[str, Any]], Awaitable[None]]] = None,
        #screenshots: Optional[List[bytes]] = None,
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
            rag_service: Optional RAG service for per-question retrieval
            rag_top_k: Number of RAG chunks to retrieve per question
            file_logger: Optional file logger for per-question logging
            screenshots: Screenshots from browser (passed directly, not via RAG)
            progress_callback: Optional coroutine fired when each question completes
        """

        profile = MODEL_CONFIG.get(quality, MODEL_CONFIG[DEFAULT_QUALITY])
        solution_model = profile.solution_model

        # Collect context sources
        pdf_files: List[bytes] = []
        direct_images: List[bytes] = []

        logger.info(
            "Generating solutions for %d questions using %s",
            len(questions),
            solution_model,
        )

        solution_agent = self.solution_flash if solution_model == "gemini-2.5-flash" else self.solution_pro
        instructions_text = personal_instructions or "No personal instructions provided."

        semaphore = asyncio.Semaphore(10)
        if not rag_service:
            raise ValueError("RAG service must be provided for solution generation.")
        rag_totals: Dict[str, int] = {"text": 0, "image": 0}
        rag_totals_lock = asyncio.Lock()

        async def process_question(question_idx: int, question: dict):
            callback_payload: Dict[str, Any] = {
                "question_id": question.get("question_id"),
                "title": question.get("title"),
            }
            async with semaphore:
                success = False
                solution_text: str = "Error: Could not generate solution"
                agent_output: Dict[str, Any] = {}
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
                    subdir = f"question_{question_idx}"

                    # Agent 2 (Solution Generator) only gets context images, NOT screenshots
                    # Screenshots are only for Agent 1 (Parser)
                    images: List[bytes] = list(direct_images)

                    # RAG retrieval per question
                    question_query = _build_search_query_for_question(question)
                    question_id = str(question.get("question_id") or question.get("id") or question_idx)

                    if file_logger:
                        file_logger.log_rag_query(
                            f"Question {question_id}: {question_query}",
                            subdir=subdir,
                        )

                    async with get_async_db_context() as rag_db:
                        db_session = cast(AsyncSession, rag_db)
                        context = await rag_service.retrieve_relevant_context(
                            db=db_session,
                            query=question_query,
                            user_id=user_id,
                            top_k=rag_top_k,
                            file_logger=file_logger,
                            question_subdir=subdir,
                        )

                    if file_logger:
                        file_logger.log_rag_response(context, subdir=subdir)

                    text_chunks = context.get("text_chunks", [])
                    image_chunks = context.get("image_chunks", [])

                    if rag_totals_lock:
                        async with rag_totals_lock:
                            rag_totals["text"] += len(text_chunks)
                            rag_totals["image"] += len(image_chunks)

                    if file_logger:
                        file_logger.log_rag_chunk_counts(
                            text_chunks=len(text_chunks),
                            image_chunks=len(image_chunks),
                            scope=f"question_{question_id}",
                            subdir=subdir,
                        )

                    logger.info(
                        "Question %s RAG context: %d text chunks, %d image chunks",
                        question_id,
                        len(text_chunks),
                        len(image_chunks),
                    )

                    if text_chunks:
                        context_info.append(
                            f"Retrieved {len(text_chunks)} relevant text sections from your documents:"
                        )
                        for i, chunk in enumerate(text_chunks[:5], 1):
                            source = chunk.get("source", "Unknown")
                            content = chunk.get("content", "")[:500]
                            context_info.append(f"{i}. From {source}:\n{content}\n")

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

                    context_section = "\n".join(context_info) if context_info else "No uploaded documents available."

                    # Filter question to only include question_data for Agent 2
                    filtered_question = extract_question_data_for_agent_2(question)

                    if file_logger:
                        question_json = json.dumps(filtered_question, indent=2, ensure_ascii=False)
                        file_logger.log_agent_query(2, question_json, subdir=subdir)
                        file_logger.log_agent_output(
                            2,
                            (
                                f"Generating solution for question {question_idx} "
                                f"(id={question.get('question_id')})"
                            ),
                            subdir=subdir,
                        )

                    solution_query = f"""Analyze the following form question and provide an appropriate solution/answer.




{("Session Instructions (highest priority): " + clipboard_text) if clipboard_text else ''}

{("Personal Instructions: " + instructions_text) if instructions_text else ''}

{("Document Context:\n") if context_section else ''}

{context_section}

----------------------------------------

Solve and answer following Form Question:
```json
{json.dumps(filtered_question, indent=2)}
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
                    agent_output = result

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
                        solution_text = result.get("output", "")
                    elif "output" in result:
                        solution_text = result["output"]
                    else:
                        solution_text = "Error: Could not generate solution"
                    success = True

                    if file_logger:
                        file_logger.log_agent_response(
                            2,
                            {
                                "question_id": question.get("question_id"),
                                "question": question,
                                "solution": solution_text,
                                "agent_output": result,
                            },
                            subdir=subdir,
                        )

                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Error generating solution for question %d/%d: %s",
                        question_idx + 1,
                        len(questions),
                        exc,
                    )
                    solution_text = "Error: Failed to generate solution"
                    agent_output = {"status": "error", "detail": str(exc)}
                finally:
                    if progress_callback:
                        progress_payload = {
                            **callback_payload,
                            "success": success,
                            "question_number": question_idx + 1,
                            "total_questions": len(questions),
                        }
                        if not success:
                            progress_payload["error"] = agent_output.get("detail")
                        try:
                            await progress_callback(question_idx + 1, len(questions), progress_payload)
                        except Exception as progress_exc:  # noqa: BLE001
                            logger.warning(
                                "Progress callback failed for question %s: %s",
                                question.get("question_id"),
                                progress_exc,
                            )

                return {
                    "question_id": question.get("question_id"),
                    "question": question,
                    "solution": solution_text,
                    "agent_output": agent_output,
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

                # Build the query with filtered questions and solutions
                # Agent 3 only needs interaction_data (selectors/targets), not semantic data
                questions_data = []
                for idx, item in enumerate(batch):
                    question = item["question"]
                    solution = item["solution"]

                    # Filter question to only include interaction_data for Agent 3
                    if "interaction_data" in question:
                        # New schema
                        questions_data.append({
                            "index": idx + 1,
                            "id": question.get("id"),
                            "type": question.get("type"),
                            "interaction_data": question.get("interaction_data"),
                            "solution": solution,
                        })
                    else:
                        # Old schema fallback
                        questions_data.append({
                            "index": idx + 1,
                            "question_id": question.get("question_id"),
                            "question_type": question.get("question_type"),
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

