"""
Service for form analysis and field value generation.

This service analyzes HTML forms and generates appropriate values
using AI and user context (uploaded files).
"""
import asyncio
import base64
import logging
import re
from collections import Counter, OrderedDict
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import form as form_schema
from ..db.crud import files_crud, form_requests_crud, users_crud, document_chunks_crud
from ..db.database import get_async_db_context
from .agent_service import AgentService
from .rag_service import get_rag_service

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


def _clean_label_text(text: Optional[str]) -> Optional[str]:
    if text is None or not isinstance(text, str):
        return None if text is None else str(text)
    cleaned = re.sub(r"\s+", " ", text)
    return cleaned.strip()


def _normalize_parser_field(field: dict) -> dict:
    normalized = dict(field)

    for key in ("label", "name"):
        value = normalized.get(key)
        if isinstance(value, str):
            normalized[key] = _clean_label_text(value)

    description = normalized.get("description")
    if isinstance(description, str):
        desc = description.replace("\r\n", "\n").replace("\r", "\n")
        desc = re.sub(r"\n{3,}", "\n\n", desc)
        normalized["description"] = desc.strip()

    options = normalized.get("options")
    if isinstance(options, list):
        cleaned_options = []
        for option in options:
            if isinstance(option, str):
                cleaned = _clean_label_text(option)
                if cleaned:
                    cleaned_options.append(cleaned)
            else:
                cleaned_options.append(option)
        normalized["options"] = cleaned_options

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


