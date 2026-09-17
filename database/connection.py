import threading
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import sessionmaker
from config.settings import settings
from database.models import Base

DATABASE_URL = f"sqlite:///{settings.DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"timeout": 30},
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

import contextvars
_thread_local = threading.local()

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """Creates the SQLite database structure if it doesn't exist yet."""
    Base.metadata.create_all(bind=engine)

@contextmanager
def get_db_session():
    """Context manager yielding a thread-local session; auto-closes on exit."""
    if not hasattr(_thread_local, 'session') or _thread_local.session is None:
        _thread_local.session = SessionLocal()
    try:
        yield _thread_local.session
    finally:
        pass

def get_thread_session():
    """Get (or create) the session for the current thread."""
    if not hasattr(_thread_local, 'session') or _thread_local.session is None:
        _thread_local.session = SessionLocal()
    return _thread_local.session

def close_thread_session():
    """Close the thread-local session (call at end of worker threads)."""
    if hasattr(_thread_local, 'session') and _thread_local.session is not None:
        _thread_local.session.close()
        _thread_local.session = None
