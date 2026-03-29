from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import settings

# TODO: understand what pool_pre_ping does and why it matters for long-running apps
engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.
    Yields a session and ensures it is closed after the request completes,
    even if an exception is raised.

    TODO: understand why this is a generator (yield) rather than just returning a session.
    Hint: look up FastAPI dependency injection and context managers.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