async def analyze_form(
    db: AsyncSession,
    user_id: str,
    request: form_schema.FormAnalyzeRequest
) -> form_schema.FormAnalyzeResponse:
    """
    Analyze a form and generate actions to fill it.

    This orchestrates the two-phase analysis:
    1. HTML Form Parser Agent - Extracts form structure
    2. Form Value Generator Agent - Generates values based on user context

    Args:
        db: Database session
        user_id: User ID
        request: Form analysis request

    Returns:
        FormAnalyzeResponse with actions
    """
    try:
        logger.info("=== Starting form analysis for user %s ===", user_id)
        logger.info("Request mode: %s", request.mode)
        html_clean, visible_clean, clipboard_clean = _extract_sanitized_inputs(request)
        raw_html_len = len(request.html or "")
        raw_visible_len = len(request.visible_text or "")
        raw_clipboard_len = len(request.clipboard_text or "")
        logger.info(
            "HTML length: raw=%d chars, sanitized=%d chars",
            raw_html_len,
            len(html_clean),
        )
        logger.info(
            "Visible text length: raw=%d chars, sanitized=%d chars",
            raw_visible_len,
            len(visible_clean),
        )
        logger.info(
            "Clipboard text length: raw=%d chars, sanitized=%d chars",
            raw_clipboard_len,
            len(clipboard_clean),
        )
        logger.info("Screenshots provided: %d", len(request.screenshots) if request.screenshots else 0)

        # Get AgentService singleton
        agent_service = get_agent_service()
        logger.info("AgentService singleton retrieved")

        # ===== PHASE 1: Parse HTML Form Structure =====
        logger.info("Phase 1: Parsing HTML form structure for user %s", user_id)

        # Decode screenshots if provided (from base64)
        screenshot_bytes = None
        if request.screenshots and request.mode == "extended":
            logger.info("Decoding %d screenshots for extended mode", len(request.screenshots))
            screenshot_bytes = []
            for idx, screenshot_b64 in enumerate(request.screenshots):
                try:
                    # Remove data URL prefix if present
                    if ',' in screenshot_b64:
                        logger.info("Screenshot %d: Removing data URL prefix", idx)
                        screenshot_b64 = screenshot_b64.split(',', 1)[1]
                    decoded = base64.b64decode(screenshot_b64)
                    screenshot_bytes.append(decoded)
                    logger.info("Screenshot %d: Successfully decoded %d bytes", idx, len(decoded))
                except Exception as e:
                    logger.warning("Failed to decode screenshot %d: %s", idx, e)
            logger.info("Successfully decoded %d screenshots", len(screenshot_bytes))
        else:
            logger.info("No screenshots to decode (either none provided or not in extended mode)")

        # Call HTML Form Parser Agent
        logger.info("Calling HTML Form Parser Agent...")
        logger.info(
            "Parser input - user_id: %s, html length: %d, dom_text length: %d, clipboard length: %d, screenshots: %d",
            user_id,
            len(html_clean),
            len(visible_clean),
            len(clipboard_clean),
            len(screenshot_bytes) if screenshot_bytes else 0,
        )

        personal_instructions = await users_crud.get_user_personal_instructions(db, user_id)
        instructions_clean = _sanitize_prompt_text(personal_instructions, collapse_whitespace=False)
        if instructions_clean:
            logger.info("Personal instructions length: %d chars", len(instructions_clean))
        else:
            logger.info("No personal instructions provided")

        parser_result = await agent_service.parse_form_structure(
            user_id=user_id,
            html=html_clean,
            dom_text=visible_clean,
            clipboard_text=clipboard_clean,
            screenshots=screenshot_bytes,
            quality=request.quality,
            personal_instructions=instructions_clean,
        )

        logger.info("HTML Form Parser Agent returned result type: %s", type(parser_result))
        logger.info(
            "Parser result keys: %s",
            parser_result.keys() if isinstance(parser_result, dict) else "NOT A DICT",
        )
        logger.info("Parser result preview: %s", str(parser_result)[:500])

        # Validate parser result
        if not parser_result or "fields" not in parser_result:
            logger.error("Parser agent returned invalid result: %s", parser_result)
            logger.error("Validation failed: parser_result is None or missing 'fields' key")
            return form_schema.FormAnalyzeResponse(
                status="error",
                message="Failed to parse form structure",
                actions=[],
                fields_detected=0
            )

        fields = parser_result["fields"]
        logger.info("Phase 1 complete: Detected %d form fields", len(fields))

        # Provide richer diagnostics about the detected fields to help debug parsing issues
        normalized_fields = []
        for field in fields:
            normalized: Optional[dict] = None
            if hasattr(field, "model_dump"):
                normalized = field.model_dump()
            elif isinstance(field, dict):
                normalized = dict(field)
            else:
                logger.warning("Unexpected field type returned from parser: %s", type(field))
                continue

            normalized = _normalize_parser_field(normalized)
            normalized_fields.append(normalized)

        if normalized_fields:
            summaries = [
                nf.get("label")
                or nf.get("name")
                or nf.get("selector")
                or f"field_{idx}"
                for idx, nf in enumerate(normalized_fields[:5])
            ]
            logger.info("Fields summary: %s", summaries)

            type_counter = Counter(f.get("type", "unknown") for f in normalized_fields)
            logger.info("Field type distribution: %s", dict(type_counter))

            max_logged_fields = 25
            for idx, field_data in enumerate(normalized_fields[:max_logged_fields]):
                selector = field_data.get("selector")
                label = field_data.get("label")
                summary = {
                    "selector": selector,
                    "label": label,
                    "type": field_data.get("type"),
                    "required": field_data.get("required"),
                    "has_placeholder": bool(field_data.get("placeholder")),
                    "options_count": len(field_data.get("options", []) or []),
                    "description_len": len(field_data.get("description") or ""),
                    "context_len": len(field_data.get("surrounding_context") or ""),
                }
                logger.info("Field[%d]: %s", idx, summary)

            if len(normalized_fields) > max_logged_fields:
                logger.info(
                    "Additional fields omitted from log: showing %d of %d entries",
                    max_logged_fields,
                    len(normalized_fields),
                )

        # If no fields detected, return early
        if len(fields) == 0:
            logger.info("No fields detected, returning early with success status")
            return form_schema.FormAnalyzeResponse(
                status="success",
                message="No form fields detected on this page",
                actions=[],
                fields_detected=0
            )

        # ===== PHASE 2: Generate Field Values =====
        logger.info("Phase 2: Generating values for %d fields", len(fields))

        field_groups = build_field_groups(normalized_fields)
        total_group_fields = sum(len(group) for group in field_groups)
        logger.info(
            "Prepared %d field groups containing %d total fields for value generation",
            len(field_groups),
            total_group_fields,
        )

        max_group_log = 15
        for group_idx, group in enumerate(field_groups[:max_group_log]):
            if not group:
                continue

            primary = group[0]
            group_id = primary.get("group_id", "<none>")
            labels = {
                (field.get("label") or field.get("name") or field.get("selector") or f"field_{idx}")
                for idx, field in enumerate(group)
            }
            types = {field.get("type", "unknown") for field in group}
            logger.info(
                "Field group %d (group_id=%s) -> labels=%s, types=%s, size=%d",
                group_idx,
                group_id,
                sorted(labels),
                sorted(types),
                len(group),
            )

            for field in group:
                logger.info(
                    "  - selector=%s | type=%s | label=%s | required=%s | options=%d",
                    field.get("selector"),
                    field.get("type"),
                    field.get("label"),
                    field.get("required"),
                    len(field.get("options") or []),
                )

        if len(field_groups) > max_group_log:
            logger.info(
                "Field groups truncated in logs: showing %d of %d entries",
                max_group_log,
                len(field_groups),
            )

        # Get user context - use RAG or direct depending on file count/size
        logger.info("Fetching user context...")
        rag_service = get_rag_service()
        use_rag = await rag_service.should_use_rag(db, user_id)

        if use_rag:
            logger.info("Using RAG for context retrieval")

            # Build search query from field labels
            query = build_search_query_from_fields(normalized_fields)
            logger.info(f"RAG search query: {query[:100]}...")

            # Retrieve relevant chunks
            context = await rag_service.retrieve_relevant_context(
                db=db,
                query=query,
                user_id=user_id,
                top_k=10
            )

            logger.info(f"Retrieved {len(context['text_chunks'])} text chunks and {len(context['image_chunks'])} image chunks")

            # Call Form Value Generator Agent with RAG context
            logger.info("Calling Form Value Generator Agent with RAG context...")
            generator_result = await agent_service.generate_form_values(
                user_id=user_id,
                field_groups=field_groups,
                visible_text=visible_clean,
                clipboard_text=clipboard_clean,
                user_files=None,  # Will use text_context and image_context instead
                quality=request.quality,
                personal_instructions=instructions_clean,
            )
        else:
            logger.info("Using direct context (all files)")

            # Fetch all files (current approach)
            user_files = await files_crud.get_user_files(db, user_id)
            logger.info("Found %d user files for context", len(user_files))
            if user_files:
                logger.info("User files: %s", [f.filename for f in user_files[:5]])

            # Call Form Value Generator Agent with direct files
            logger.info("Calling Form Value Generator Agent with direct context...")
            logger.info(
                "Generator input - user_id: %s, fields count: %d, visible_text length: %d, clipboard length: %d, user_files count: %d",
                user_id,
                total_group_fields,
                len(visible_clean),
                len(clipboard_clean),
                len(user_files),
            )

            generator_result = await agent_service.generate_form_values(
                user_id=user_id,
                field_groups=field_groups,
                visible_text=visible_clean,
                clipboard_text=clipboard_clean,
                user_files=user_files,
                quality=request.quality,
                personal_instructions=instructions_clean,
            )

        logger.info("Form Value Generator Agent returned result type: %s", type(generator_result))
        logger.info(
            "Generator result keys: %s",
            generator_result.keys() if isinstance(generator_result, dict) else "NOT A DICT",
        )
        logger.info("Generator result preview: %s", str(generator_result)[:500])

        # Validate generator result
        if not generator_result or "actions" not in generator_result:
            logger.error("Generator agent returned invalid result: %s", generator_result)
            logger.error("Validation failed: generator_result is None or missing 'actions' key")
            return form_schema.FormAnalyzeResponse(
                status="error",
                message="Failed to generate form values",
                actions=[],
                fields_detected=len(fields)
            )

        # Convert to FormAction objects
        logger.info("Converting %d actions to FormAction objects", len(generator_result["actions"]))
        actions = []
        for idx, action_data in enumerate(generator_result["actions"]):
            try:
                logger.info("Processing action %d: %s", idx, action_data)

                # Map action_type to match browser extension expectations
                original_type = action_data.get("action_type", "")
                action_type = map_action_type(original_type)
                logger.info("Action %d: Mapped type '%s' -> '%s'", idx, original_type, action_type)

                value = action_data.get("value")
                requires_value = {"fillText", "setText", "selectDropdown", "selectCheckbox"}
                if action_type in requires_value and value is None:
                    logger.info(
                        "Action %d skipped: '%s' requires value but received None (selector=%s)",
                        idx,
                        action_type,
                        action_data.get("selector"),
                    )
                    continue

                label = _clean_label_text(action_data.get("label"))

                action = form_schema.FormAction(
                    action_type=action_type,
                    selector=action_data.get("selector", ""),
                    value=value,
                    label=label or ""
                )
                actions.append(action)
                logger.info("Action %d: Successfully created FormAction", idx)
            except Exception as e:
                logger.warning("Failed to create action from data %s: %s", action_data, e)
                logger.exception("Action %d conversion error details:", idx)
                continue

        optimized_actions = optimize_actions(actions)

        logger.info("Phase 2 complete: Generated %d actions (optimized to %d)", len(actions), len(optimized_actions))
        logger.info("Actions summary: %s", [f"{a.action_type}:{a.label}" for a in optimized_actions[:5]])

        # Return success response
        logger.info(
            "=== Form analysis complete: %d fields, %d actions ===",
            len(fields),
            len(optimized_actions),
        )
        return form_schema.FormAnalyzeResponse(
            status="success",
            message=f"Successfully analyzed form with {len(fields)} fields",
            actions=optimized_actions,
            fields_detected=len(fields)
        )

    except Exception as e:
        logger.exception("Error analyzing form: %s", e)
        logger.error("Exception type: %s", type(e).__name__)
        logger.error("Exception args: %s", e.args)
        return form_schema.FormAnalyzeResponse(
            status="error",
            message=f"Error analyzing form: {str(e)}",
            actions=[],
            fields_detected=0
        )


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


