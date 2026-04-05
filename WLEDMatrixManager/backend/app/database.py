"""
Async SQLite database setup using SQLAlchemy 2.0
"""

import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# Database path - use /data/ for persistent storage in HA addon
DB_DIR = os.environ.get("DB_DIR", "/data")
DB_PATH = os.path.join(DB_DIR, "wled_matrix.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables and run migrations for new columns."""
    os.makedirs(DB_DIR, exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Lightweight migrations: add columns if missing
    migrations = [
        ("devices", "scale_mode", "VARCHAR(20) DEFAULT 'stretch'"),
    ]
    async with engine.begin() as conn:
        for table, column, col_type in migrations:
            try:
                await conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                )
                logger.info(f"Migration: added {table}.{column}")
            except Exception:
                pass  # Column already exists


async def get_session() -> AsyncSession:
    """Get a database session"""
    async with async_session() as session:
        yield session
