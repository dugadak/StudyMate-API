"""
Database configuration and session management.

Uses SQLAlchemy 2.x with async support for PostgreSQL.
"""

from typing import AsyncGenerator

import structlog
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_database_url, settings

logger = structlog.get_logger(__name__)

# Database engine
engine = create_async_engine(
    get_database_url(),
    echo=settings.DEBUG,
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Metadata for explicit table naming and constraints
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    """Base class for all database models."""
    metadata = metadata


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency to get database session.
    
    Yields:
        AsyncSession: Database session
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error("Database session error", error=str(e))
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_tables() -> None:
    """Create all database tables."""
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they're registered
            from app.models import user, calendar, event, token  # noqa: F401
            
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))
        raise


async def drop_tables() -> None:
    """Drop all database tables (use with caution)."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.warning("All database tables dropped")
    except Exception as e:
        logger.error("Failed to drop database tables", error=str(e))
        raise


class DatabaseManager:
    """Database management utilities."""
    
    @staticmethod
    async def health_check() -> bool:
        """
        Check database connectivity.
        
        Returns:
            bool: True if database is healthy
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute("SELECT 1")
                result.fetchone()
                return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    @staticmethod
    async def get_table_count() -> dict:
        """
        Get row count for all tables.
        
        Returns:
            dict: Table names and their row counts
        """
        try:
            async with AsyncSessionLocal() as session:
                tables = ["users", "calendars", "events", "timetree_tokens", "idempotency_keys"]
                counts = {}
                
                for table in tables:
                    try:
                        result = await session.execute(f"SELECT COUNT(*) FROM {table}")
                        count = result.scalar()
                        counts[table] = count
                    except Exception:
                        counts[table] = "N/A"
                
                return counts
        except Exception as e:
            logger.error("Failed to get table counts", error=str(e))
            return {}
    
    @staticmethod
    async def cleanup_expired_tokens() -> int:
        """
        Clean up expired tokens.
        
        Returns:
            int: Number of cleaned up tokens
        """
        try:
            from datetime import datetime, timezone
            from app.models.token import TimeTreeToken
            
            async with AsyncSessionLocal() as session:
                # Delete expired tokens
                result = await session.execute(
                    "DELETE FROM timetree_tokens WHERE expires_at < $1",
                    [datetime.now(timezone.utc)]
                )
                count = result.rowcount
                await session.commit()
                
                logger.info("Cleaned up expired tokens", count=count)
                return count
        except Exception as e:
            logger.error("Failed to cleanup expired tokens", error=str(e))
            return 0


# Global database manager instance
db_manager = DatabaseManager()