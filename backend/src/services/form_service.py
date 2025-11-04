"""
Service for form analysis and field value generation.

This service analyzes HTML forms and generates appropriate values
using AI and user context (uploaded files).
"""
import base64
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..api.schemas import form as form_schema
from ..db.crud import files_crud, form_requests_crud
from ..db.database import get_async_db_context
from .agent_service import AgentService

logger = logging.getLogger(__name__)

# Singleton instance of AgentService
_agent_service = None


def get_agent_service() -> AgentService:
    """Get or create the singleton AgentService instance."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service


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
        logger.info(f"=== Starting form analysis for user {user_id} ===")
        logger.info(f"Request mode: {request.mode}")
        logger.info(f"HTML length: {len(request.html) if request.html else 0} chars")
        logger.info(f"Visible text length: {len(request.visible_text) if request.visible_text else 0} chars")
        logger.info(f"Clipboard text length: {len(request.clipboard_text) if request.clipboard_text else 0} chars")
        logger.info(f"Screenshots provided: {len(request.screenshots) if request.screenshots else 0}")

        # Get AgentService singleton
        agent_service = get_agent_service()
        logger.info("AgentService singleton retrieved")

        # ===== PHASE 1: Parse HTML Form Structure =====
        logger.info(f"Phase 1: Parsing HTML form structure for user {user_id}")

        # Decode screenshots if provided (from base64)
        screenshot_bytes = None
        if request.screenshots and request.mode == "extended":
            logger.info(f"Decoding {len(request.screenshots)} screenshots for extended mode")
            screenshot_bytes = []
            for idx, screenshot_b64 in enumerate(request.screenshots):
                try:
                    # Remove data URL prefix if present
                    if ',' in screenshot_b64:
                        logger.info(f"Screenshot {idx}: Removing data URL prefix")
                        screenshot_b64 = screenshot_b64.split(',', 1)[1]
                    decoded = base64.b64decode(screenshot_b64)
                    screenshot_bytes.append(decoded)
                    logger.info(f"Screenshot {idx}: Successfully decoded {len(decoded)} bytes")
                except Exception as e:
                    logger.warning(f"Failed to decode screenshot {idx}: {e}")
            logger.info(f"Successfully decoded {len(screenshot_bytes)} screenshots")
        else:
            logger.info("No screenshots to decode (either none provided or not in extended mode)")

        # Call HTML Form Parser Agent
        logger.info("Calling HTML Form Parser Agent...")
        logger.info(
            f"Parser input - user_id: {user_id}, html length: {len(request.html)}, "
            f"dom_text length: {len(request.visible_text) if request.visible_text else 0}, "
            f"clipboard length: {len(request.clipboard_text) if request.clipboard_text else 0}, "
            f"screenshots: {len(screenshot_bytes) if screenshot_bytes else 0}"
        )

        parser_result = await agent_service.parse_form_structure(
            user_id=user_id,
            html=request.html,
            dom_text=request.visible_text,
            clipboard_text=request.clipboard_text,
            screenshots=screenshot_bytes,
            quality=request.quality
        )

        logger.info(f"HTML Form Parser Agent returned result type: {type(parser_result)}")
        logger.info(f"Parser result keys: {parser_result.keys() if isinstance(parser_result, dict) else 'NOT A DICT'}")
        logger.info(f"Parser result preview: {str(parser_result)[:500]}")

        # Validate parser result
        if not parser_result or "fields" not in parser_result:
            logger.error(f"Parser agent returned invalid result: {parser_result}")
            logger.error("Validation failed: parser_result is None or missing 'fields' key")
            return form_schema.FormAnalyzeResponse(
                status="error",
                message="Failed to parse form structure",
                actions=[],
                fields_detected=0
            )

        fields = parser_result["fields"]
        logger.info(f"Phase 1 complete: Detected {len(fields)} form fields")
        logger.info(f"Fields summary: {[f.get('label', f.get('name', 'unknown')) for f in fields[:5]]}")

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
        logger.info(f"Phase 2: Generating values for {len(fields)} fields")

        # Get user's uploaded files
        logger.info("Fetching user files from database...")
        user_files = await files_crud.get_user_files(db, user_id)
        logger.info(f"Found {len(user_files)} user files for context")
        if user_files:
            logger.info(f"User files: {[f.filename for f in user_files[:5]]}")

        # Call Form Value Generator Agent
        logger.info("Calling Form Value Generator Agent...")
        logger.info(
            f"Generator input - user_id: {user_id}, fields count: {len(fields)}, "
            f"visible_text length: {len(request.visible_text) if request.visible_text else 0}, "
            f"clipboard length: {len(request.clipboard_text) if request.clipboard_text else 0}, "
            f"user_files count: {len(user_files)}"
        )

        generator_result = await agent_service.generate_form_values(
            user_id=user_id,
            fields=fields,
            visible_text=request.visible_text,
            clipboard_text=request.clipboard_text,
            user_files=user_files,
            quality=request.quality
        )

        logger.info(f"Form Value Generator Agent returned result type: {type(generator_result)}")
        logger.info(f"Generator result keys: {generator_result.keys() if isinstance(generator_result, dict) else 'NOT A DICT'}")
        logger.info(f"Generator result preview: {str(generator_result)[:500]}")

        # Validate generator result
        if not generator_result or "actions" not in generator_result:
            logger.error(f"Generator agent returned invalid result: {generator_result}")
            logger.error("Validation failed: generator_result is None or missing 'actions' key")
            return form_schema.FormAnalyzeResponse(
                status="error",
                message="Failed to generate form values",
                actions=[],
                fields_detected=len(fields)
            )

        # Convert to FormAction objects
        logger.info(f"Converting {len(generator_result['actions'])} actions to FormAction objects")
        actions = []
        for idx, action_data in enumerate(generator_result["actions"]):
            try:
                logger.info(f"Processing action {idx}: {action_data}")

                # Map action_type to match browser extension expectations
                original_type = action_data.get("action_type", "")
                action_type = map_action_type(original_type)
                logger.info(f"Action {idx}: Mapped type '{original_type}' -> '{action_type}'")

                action = form_schema.FormAction(
                    action_type=action_type,
                    selector=action_data.get("selector", ""),
                    value=action_data.get("value"),
                    label=action_data.get("label", "")
                )
                actions.append(action)
                logger.info(f"Action {idx}: Successfully created FormAction")
            except Exception as e:
                logger.warning(f"Failed to create action from data {action_data}: {e}")
                logger.exception(f"Action {idx} conversion error details:")
                continue

        logger.info(f"Phase 2 complete: Generated {len(actions)} actions")
        logger.info(f"Actions summary: {[f'{a.action_type}:{a.label}' for a in actions[:5]]}")

        # Return success response
        logger.info(f"=== Form analysis complete: {len(fields)} fields, {len(actions)} actions ===")
        return form_schema.FormAnalyzeResponse(
            status="success",
            message=f"Successfully analyzed form with {len(fields)} fields",
            actions=actions,
            fields_detected=len(fields)
        )

    except Exception as e:
        logger.exception(f"Error analyzing form: {e}")
        logger.error(f"Exception type: {type(e).__name__}")
        logger.error(f"Exception args: {e.args}")
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
        logger.info(f"[AsyncTask {request_id}] Starting background analysis for user {user_id}")

        async with get_async_db_context() as db:
            # Update status to processing_step_1 (parsing HTML form structure)
            await form_requests_crud.update_form_request_status(
                db, request_id, "processing_step_1"
            )
            logger.info(f"[AsyncTask {request_id}] Status updated to 'processing_step_1'")

        # Get AgentService singleton
        agent_service = get_agent_service()

        # ===== PHASE 1: Parse HTML Form Structure =====
        logger.info(f"[AsyncTask {request_id}] Phase 1: Parsing HTML form structure")

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
                    logger.warning(f"Failed to decode screenshot {idx}: {e}")

        async with get_async_db_context() as db:
            # Call HTML Form Parser Agent
            parser_result = await agent_service.parse_form_structure(
                user_id=user_id,
                html=request_data.html,
                dom_text=request_data.visible_text,
                clipboard_text=request_data.clipboard_text,
                screenshots=screenshot_bytes,
                quality=request_data.quality
            )

            # Validate parser result
            if not parser_result or "fields" not in parser_result:
                logger.error(f"[AsyncTask {request_id}] Parser agent returned invalid result")
                await form_requests_crud.update_form_request_status(
                    db, request_id, "failed", error_message="Failed to parse form structure"
                )
                return

            fields = parser_result["fields"]
            logger.info(f"[AsyncTask {request_id}] Phase 1 complete: Detected {len(fields)} form fields")

            # If no fields detected, mark as completed with 0 actions
            if len(fields) == 0:
                logger.info(f"[AsyncTask {request_id}] No fields detected, marking as completed")
                await form_requests_crud.update_form_request_status(
                    db, request_id, "completed", fields_detected=0
                )
                return

        # ===== PHASE 2: Generate Field Values =====
        async with get_async_db_context() as db:
            # Update status to processing_step_2 (generating field values)
            await form_requests_crud.update_form_request_status(
                db, request_id, "processing_step_2"
            )
            logger.info(f"[AsyncTask {request_id}] Status updated to 'processing_step_2'")

            logger.info(f"[AsyncTask {request_id}] Phase 2: Generating values for {len(fields)} fields")

            # Get user's uploaded files
            user_files = await files_crud.get_user_files(db, user_id)
            logger.info(f"[AsyncTask {request_id}] Found {len(user_files)} user files for context")

            # Call Form Value Generator Agent
            generator_result = await agent_service.generate_form_values(
                user_id=user_id,
                fields=fields,
                visible_text=request_data.visible_text,
                clipboard_text=request_data.clipboard_text,
                user_files=user_files,
                quality=request_data.quality
            )

            # Validate generator result
            if not generator_result or "actions" not in generator_result:
                logger.error(f"[AsyncTask {request_id}] Generator agent returned invalid result")
                await form_requests_crud.update_form_request_status(
                    db, request_id, "failed", error_message="Failed to generate form values"
                )
                return

            logger.info(f"[AsyncTask {request_id}] Phase 2 complete: Generated {len(generator_result['actions'])} actions")

        # Save results to database
        async with get_async_db_context() as db:
            # Convert actions to dict format and filter out null values
            actions_dict = []
            for action_data in generator_result["actions"]:
                # Skip actions with null values
                if action_data.get("value") is None:
                    logger.info(f"[AsyncTask {request_id}] Skipping action with null value: {action_data.get('label', 'unknown')}")
                    continue

                # Map action_type
                original_type = action_data.get("action_type", "")
                action_type = map_action_type(original_type)

                actions_dict.append({
                    "action_type": action_type,
                    "selector": action_data.get("selector", ""),
                    "value": action_data.get("value"),
                    "label": action_data.get("label", "")
                })

            # Save actions to database
            await form_requests_crud.create_form_actions(
                db, request_id, actions_dict
            )
            logger.info(f"[AsyncTask {request_id}] Saved {len(actions_dict)} actions to database")

            # Update status to completed
            await form_requests_crud.update_form_request_status(
                db,
                request_id,
                "completed",
                fields_detected=len(fields)
            )
            logger.info(f"[AsyncTask {request_id}] Status updated to 'completed'")

    except Exception as e:
        logger.exception(f"[AsyncTask {request_id}] Exception during async analysis: {e}")

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
            logger.error(f"[AsyncTask {request_id}] Failed to update error status: {db_error}")
