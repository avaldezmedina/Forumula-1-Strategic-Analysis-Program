from __future__ import annotations
import httpx
from app.workers.celery_app import celery_app
from app.db.base import SessionLocal
from app.ingestion.client import OpenF1Client, OpenF1ClientError
from app.ingestion.ingest import ingest_full_session, ingest_meeting, ingest_session

def _is_retryable_openf1_error(exc: OpenF1ClientError) -> bool:
    """
    Decide whether an OpenF1ClientError is transient and should be retried.

    Current logic relies on the wrapped cause from client._get().
    A future improvement would be to store status_code directly on
    OpenF1ClientError instead of inspecting __cause__.
    """
    cause = exc.__cause__

    if isinstance(cause, httpx.RequestError):
        return True

    if isinstance(cause, httpx.HTTPStatusError):
        status_code = cause.response.status_code
        return status_code in {429, 500, 502, 503, 504}

    if isinstance(cause, ValueError):
        return True

    return False

@celery_app.task(bind=True, max_retries=3)
def ingest_session_task(self, session_key: int) -> None:
    """
    Ingest one full session starting from session_key.

    Flow:
    1. Fetch session by session_key
    2. Fetch parent meeting by meeting_key
    3. Persist meeting
    4. Persist session
    5. Ingest all child data and commit once inside ingest_full_session
    """
    client = OpenF1Client()
    db = SessionLocal()

    try:
        raw_session = client.get_session(session_key)
        raw_meeting = client.get_meeting(raw_session["meeting_key"])

        ingest_meeting(db, raw_meeting)
        ingest_session(db, raw_session)

        ingest_full_session(db, client, raw_session)

    except OpenF1ClientError as exc:
        db.rollback()

        if _is_retryable_openf1_error(exc):
            countdown = min(60, 2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)

        raise

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def compute_stint_pace_task(self, session_key: int):
    """
    Celery task that computes stint pace summaries for a session.
    Should be triggered after ingest_session_task completes successfully.

    TODO: Implement this task.
    Call the appropriate function from app.strategy.pace
    """
    raise NotImplementedError


@celery_app.task(bind=True, max_retries=3)
def compute_tire_life_task(self, circuit_key: int):
    """
    Celery task that recomputes tire life estimates for a circuit.
    Should be triggered after new race data is ingested for that circuit.

    TODO: Implement this task.
    Call the appropriate function from app.strategy.tire_life
    """
    raise NotImplementedError


@celery_app.task(bind=True, max_retries=3)
def compute_pit_window_task(self, session_key: int):
    """
    Celery task that computes pit window scores for all drivers in a session.
    Depends on stint_pace_summary and tire_life_estimates being populated first.

    TODO: Implement this task.
    Think about: what order do these tasks need to run in?
    Look up Celery task chaining with chain() or link()
    """
    raise NotImplementedError
