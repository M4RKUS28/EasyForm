"""
Service for form analysis and field value generation.

This service analyzes HTML forms and generates appropriate values
using AI and user context (uploaded files).
"""
import asyncio
import base64
import logging
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import form as form_schema
from ..db.crud import files_crud, form_requests_crud, users_crud
from ..db.database import get_async_db_context
from .agent_service import AgentService
from .rag_service import get_rag_service
from .file_logger import create_file_logger
from ..config import settings

logger = logging.getLogger(__name__)

# Singleton instance of AgentService
_agent_service = None


def get_agent_service() -> AgentService:
    """Get or create the singleton AgentService instance."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


_active_analysis_tasks: Dict[str, asyncio.Task] = {}


def _sanitize_prompt_text(text: Optional[str], *, collapse_whitespace: bool = True) -> Optional[str]:
    if text is None:
        return None
    sanitized = text.replace("\r\n", "\n").replace("\r", "\n")
    sanitized = sanitized.replace("\t", " ").replace("\x0c", " ")
    if collapse_whitespace:
        sanitized = re.sub(r"[ \u00a0]{2,}", " ", sanitized)
    sanitized = re.sub(r"\n{3,}", "\n\n", sanitized)
    sanitized = sanitized.strip()
    return sanitized


def _clean_text_block(text: Optional[str], *, preserve_newlines: bool) -> Optional[str]:
    if text is None:
        return None
    text_str = str(text)
    normalized = text_str.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\t", " ").replace("\f", " ").replace("\u00a0", " ")
    if preserve_newlines:
        normalized = re.sub(r"[ \u00a0]{2,}", " ", normalized)
        normalized = re.sub(r"[ \u00a0]*\n[ \u00a0]*", "\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    else:
        normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _clean_label_text(text: Optional[str]) -> Optional[str]:
    return _clean_text_block(text, preserve_newlines=False)


def _normalize_parser_question(question: dict) -> dict:
    """Sanitize parser output so question metadata and inputs remain consistent."""

    normalized = dict(question)

    inline_keys = ("title",)
    for key in inline_keys:
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = _clean_label_text(value)

    block_keys = ("description", "context")
    for key in block_keys:
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = _clean_text_block(value, preserve_newlines=True)

    hints = normalized.get("hints")
    if isinstance(hints, list):
        cleaned_hints = []
        for hint in hints:
            if isinstance(hint, str):
                cleaned_hint = _clean_text_block(hint, preserve_newlines=False)
                if cleaned_hint:
                    cleaned_hints.append(cleaned_hint)
        normalized["hints"] = cleaned_hints

    inputs = normalized.get("inputs") or []
    cleaned_inputs: List[dict] = []
    for raw_input in inputs:
        cleaned_input = _normalize_question_input(raw_input)
        if cleaned_input:
            cleaned_inputs.append(cleaned_input)
    normalized["inputs"] = cleaned_inputs

    return normalized


def _normalize_question_input(input_data: Any) -> Optional[dict]:
    if not isinstance(input_data, dict):
        return None

    normalized = dict(input_data)

    label_like_keys = ("option_label",)
    for key in label_like_keys:
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = _clean_label_text(value)

    block_keys = ("current_value", "constraints", "notes")
    for key in block_keys:
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = _clean_text_block(value, preserve_newlines=True)

    value_hint = normalized.get("value_hint")
    if isinstance(value_hint, str):
        normalized["value_hint"] = _clean_text_block(value_hint, preserve_newlines=False)

    return normalized


def _extract_sanitized_inputs(request_data: form_schema.FormAnalyzeRequest) -> Tuple[str, str, str]:
    html_clean = _sanitize_prompt_text(request_data.html, collapse_whitespace=False) or ""
    visible_clean = _sanitize_prompt_text(request_data.visible_text) or ""
    clipboard_clean = _sanitize_prompt_text(request_data.clipboard_text) or ""
    return html_clean, visible_clean, clipboard_clean


def schedule_form_analysis_task(
    request_id: str,
    user_id: str,
    request_data: form_schema.FormAnalyzeRequest,
) -> None:
    loop = asyncio.get_running_loop()
    task = loop.create_task(process_form_analysis_async(request_id, user_id, request_data))
    _active_analysis_tasks[request_id] = task


async def cancel_form_analysis_task(request_id: str) -> bool:
    task = _active_analysis_tasks.pop(request_id, None)
    if not task:
        return False
    if not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("[AsyncTask %s] Background analysis cancelled", request_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[AsyncTask %s] Cancellation surfaced exception: %s", request_id, exc)
    return True


async def shutdown_active_tasks(timeout: int = 300) -> None:
    """
    Gracefully shutdown all active analysis tasks.

    Called during application shutdown to ensure tasks complete or are properly cancelled.

    Args:
        timeout: Maximum seconds to wait for tasks to complete (default: 30)
    """
    if not _active_analysis_tasks:
        logger.info("No active analysis tasks to shutdown")
        return

    task_count = len(_active_analysis_tasks)
    request_ids = list(_active_analysis_tasks.keys())
    logger.info(f"Shutting down {task_count} active analysis tasks: {request_ids}")

    tasks = list(_active_analysis_tasks.values())

    try:
        # Wait for tasks to complete with timeout
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=timeout
        )
        logger.info(f"All {task_count} tasks completed gracefully")
    except asyncio.TimeoutError:
        logger.warning(
            f"Shutdown timeout ({timeout}s) reached, forcefully cancelling {len(tasks)} remaining tasks"
        )

        # Cancel remaining tasks
        for request_id, task in list(_active_analysis_tasks.items()):
            if not task.done():
                logger.warning(f"Cancelling incomplete task: {request_id}")
                task.cancel()

                # Mark as failed in database
                try:
                    async with get_async_db_context() as db:
                        db_session = cast(AsyncSession, db)
                        await form_requests_crud.update_form_request_status(
                            db_session, request_id, "failed",
                            error_message="Server shutdown before completion"
                        )
                        logger.info(f"Marked request {request_id} as failed due to shutdown")
                except Exception as e:
                    logger.error(f"Failed to update status for {request_id}: {e}")

        # Wait briefly for cancellations to process
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=5
            )
        except asyncio.TimeoutError:
            logger.error("Some tasks did not respond to cancellation")

    # Clear the task dictionary
    _active_analysis_tasks.clear()
    logger.info("Task shutdown complete")

def map_action_type(agent_action_type: str) -> str:
    """
    Map agent action types to browser extension action types.

    Agent uses: fillText, selectDropdown, selectRadio, selectCheckbox, click
    Extension uses: fillText, selectDropdown, selectRadio, selectCheckbox, click, setText

    Args:
        agent_action_type: Action type from agent

    Returns:
        Mapped action type for browser extension
    """
    # Mapping table
    mapping = {
        "fillText": "fillText",
        "selectDropdown": "selectDropdown",
        "selectRadio": "selectRadio",
        "selectCheckbox": "selectCheckbox",
        "click": "click",
        "setText": "fillText",  # setText is alias for fillText
    }

    return mapping.get(agent_action_type, "fillText")  # Default to fillText


def optimize_actions(actions: List[form_schema.FormAction]) -> List[form_schema.FormAction]:
    """Remove redundant actions and keep intent for single-choice groups.

    Google Forms radio questions often appear as individual options in the parser output.
    The value generator may therefore emit multiple `selectRadio` actions that map to
    the same logical question. We keep only the last action per group while still
    allowing distinct grid rows to execute.
    """

    if not actions:
        return []

    optimized: List[form_schema.FormAction] = []

    seen_radio_keys: Set[str] = set()
    seen_generic_keys: Set[Tuple[str, str, str]] = set()

    for action in reversed(actions):
        if action.action_type == "selectRadio":
            key = _radio_group_key(action)
            if key in seen_radio_keys:
                logger.debug("Dropping redundant radio action for key %s selector=%s", key, action.selector)
                continue
            seen_radio_keys.add(key)

        generic_key = (
            action.action_type,
            (action.selector or "").strip(),
            repr(action.value).strip() if action.value is not None else "",
        )

        if generic_key in seen_generic_keys:
            logger.debug(
                "Dropping duplicate action type=%s selector=%s value=%s",
                action.action_type,
                action.selector,
                action.value,
            )
            continue

        seen_generic_keys.add(generic_key)

        optimized.append(action)

    optimized.reverse()
    return optimized


def _radio_group_key(action: form_schema.FormAction) -> str:
    label = (action.label or "").strip().lower()
    selector = action.selector or ""

    # Preserve distinct rows in grid questions by incorporating field indices if present
    for marker in ("data-field-index", "data-row-index", "data-row-id", "data-question-id"):
        marker_pos = selector.find(marker)
        if marker_pos != -1:
            # Extract marker and immediate value portion for stability
            fragment = selector[marker_pos:]
            # Limit length to avoid consuming entire selector
            fragment = fragment.split(']', 1)[0]
            return f"radio:{label}:{fragment}"

    if selector:
        # Use trimmed selector to keep uniqueness per question when label missing
        return f"radio:{label}:{selector.strip()}"

    return f"radio:{label or 'unknown'}"


# ===== NEW: Async Background Task for Form Analysis =====


async def process_form_analysis_async(
    request_id: str,
    user_id: str,
    request_data: form_schema.FormAnalyzeRequest
):
    """
    Process form analysis asynchronously in background.
    Updates the form request status in database as it progresses.

    Args:
        request_id: Form request ID
        user_id: User ID
        request_data: Form analysis request data

    This function:
    1. Updates status to 'processing'
    2. Runs the analysis (same as analyze_form)
    3. Saves actions to database
    4. Updates status to 'completed' or 'failed'
    """
    async def record_progress_event(
        stage: str,
        message: str,
        progress: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        db_session: Optional[AsyncSession] = None,
    ) -> None:
        """Persist a granular progress update for the request."""
        if db_session is None:
            async with get_async_db_context() as progress_db:
                progress_session = cast(AsyncSession, progress_db)
                await form_requests_crud.log_progress_event(
                    progress_session,
                    request_id,
                    stage,
                    message,
                    progress=progress,
                    metadata=metadata,
                )
        else:
            await form_requests_crud.log_progress_event(
                db_session,
                request_id,
                stage,
                message,
                progress=progress,
                metadata=metadata,
            )

    try:
        logger.info("[AsyncTask %s] Starting background analysis for user %s", request_id, user_id)
        html_clean, visible_clean, clipboard_clean = _extract_sanitized_inputs(request_data)
        logger.info(
            "[AsyncTask %s] Input lengths - HTML raw=%d/sanitized=%d, visible raw=%d/sanitized=%d, clipboard raw=%d/sanitized=%d",
            request_id,
            len(request_data.html or ""),
            len(html_clean),
            len(request_data.visible_text or ""),
            len(visible_clean),
            len(request_data.clipboard_text or ""),
            len(clipboard_clean),
        )
        await record_progress_event(
            "inputs_sanitized",
            "Inputs sanitized and queued for analysis",
            progress=5,
            metadata={
                "html_chars": len(html_clean),
                "visible_chars": len(visible_clean),
                "clipboard_chars": len(clipboard_clean),
            },
        )

        # Initialize FileLogger if enabled
        file_logger = create_file_logger(user_id, request_id, enabled=settings.LOG_FILE)
        if file_logger:
            logger.info("[AsyncTask %s] File logging enabled at %s", request_id, file_logger.get_log_path())

        personal_instructions = None
        async with get_async_db_context() as db:
            db_session = cast(AsyncSession, db)
            personal_instructions = await users_crud.get_user_personal_instructions(db_session, user_id)
            # Update status to processing_step_1 (parsing HTML form structure)
            await form_requests_crud.update_form_request_status(
                db_session, request_id, "processing_step_1"
            )
            logger.info("[AsyncTask %s] Status updated to 'processing_step_1'", request_id)
            await record_progress_event(
                "parser_started",
                "Parsing form structure (Phase 1)",
                progress=10,
                db_session=db_session,
            )

        instructions_clean = _sanitize_prompt_text(personal_instructions, collapse_whitespace=False)
        if instructions_clean:
            logger.info(
                "[AsyncTask %s] Personal instructions length: %d chars",
                request_id,
                len(instructions_clean),
            )
        else:
            logger.info("[AsyncTask %s] No personal instructions provided", request_id)

        # Get AgentService singleton
        agent_service = get_agent_service()

        # ===== PHASE 1: Parse HTML Form Structure =====
        logger.info("[AsyncTask %s] Phase 1: Parsing HTML form structure", request_id)

        # Decode screenshots if provided
        screenshot_bytes = None
        if request_data.screenshots and request_data.mode == "extended":
            screenshot_bytes = []
            for idx, screenshot_b64 in enumerate(request_data.screenshots):
                try:
                    if ',' in screenshot_b64:
                        screenshot_b64 = screenshot_b64.split(',', 1)[1]
                    decoded = base64.b64decode(screenshot_b64)
                    screenshot_bytes.append(decoded)
                except Exception as e:
                    logger.warning("Failed to decode screenshot %d: %s", idx, e)

        normalized_questions_async: List[dict] = []
        async_total_inputs = 0

        async with get_async_db_context() as db:
            # Call HTML Form Parser Agent
            parser_result = await agent_service.parse_form_structure(
                user_id=user_id,
                html=html_clean,
                dom_text=visible_clean,
                clipboard_text=clipboard_clean,
                screenshots=screenshot_bytes,
                quality=request_data.quality,
                personal_instructions=instructions_clean,
                file_logger=file_logger,
            )

            # Validate parser result
            if not parser_result or "questions" not in parser_result:
                logger.error("[AsyncTask %s] Parser agent returned invalid result", request_id)
                await record_progress_event(
                    "parser_failed",
                    "Parser agent returned an invalid response",
                    progress=25,
                    metadata={"reason": "missing_questions_key"},
                    db_session=db_session,
                )
                await form_requests_crud.update_form_request_status(
                    db_session, request_id, "failed", error_message="Failed to parse form structure"
                )
                return

            questions = parser_result["questions"]
            logger.info(
                "[AsyncTask %s] Phase 1 complete: Detected %d form questions",
                request_id,
                len(questions),
            )
            await record_progress_event(
                "parser_completed",
                f"Detected {len(questions)} form questions",
                progress=40,
                metadata={"questions": len(questions)},
                db_session=db_session,
            )

            # If no questions detected, mark as completed with 0 actions
            if len(questions) == 0:
                logger.info("[AsyncTask %s] No questions detected, marking as completed", request_id)
                await record_progress_event(
                    "no_questions",
                    "No questions detected; analysis completed",
                    progress=100,
                    metadata={"questions": 0},
                    db_session=db_session,
                )
                await form_requests_crud.update_form_request_status(
                    db_session, request_id, "completed", fields_detected=0
                )
                return

            for index, question in enumerate(questions):
                raw_question: Optional[dict] = None
                if hasattr(question, "model_dump"):
                    raw_question = question.model_dump()
                elif isinstance(question, dict):
                    raw_question = dict(question)
                else:
                    logger.warning(
                        "[AsyncTask %s] Unexpected question type returned from parser: %s",
                        request_id,
                        type(question),
                    )
                if raw_question is None:
                    continue

                normalized_question = _normalize_parser_question(raw_question)
                async_total_inputs += len(normalized_question.get("inputs") or [])
                normalized_questions_async.append(normalized_question)

                if index < 20:
                    logger.info(
                        "[AsyncTask %s] Question[%d]: id=%s | type=%s | title=%s | inputs=%d",
                        request_id,
                        index,
                        normalized_question.get("question_id"),
                        normalized_question.get("question_type"),
                        normalized_question.get("title"),
                        len(normalized_question.get("inputs") or []),
                    )

        total_questions = len(normalized_questions_async)

        # ===== PHASE 2: Generate Solutions =====
        async with get_async_db_context() as db:
            db_session = db
            # Update status to processing_step_2 (generating solutions)
            await form_requests_crud.update_form_request_status(
                db_session, request_id, "processing_step_2"
            )
            logger.info("[AsyncTask %s] Status updated to 'processing_step_2' (generating solutions)", request_id)
            await record_progress_event(
                "solutions_started",
                f"Generating solutions for {len(normalized_questions_async)} questions",
                progress=50,
                metadata={"questions": len(normalized_questions_async)},
                db_session=db_session,
            )

            logger.info(
                "[AsyncTask %s] Phase 2: Generating solutions for %d questions (%d inputs)",
                request_id,
                len(normalized_questions_async),
                async_total_inputs,
            )

            # RAG retrieval is now the default path
            rag_service = get_rag_service()
            logger.info("[AsyncTask %s] Using RAG for context retrieval", request_id)
            user_files = await files_crud.get_user_files(db_session, user_id)

            async def solutions_progress_callback(completed_idx: int, total: int, payload: Dict[str, Any]):
                effective_total = total or total_questions or 1
                percent = 50 + int((completed_idx / effective_total) * 25)
                message = f"Generated solution {completed_idx}/{effective_total}"
                if payload.get("question_id"):
                    message += f" (id={payload['question_id']})"
                await record_progress_event(
                    "solutions_progress",
                    message,
                    progress=min(percent, 75),
                    metadata=payload,
                )

            question_solutions = await agent_service.generate_solutions_per_question(
                user_id=user_id,
                questions=normalized_questions_async,
                user_files=user_files,
                #visible_text=visible_clean,
                clipboard_text=clipboard_clean,
                quality=request_data.quality,
                personal_instructions=instructions_clean,
                rag_service=rag_service,
                rag_top_k=10,
                file_logger=file_logger,
                #screenshots=screenshot_bytes,
                progress_callback=solutions_progress_callback,
            )

            logger.info(
                "[AsyncTask %s] Phase 2 complete: Generated %d solutions",
                request_id,
                len(question_solutions),
            )
            success_count = sum(
                1
                for item in question_solutions
                if isinstance(item.get("solution"), str) and not str(item.get("solution")).startswith("Error")
            )
            await record_progress_event(
                "solutions_completed",
                f"Generated solutions for {success_count}/{len(question_solutions)} questions",
                progress=80,
                metadata={"total": len(question_solutions), "success": success_count},
                db_session=db_session,
            )

        # ===== PHASE 3: Generate Actions from Solutions =====
        async with get_async_db_context() as db:
            db_session = db
            logger.info(
                "[AsyncTask %s] Phase 3: Converting %d solutions to actions",
                request_id,
                len(question_solutions),
            )
            await record_progress_event(
                "actions_started",
                f"Generating actions for {len(question_solutions)} solutions",
                progress=85,
                metadata={"solutions": len(question_solutions)},
                db_session=db_session,
            )

            # Call Action Generator Agent (with batching)
            generator_result = await agent_service.generate_actions_from_solutions(
                user_id=user_id,
                question_solution_pairs=question_solutions,
                quality=request_data.quality,
                batch_size=10,
                file_logger=file_logger,
            )

            # Validate generator result
            if not generator_result or "actions" not in generator_result:
                logger.error("[AsyncTask %s] Action generator returned invalid result", request_id)
                await record_progress_event(
                    "actions_failed",
                    "Action generator returned an invalid result",
                    progress=90,
                    metadata={"reason": "invalid_response"},
                    db_session=db_session,
                )
                await form_requests_crud.update_form_request_status(
                    db_session, request_id, "failed", error_message="Failed to generate actions from solutions"
                )
                return

            logger.info(
                "[AsyncTask %s] Phase 3 complete: Generated %d actions",
                request_id,
                len(generator_result["actions"]),
            )
            await record_progress_event(
                "actions_generated",
                f"Generated {len(generator_result['actions'])} actions",
                progress=90,
                metadata={"actions": len(generator_result["actions"])},
                db_session=db_session,
            )

        # Save results to database
        async with get_async_db_context() as db:
            db_session = db
            # Convert actions to dict format and filter out incomplete values only when required
            actions_dict = []
            required_value_actions = {"fillText", "selectDropdown", "selectCheckbox", "setText"}
            for action_data in generator_result["actions"]:
                original_type = action_data.get("action_type", "")
                action_type = map_action_type(original_type)
                value = action_data.get("value")

                if action_type in required_value_actions and value is None:
                    logger.info(
                        "[AsyncTask %s] Skipping %s action with null value: %s",
                        request_id,
                        action_type,
                        action_data.get("question", "unknown"),
                    )
                    continue

                actions_dict.append({
                    "action_type": action_type,
                    "selector": action_data.get("selector", ""),
                    "value": value,
                    "question": action_data.get("question")
                })

            # Save actions to database
            await form_requests_crud.create_form_actions(
                db_session, request_id, actions_dict
            )
            logger.info(
                "[AsyncTask %s] Saved %d actions to database",
                request_id,
                len(actions_dict),
            )
            await record_progress_event(
                "actions_saved",
                f"Persisted {len(actions_dict)} actions",
                progress=95,
                metadata={"actions": len(actions_dict)},
                db_session=db_session,
            )

            # Update status to completed
            await form_requests_crud.update_form_request_status(
                db_session,
                request_id,
                "completed",
                fields_detected=async_total_inputs
            )
            logger.info("[AsyncTask %s] Status updated to 'completed'", request_id)
            await record_progress_event(
                "completed",
                "Analysis finished successfully",
                progress=100,
                metadata={"actions": len(actions_dict), "fields_detected": async_total_inputs},
                db_session=db_session,
            )

    except asyncio.CancelledError:
        await record_progress_event(
            "cancelled",
            "Analysis was cancelled before completion",
            progress=None,
        )
        logger.info("[AsyncTask %s] Cancelled before completion", request_id)
        raise
    except Exception as e:
        logger.exception("[AsyncTask %s] Exception during async analysis: %s", request_id, e)

        # Update status to failed
        try:
            async with get_async_db_context() as db:
                db_session = cast(AsyncSession, db)
                await form_requests_crud.update_form_request_status(
                    db_session,
                    request_id,
                    "failed",
                    error_message=str(e)
                )
                await record_progress_event(
                    "failed",
                    "Analysis failed",
                    progress=None,
                    metadata={"error": str(e)},
                    db_session=db_session,
                )
        except Exception as db_error:
            logger.error("[AsyncTask %s] Failed to update error status: %s", request_id, db_error)
    finally:
        _active_analysis_tasks.pop(request_id, None)


def build_search_query_from_questions(questions: List[dict]) -> str:
    """Build a search query from question titles and descriptions for RAG retrieval."""

    phrases: List[str] = []
    for question in questions[:15]:  # Use first 15 questions for context search
        title = question.get("title") or ""
        description = question.get("description") or ""

        if title:
            phrases.append(title)
        if description:
            phrases.append(description)

    return " ".join(phrases).strip() or "form information"


def build_search_query_for_question(question: dict, max_inputs: int = 10) -> str:
    """Assemble a semantic search query tailored to a single question."""

    phrases: List[str] = []

    title = question.get("title")
    if title:
        phrases.append(str(title).strip())

    description = question.get("description")
    if description:
        phrases.append(str(description).strip())

    hints = question.get("hints") or []
    for hint in hints:
        if hint:
            phrases.append(str(hint).strip())

    inputs = (question.get("inputs") or [])[:max_inputs]
    for input_data in inputs:
        option_label = input_data.get("option_label")
        value_hint = input_data.get("value_hint")
        notes = input_data.get("notes")
        for candidate in (option_label, value_hint, notes):
            if candidate:
                phrases.append(str(candidate).strip())

    metadata = question.get("metadata")
    if isinstance(metadata, dict):
        for value in metadata.values():
            if isinstance(value, str):
                phrases.append(value.strip())
            elif isinstance(value, list):
                for entry in value[:max_inputs]:
                    if isinstance(entry, str):
                        phrases.append(entry.strip())

    sanitized = [phrase for phrase in phrases if phrase]
    return " ".join(sanitized).strip() or "form question context"
