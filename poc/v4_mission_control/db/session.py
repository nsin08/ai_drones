"""SQLAlchemy engine and session factory for Mission Control v4.

Uses synchronous SQLAlchemy so the existing service layer (which is sync)
works without change. Routes that require a DB session declare it with FastAPI's
Depends(get_db) dependency.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings

_engine = None
_SessionLocal: sessionmaker | None = None


def _build_engine():
    settings = get_settings()
    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def get_engine():
    """Return (and lazily create) the shared SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory() -> sessionmaker:
    """Return (and lazily create) the scoped session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager yielding a committed/rolled-back session.

    Use this in non-FastAPI code (CLI tools, seed scripts, tests).
    """
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
