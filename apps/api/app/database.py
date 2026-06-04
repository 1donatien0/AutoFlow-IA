from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


def make_engine(url: str) -> AsyncEngine:
    kwargs: dict = {"echo": False}
    if not url.startswith("sqlite"):
        kwargs["pool_pre_ping"] = True
    eng = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):
        # SQLite n'applique pas les clés étrangères par défaut : on les active
        # pour retrouver le comportement de PostgreSQL (et détecter les bugs en dev).
        @event.listens_for(eng.sync_engine, "connect")
        def _fk_pragma(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return eng


engine = make_engine(settings.database_url)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