def build_field_groups(fields: List[dict]) -> List[List[dict]]:
    """Group parsed fields by their shared group_id for downstream processing.

    Ensures a stable identifier exists for every field. When the parser omits
    `group_id`, the function synthesizes a unique value so those controls remain
    isolated in their own groups.
    """

    groups: "OrderedDict[str, List[dict]]" = OrderedDict()
    fallback_counter = 0

    for field in fields:
        if not isinstance(field, dict):
            continue

        field_copy = dict(field)
        group_id = field_copy.get("group_id")

        if not group_id:
            selector = field_copy.get("selector")
            if selector:
                group_id = f"selector::{selector}"
            else:
                group_id = f"field::{fallback_counter}"
                fallback_counter += 1

            field_copy["group_id"] = group_id
            logger.debug("Synthesized group_id '%s' for selector '%s'", group_id, selector)

        groups.setdefault(group_id, []).append(field_copy)

    return list(groups.values())


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

        personal_instructions = None
        async with get_async_db_context() as db:
            personal_instructions = await users_crud.get_user_personal_instructions(db, user_id)
            # Update status to processing_step_1 (parsing HTML form structure)
            await form_requests_crud.update_form_request_status(
                db, request_id, "processing_step_1"
            )
            logger.info("[AsyncTask %s] Status updated to 'processing_step_1'", request_id)

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
            )

            # Validate parser result
            if not parser_result or "fields" not in parser_result:
                logger.error("[AsyncTask %s] Parser agent returned invalid result", request_id)
                await form_requests_crud.update_form_request_status(
                    db, request_id, "failed", error_message="Failed to parse form structure"
                )
                return

            fields = parser_result["fields"]
            logger.info(
                "[AsyncTask %s] Phase 1 complete: Detected %d form fields",
                request_id,
                len(fields),
            )

            # If no fields detected, mark as completed with 0 actions
            if len(fields) == 0:
                logger.info("[AsyncTask %s] No fields detected, marking as completed", request_id)
                await form_requests_crud.update_form_request_status(
                    db, request_id, "completed", fields_detected=0
                )
                return

            normalized_fields_async = []
            for field in fields:
                if hasattr(field, "model_dump"):
                    normalized_fields_async.append(field.model_dump())
                elif isinstance(field, dict):
                    normalized_fields_async.append(dict(field))
                else:
                    logger.warning(
                        "[AsyncTask %s] Unexpected field type returned from parser: %s",
                        request_id,
                        type(field),
                    )

            async_field_groups = build_field_groups(normalized_fields_async)
            async_total_group_fields = sum(len(group) for group in async_field_groups)
            logger.info(
                "[AsyncTask %s] Prepared %d field groups containing %d total fields",
                request_id,
                len(async_field_groups),
                async_total_group_fields,
            )

        # ===== PHASE 2: Generate Field Values =====
        async with get_async_db_context() as db:
            # Update status to processing_step_2 (generating field values)
            await form_requests_crud.update_form_request_status(
                db, request_id, "processing_step_2"
            )
            logger.info("[AsyncTask %s] Status updated to 'processing_step_2'", request_id)

            logger.info(
                "[AsyncTask %s] Phase 2: Generating values for %d fields",
                request_id,
                async_total_group_fields,
            )

            # Get user context - use RAG or direct depending on file count/size
            logger.info("[AsyncTask %s] Fetching user context...", request_id)
            rag_service = get_rag_service()
            use_rag = await rag_service.should_use_rag(db, user_id)

            if use_rag:
                logger.info("[AsyncTask %s] Using RAG for context retrieval", request_id)

                # Build search query from field labels
                query = build_search_query_from_fields(normalized_fields_async)
                logger.info("[AsyncTask %s] RAG search query: %s...", request_id, query[:100])

                # Retrieve relevant chunks
                context = await rag_service.retrieve_relevant_context(
                    db=db,
                    query=query,
                    user_id=user_id,
                    top_k=10
                )

                logger.info(
                    "[AsyncTask %s] Retrieved %d text chunks and %d image chunks",
                    request_id,
                    len(context['text_chunks']),
                    len(context['image_chunks'])
                )

                # Call Form Value Generator Agent with RAG context
                generator_result = await agent_service.generate_form_values(
                    user_id=user_id,
                    field_groups=async_field_groups,
                    visible_text=visible_clean,
                    clipboard_text=clipboard_clean,
                    user_files=None,  # Will use text_context and image_context instead
                    quality=request_data.quality,
                    personal_instructions=instructions_clean,
                )
            else:
                logger.info("[AsyncTask %s] Using direct context (all files)", request_id)

                # Get user's uploaded files
                user_files = await files_crud.get_user_files(db, user_id)
                logger.info(
                    "[AsyncTask %s] Found %d user files for context",
                    request_id,
                    len(user_files),
                )

                # Call Form Value Generator Agent with direct files
                generator_result = await agent_service.generate_form_values(
                    user_id=user_id,
                    field_groups=async_field_groups,
                    visible_text=visible_clean,
                    clipboard_text=clipboard_clean,
                    user_files=user_files,
                    quality=request_data.quality,
                    personal_instructions=instructions_clean,
                )

            # Validate generator result
            if not generator_result or "actions" not in generator_result:
                logger.error("[AsyncTask %s] Generator agent returned invalid result", request_id)
                await form_requests_crud.update_form_request_status(
                    db, request_id, "failed", error_message="Failed to generate form values"
                )
                return

            logger.info(
                "[AsyncTask %s] Phase 2 complete: Generated %d actions",
                request_id,
                len(generator_result["actions"]),
            )

        # Save results to database
        async with get_async_db_context() as db:
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
                        action_data.get("label", "unknown"),
                    )
                    continue

                actions_dict.append({
                    "action_type": action_type,
                    "selector": action_data.get("selector", ""),
                    "value": value,
                    "label": action_data.get("label", "")
                })

            # Save actions to database
            await form_requests_crud.create_form_actions(
                db, request_id, actions_dict
            )
            logger.info(
                "[AsyncTask %s] Saved %d actions to database",
                request_id,
                len(actions_dict),
            )

            # Update status to completed
            await form_requests_crud.update_form_request_status(
                db,
                request_id,
                "completed",
                fields_detected=len(fields)
            )
            logger.info("[AsyncTask %s] Status updated to 'completed'", request_id)

    except asyncio.CancelledError:
        logger.info("[AsyncTask %s] Cancelled before completion", request_id)
        raise
    except Exception as e:
        logger.exception("[AsyncTask %s] Exception during async analysis: %s", request_id, e)

        # Update status to failed
        try:
            async with get_async_db_context() as db:
                await form_requests_crud.update_form_request_status(
                    db,
                    request_id,
                    "failed",
                    error_message=str(e)
                )
        except Exception as db_error:
            logger.error("[AsyncTask %s] Failed to update error status: %s", request_id, db_error)
    finally:
        _active_analysis_tasks.pop(request_id, None)


def build_search_query_from_fields(fields: List[dict]) -> str:
    """
    Build a search query from form field labels for RAG retrieval.

    Args:
        fields: List of form field dictionaries

    Returns:
        Search query string
    """
    labels = []
    for field in fields[:15]:  # Use first 15 fields for query
        label = field.get("label") or field.get("name") or ""
        if label:
            labels.append(label)

    return " ".join(labels) if labels else "form information"
