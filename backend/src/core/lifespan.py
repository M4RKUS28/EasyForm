import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from ..db.database import get_engine, Base, get_async_db_context
from ..db.bucket_session import get_bucket_engine
from ..db.seed_data import seed_mock_data
from ..config import settings


scheduler = AsyncIOScheduler()
logger = logging.getLogger(__name__)

for _logger_name in (
    "apscheduler.executors.default",
    "apscheduler.scheduler",
    "apscheduler.jobstores.default",
):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

#
from ..db.database import Base, engine
from ..db.models import db_recipe


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage application lifecycle including startup and shutdown events."""
    logger.info("Starting application...")
    
    try:
        # Initialize database engine and create tables
        engine = await get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(db_recipe.Base.metadata.create_all)

        logger.info("✅ Database tables created/verified")
        
        logger.info("✅ Bucket engine initialized")
        
        logger.info("Scheduler started.")   

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
