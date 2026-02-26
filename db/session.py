from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


_ENGINE: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine(db_path: str | Path = "po_matching.db") -> Engine:
    """
    Create (or reuse) a SQLite engine for lightweight persistence if needed.
    """
    global _ENGINE
    if _ENGINE is None:
        db_url = f"sqlite:///{Path(db_path)}"
        _ENGINE = create_engine(db_url, future=True)
    return _ENGINE


def get_session() -> sessionmaker:
    """
    Returns a configured session factory. The current app primarily uses
    in-memory session_state for state, but this allows easy extension.
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return _SessionLocal

