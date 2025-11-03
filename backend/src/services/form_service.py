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
from ..db.crud import files_crud
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
        # Get AgentService singleton
        agent_service = get_agent_service()
        # ===== PHASE 1: Parse HTML Form Structure =====
        logger.info(f"Phase 1: Parsing HTML form structure for user {user_id}")

        # Decode screenshots if provided (from base64)
        screenshot_bytes = None
        if request.screenshots and request.mode == "extended":
            screenshot_bytes = []
            for screenshot_b64 in request.screenshots:
                try:
                    # Remove data URL prefix if present
                    if ',' in screenshot_b64:
                        screenshot_b64 = screenshot_b64.split(',', 1)[1]
                    screenshot_bytes.append(base64.b64decode(screenshot_b64))
                except Exception as e:
                    logger.warning(f"Failed to decode screenshot: {e}")

        # Call HTML Form Parser Agent
        parser_result = await agent_service.parse_form_structure(
            user_id=user_id,
            html=request.html,
            dom_text=request.visible_text,
            screenshots=screenshot_bytes
        )

        # Validate parser result
        if not parser_result or "fields" not in parser_result:
            logger.error(f"Parser agent returned invalid result: {parser_result}")
            return form_schema.FormAnalyzeResponse(
                status="error",
                message="Failed to parse form structure",
                actions=[],
                fields_detected=0
            )

        fields = parser_result["fields"]
        logger.info(f"Phase 1 complete: Detected {len(fields)} form fields")

        # If no fields detected, return early
        if len(fields) == 0:
            return form_schema.FormAnalyzeResponse(
                status="success",
                message="No form fields detected on this page",
                actions=[],
                fields_detected=0
            )

        # ===== PHASE 2: Generate Field Values =====
        logger.info(f"Phase 2: Generating values for {len(fields)} fields")

        # Get user's uploaded files
        user_files = await files_crud.get_user_files(db, user_id)
        logger.info(f"Found {len(user_files)} user files for context")

        # Call Form Value Generator Agent
        generator_result = await agent_service.generate_form_values(
            user_id=user_id,
            fields=fields,
            visible_text=request.visible_text,
            user_files=user_files
        )

        # Validate generator result
        if not generator_result or "actions" not in generator_result:
            logger.error(f"Generator agent returned invalid result: {generator_result}")
            return form_schema.FormAnalyzeResponse(
                status="error",
                message="Failed to generate form values",
                actions=[],
                fields_detected=len(fields)
            )

        # Convert to FormAction objects
        actions = []
        for action_data in generator_result["actions"]:
            try:
                # Map action_type to match browser extension expectations
                action_type = map_action_type(action_data.get("action_type", ""))

                action = form_schema.FormAction(
                    action_type=action_type,
                    selector=action_data.get("selector", ""),
                    value=action_data.get("value"),
                    label=action_data.get("label", "")
                )
                actions.append(action)
            except Exception as e:
                logger.warning(f"Failed to create action from data {action_data}: {e}")
                continue

        logger.info(f"Phase 2 complete: Generated {len(actions)} actions")

        # Return success response
        return form_schema.FormAnalyzeResponse(
            status="success",
            message=f"Successfully analyzed form with {len(fields)} fields",
            actions=actions,
            fields_detected=len(fields)
        )

    except Exception as e:
        logger.exception(f"Error analyzing form: {e}")
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
