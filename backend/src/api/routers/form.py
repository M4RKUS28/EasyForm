"""
Form Analysis Router
Endpoint for analyzing forms and generating fill actions.
"""
from fastapi import APIRouter, Depends, status, Request, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...db.crud import form_requests_crud
from ...services import form_service
from ...utils.auth import get_user_id_from_api_token_or_cookie
from ..schemas import form as form_schema


router = APIRouter(
    prefix="/form",
    tags=["form"],
    responses={404: {"description": "Not found"}},
)


# ===== Async API Endpoints =====


@router.post(
    "/analyze/async",
    response_model=form_schema.FormAnalyzeAsyncResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start async form analysis (returns request ID immediately)"
)
async def analyze_form_async(
    form_request: form_schema.FormAnalyzeRequest,
    _background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Start form analysis asynchronously.

    Returns a request ID immediately and processes the analysis in the background.
    Client should poll `/form/request/{id}/status` to check progress.

    **Returns:**
    - `request_id`: Unique ID to track the request
    - `status`: Always "pending" initially

    **Process:**
    1. Creates a form request in database with status "pending"
    2. Starts background task to process the analysis
    3. Returns request ID immediately (HTTP 202)
    4. Client polls status endpoint until completed
    """
    # Get user_id from either API token or cookie
    user_id = await get_user_id_from_api_token_or_cookie(request)

    # Check if user already has an active request
    existing_request = await form_requests_crud.get_active_request_for_user(db, user_id)
    if existing_request:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User already has an active request: {existing_request.id}. "
                   "Please wait for it to complete or cancel it first."
        )

    # Create form request in database
    form_request_db = await form_requests_crud.create_form_request(
        db, user_id=user_id
    )

    # Start background task (tracked so it can be cancelled later)
    form_service.schedule_form_analysis_task(
        form_request_db.id,
        user_id,
        form_request
    )

    return form_schema.FormAnalyzeAsyncResponse(
        request_id=form_request_db.id,
        status="pending"
    )


@router.get(
    "/request/{request_id}/status",
    response_model=form_schema.FormRequestStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get form request status"
)
async def get_request_status(
    request_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the status of a form analysis request.

    **Returns:**
    - `request_id`: Request ID
    - `status`: Current status (pending, processing, completed, failed)
    - `fields_detected`: Number of fields detected (when completed)
    - `error_message`: Error message (when failed)
    - Timestamps: created_at, started_at, completed_at
    """
    # Get user_id from either API token or cookie
    user_id = await get_user_id_from_api_token_or_cookie(request)

    # Get request from database (with authorization check)
    form_request = await form_requests_crud.get_form_request(db, request_id, user_id)

    if not form_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Form request {request_id} not found"
        )

    progress_events = await form_requests_crud.list_progress_events(db, request_id)
    progress_payload = [
        form_schema.FormRequestProgressEntry(
            stage=event.stage,
            message=event.message,
            progress=event.progress,
            metadata=event.payload,
            created_at=event.created_at,
        )
        for event in progress_events
    ]

    return form_schema.FormRequestStatusResponse(
        request_id=form_request.id,
        status=form_request.status,
        progress=progress_payload,
        fields_detected=form_request.fields_detected,
        error_message=form_request.error_message,
        created_at=form_request.created_at,
        started_at=form_request.started_at,
        completed_at=form_request.completed_at
    )


@router.get(
    "/request/{request_id}/actions",
    response_model=form_schema.FormRequestActionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get form actions for completed request"
)
async def get_request_actions(
    request_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the actions for a completed form analysis request.

    **Returns:**
    - `request_id`: Request ID
    - `status`: Current status
    - `actions`: List of actions (only available when status is 'completed')

    **Note:** Actions are only returned when status is 'completed'.
    """
    # Get user_id from either API token or cookie
    user_id = await get_user_id_from_api_token_or_cookie(request)

    # Get request with actions loaded
    form_request = await form_requests_crud.get_form_request_with_actions(
        db, request_id, user_id
    )

    if not form_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Form request {request_id} not found"
        )

    # Convert database actions to FormAction schema
    actions = []
    if form_request.status == "completed" and form_request.actions:
        actions = [
            form_schema.FormAction(
                action_type=action.action_type,
                selector=action.selector,
                value=action.value,
                question=action.question
            )
            for action in form_request.actions
        ]

    return form_schema.FormRequestActionsResponse(
        request_id=form_request.id,
        status=form_request.status,
        actions=actions
    )


@router.delete(
    "/request/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel/delete a form request"
)
async def delete_request(
    request_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel or delete a form analysis request.

    This will:
    - Cancel any in-flight background processing for the request
    - Delete the request from database
    - Delete all associated actions (cascade)
    """
    # Get user_id from either API token or cookie
    user_id = await get_user_id_from_api_token_or_cookie(request)

    form_request = await form_requests_crud.get_form_request(db, request_id, user_id)

    if not form_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Form request {request_id} not found"
        )

    await form_service.cancel_form_analysis_task(request_id)

    await form_requests_crud.delete_form_request(db, request_id, user_id)

    return None  # 204 No Content
