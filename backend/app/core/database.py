from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.config import settings
from app.core.logging import logger

# SQLAlchemy 2.0 Async Engine
# Configure connection pool settings suitable for enterprise API usage
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,           # Never echo SQL — prevents token values appearing in logs
    hide_parameters=True, # Suppress bound parameter values in error tracebacks
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Async Session Factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency yielding an asynchronous SQLAlchemy database session.
    Automatically handles rollback on exceptions and session closure.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session rollback due to exception: {e}")
            raise
        finally:
            await session.close()

