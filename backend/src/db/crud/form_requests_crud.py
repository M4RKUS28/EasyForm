"""
CRUD operations for form requests and actions.
"""
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.db_form_request import FormRequest
from ..models.db_form_action import FormAction
from ..models.db_form_request_progress import FormRequestProgress


async def create_form_request(
    db: AsyncSession,
    user_id: str,
    html_hash: Optional[str] = None
) -> FormRequest:
    """
    Create a new form analysis request.

    Args:
        db: Database session
        user_id: User ID
        html_hash: Optional hash of HTML for duplicate detection

    Returns:
        Created FormRequest
    """
    request_id = str(uuid.uuid4())

    request = FormRequest(
        id=request_id,
        user_id=user_id,
        status="pending",
        html_hash=html_hash,
        created_at=datetime.now(timezone.utc)
    )

    db.add(request)
    db.add(
        FormRequestProgress(
            request_id=request_id,
            stage="queued",
            message="Request received and queued for processing",
            progress=0,
        )
    )
    await db.commit()
    await db.refresh(request)

    return request


async def get_form_request(
    db: AsyncSession,
    request_id: str,
    user_id: Optional[str] = None
) -> Optional[FormRequest]:
    """
    Get a form request by ID.

    Args:
        db: Database session
        request_id: Request ID
        user_id: Optional user ID for authorization check

    Returns:
        FormRequest if found, None otherwise
    """
    query = select(FormRequest).where(FormRequest.id == request_id)

    if user_id:
        query = query.where(FormRequest.user_id == user_id)

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_form_request_with_actions(
    db: AsyncSession,
    request_id: str,
    user_id: Optional[str] = None
) -> Optional[FormRequest]:
    """
    Get a form request with its actions loaded.

    Args:
        db: Database session
        request_id: Request ID
        user_id: Optional user ID for authorization check

    Returns:
        FormRequest with actions if found, None otherwise
    """
    query = (
        select(FormRequest)
        .options(selectinload(FormRequest.actions))
        .where(FormRequest.id == request_id)
    )

    if user_id:
        query = query.where(FormRequest.user_id == user_id)

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def update_form_request_status(
    db: AsyncSession,
    request_id: str,
    status: str,
    fields_detected: Optional[int] = None,
    error_message: Optional[str] = None
) -> Optional[FormRequest]:
    """
    Update the status of a form request.

    Args:
        db: Database session
        request_id: Request ID
        status: New status (pending, processing, completed, failed)
        fields_detected: Optional number of fields detected
        error_message: Optional error message for failed status

    Returns:
        Updated FormRequest if found, None otherwise
    """
    request = await get_form_request(db, request_id)

    if not request:
        return None

    request.status = status

    if status.startswith("processing") and not request.started_at:
        request.started_at = datetime.now(timezone.utc)

    if status in ["completed", "failed"]:
        request.completed_at = datetime.now(timezone.utc)

    if fields_detected is not None:
        request.fields_detected = fields_detected

    if error_message is not None:
        request.error_message = error_message

    await db.commit()
    await db.refresh(request)

    return request


async def create_form_actions(
    db: AsyncSession,
    request_id: str,
    actions: List[dict]
) -> List[FormAction]:
    """
    Create form actions for a request.

    Args:
        db: Database session
        request_id: Request ID
        actions: List of action dictionaries

    Returns:
        List of created FormAction objects
    """
    db_actions = []

    for idx, action_data in enumerate(actions):
        db_action = FormAction(
            request_id=request_id,
            action_type=action_data.get("action_type", ""),
            selector=action_data.get("selector", ""),
            value=action_data.get("value"),
            label=action_data.get("label", ""),
            question=action_data.get("question"),
            order_index=idx
        )
        db_actions.append(db_action)
        db.add(db_action)

    await db.commit()

    # Refresh all actions
    for action in db_actions:
        await db.refresh(action)

    return db_actions


async def get_form_actions(
    db: AsyncSession,
    request_id: str
) -> List[FormAction]:
    """
    Get all actions for a form request, ordered by order_index.

    Args:
        db: Database session
        request_id: Request ID

    Returns:
        List of FormAction objects
    """
    query = (
        select(FormAction)
        .where(FormAction.request_id == request_id)
        .order_by(FormAction.order_index)
    )

    result = await db.execute(query)
    return list(result.scalars().all())


async def delete_form_request(
    db: AsyncSession,
    request_id: str,
    user_id: Optional[str] = None
) -> bool:
    """
    Delete a form request and all its actions (CASCADE).

    Args:
        db: Database session
        request_id: Request ID
        user_id: Optional user ID for authorization check

    Returns:
        True if deleted, False if not found
    """
    # First check if request exists and belongs to user
    request = await get_form_request(db, request_id, user_id)

    if not request:
        return False

    # Delete the request (actions will be cascade deleted)
    await db.delete(request)
    await db.commit()

    return True


async def log_progress_event(
    db: AsyncSession,
    request_id: str,
    stage: str,
    message: str,
    progress: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> FormRequestProgress:
    """
    Persist a granular progress update for a form request.
    """
    event = FormRequestProgress(
        request_id=request_id,
        stage=stage,
        message=message,
        progress=progress,
        payload=metadata,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event


async def list_progress_events(
    db: AsyncSession,
    request_id: str,
) -> List[FormRequestProgress]:
    """
    Retrieve all progress events for a request ordered by time.
    """
    query = (
        select(FormRequestProgress)
        .where(FormRequestProgress.request_id == request_id)
        .order_by(FormRequestProgress.created_at.asc())
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_active_request_for_user(
    db: AsyncSession,
    user_id: str
) -> Optional[FormRequest]:
    """
    Get any active (pending or processing) request for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Active FormRequest if found, None otherwise
    """
    query = (
        select(FormRequest)
        .where(FormRequest.user_id == user_id)
        .where(FormRequest.status.in_(["pending", "processing"]))
        .order_by(FormRequest.created_at.desc())
    )

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def cleanup_old_requests(
    db: AsyncSession,
    hours: int = 24
) -> int:
    """
    Delete form requests older than specified hours.

    Args:
        db: Database session
        hours: Age threshold in hours (default: 24)

    Returns:
        Number of deleted requests
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Get count of requests to delete
    count_query = select(FormRequest).where(FormRequest.created_at < cutoff_time)
    result = await db.execute(count_query)
    count = len(list(result.scalars().all()))

    # Delete old requests (actions will be cascade deleted)
    delete_query = delete(FormRequest).where(FormRequest.created_at < cutoff_time)
    await db.execute(delete_query)
    await db.commit()

    return count
