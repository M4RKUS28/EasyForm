import asyncio
import logging
from typing import AsyncGenerator, Optional, Callable
from contextlib import asynccontextmanager
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import SQLAlchemyError
from ..config import settings

logger = logging.getLogger(__name__)

class _DBState:
    def __init__(self) -> None:
        self.engine: Optional[AsyncEngine] = None  # Lazy-initialized async engine instance
        self.session_factory: Optional[Callable[[], AsyncSession]] = None


state = _DBState()

# ✅ Local SQLite fallback
async def _create_local_engine(url: str):
    if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    local_engine = create_async_engine(
        url,
        poolclass=NullPool,
        connect_args={"check_same_thread": False},
    )
    return local_engine

# ✅ Retry-enabled MySQL Cloud connection
async def _create_cloud_engine_with_retry(max_retries=5, wait_seconds=2):
    # Build MySQL connection URL safely
    safe_password = quote_plus(settings.DB_PASSWORD or "")
    mysql_url= (
        f"mysql+aiomysql://{settings.DB_USER}:{safe_password}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )
    logger.info("Connecting to Cloud SQL: %s", mysql_url)

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            new_engine = create_async_engine(
                mysql_url,
                pool_recycle=settings.DB_POOL_RECYCLE,
                pool_pre_ping=settings.DB_POOL_PRE_PING,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                connect_args={"connect_timeout": settings.DB_CONNECT_TIMEOUT},
            )
            async with new_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("✅ Cloud SQL connected on attempt %d", attempt)
            return new_engine
        except SQLAlchemyError as e:
            last_exc = e
            logger.warning("Retry %d/%d failed: %s", attempt, max_retries, e)
            await asyncio.sleep(wait_seconds)
    raise last_exc if last_exc else Exception("Failed to connect to Cloud SQL")

# ✅ Select engine based on DATABASE_URL
async def get_engine():
    """Get or create the global database engine based on configuration."""
    if state.engine is None:
        if settings.DATABASE_URL and settings.DATABASE_URL.startswith("sqlite"):
            logger.info("Using LOCAL SQLite database.")
            state.engine = await _create_local_engine(settings.DATABASE_URL)
        else:
            logger.info("Using Cloud SQL MySQL database.")
            state.engine = await _create_cloud_engine_with_retry()
        state.session_factory = async_sessionmaker(
            state.engine,
            expire_on_commit=False,
            autoflush=False,
        )
    return state.engine

# ✅ Session factory
# ✅ FastAPI dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    await get_engine()
    if state.session_factory is None:
        raise RuntimeError("Async session factory not initialized")
    session = state.session_factory()
    try:
        yield session
    finally:
        await session.close()

Base = declarative_base()

# ✅ Optional: Async context manager
@asynccontextmanager
async def get_async_db_context():
    await get_engine()
    if state.session_factory is None:
        raise RuntimeError("Async session factory not initialized")
    session = state.session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
