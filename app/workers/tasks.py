from app.workers.celery_app import celery_app
from app.db.base import SessionLocal


@celery_app.task(bind=True, max_retries=3)
def ingest_session_task(self, session_key: int):
    """
    Celery task that triggers full ingestion for a race session.

    TODO: Implement this task. It should:
    1. Open a database session using SessionLocal()
    2. Call ingest_full_session from app.ingestion.ingest
    3. Close the session when done

    The retry decorator means Celery will automatically retry
    this task up to 3 times if it raises an exception.

    Think about: what kinds of failures should trigger a retry?
    (network errors, API timeouts) vs what failures should NOT
    retry? (bad data that will always fail)

    Look up: self.retry() and how to raise a retry with backoff.
    """
    raise NotImplementedError


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
