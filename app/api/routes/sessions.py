from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.base import get_db
from app.workers.tasks import ingest_session_task

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/ingest/{session_key}")
def trigger_ingestion(session_key: int, db: Session = Depends(get_db)):
    """
    Trigger background ingestion for a session.
    This kicks off a Celery task and returns immediately.

    TODO: Implement this endpoint. It should:
    1. Call ingest_session_task.delay(session_key)
    2. Return a response with the task ID so the caller can check status

    Look up: what does .delay() do in Celery?
    What does it return and how do you check task status later?
    """
    raise NotImplementedError


@router.get("/ingest/status/{task_id}")
def get_ingestion_status(task_id: str):
    """
    Check the status of an ingestion task by its Celery task ID.

    TODO: Implement this endpoint.
    Look up: AsyncResult in Celery and how to check task state.
    Possible states: PENDING, STARTED, SUCCESS, FAILURE, RETRY
    """
    raise NotImplementedError
