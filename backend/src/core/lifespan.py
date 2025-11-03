import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from ..db.database import get_engine, Base, get_async_db_context
from ..db.crud import form_requests_crud
from ..config import settings


scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)

for _logger_name in (
    "apscheduler.executors.default",
    "apscheduler.scheduler",
    "apscheduler.jobstores.default",
):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)


# Cleanup job for old form requests
async def cleanup_old_form_requests():
    """Delete form requests older than 24 hours."""
    try:
        logger.info("Running cleanup job for old form requests...")
        async with get_async_db_context() as db:
            count = await form_requests_crud.cleanup_old_requests(db, hours=24)
            logger.info(f"Cleanup completed: {count} old requests deleted")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage application lifecycle including startup and shutdown events."""
    logger.info("Starting application...")
    
    try:
        # Initialize database engine and create tables
        engine = await get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("✅ Database tables created/verified")


        # Schedule cleanup job to run every 24 hours
        scheduler.add_job(
            cleanup_old_form_requests,
            "interval",
            hours=24,
            id="cleanup_old_form_requests",
            replace_existing=True
        )
        scheduler.start()
        logger.info("✅ Scheduler started with cleanup job")

        yield
    except Exception as e:  # noqa: BLE001
        logger.error("Error during startup: %s", e, exc_info=True)
        raise
    finally:
        logger.info("Shutting down application...")
        if scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler stopped.")
        logger.info("Application shutdown complete.")
