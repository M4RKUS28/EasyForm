"""
Form Analysis Router
Endpoint for analyzing forms and generating fill actions.
"""
from fastapi import APIRouter, Depends, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...services import form_service
from ...utils.auth import get_user_id_from_api_token_or_cookie
from ..schemas import form as form_schema


router = APIRouter(
    prefix="/form",
    tags=["form"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/analyze",
    response_model=form_schema.FormAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a form and generate fill actions"
)
async def analyze_form(
    form_request: form_schema.FormAnalyzeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze a form and generate actions to fill it.

    Supports authentication via:
    - Cookie (web app)
    - Authorization header with API token (browser extension)

    **Request Body:**
    - `html`: Complete HTML code of the page
    - `visible_text`: Visible text content of the page
    - `screenshots`: Optional list of base64-encoded screenshots (for extended mode)
    - `mode`: "basic" (HTML + text only) or "extended" (includes screenshots)

    **Response:**
    - `status`: "success" or "error"
    - `actions`: List of actions to perform on the form
    - `fields_detected`: Number of form fields detected

    **Process:**
    1. Parse HTML to identify form fields
    2. Gather context from user's uploaded files (PDFs, images)
    3. Use AI to generate appropriate values
    4. Return structured actions for the browser extension to execute

    **Note:** The AI implementation is currently a placeholder.
    See `services/form_service.py` for detailed TODO comments.
    """
    # Get user_id from either API token or cookie
    user_id = await get_user_id_from_api_token_or_cookie(request)

    return await form_service.analyze_form(db, user_id, form_request)
