from fastapi import APIRouter, HTTPException, status
from celery.result import AsyncResult

from app.workers.tasks import ingest_session_task, run_full_session_pipeline_task, build_session_replay_task

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/ingest/status/{task_id}")
def get_ingestion_status(task_id: str):
    """
    Check the status of an ingestion or pipeline task by Celery task ID.

    Common Celery states:
    PENDING, STARTED, SUCCESS, FAILURE, RETRY
    """
    task_result = AsyncResult(task_id, app=ingest_session_task.app)

    response = {
        "task_id": task_id,
        "status": task_result.state,
    }

    if task_result.state == "SUCCESS":
        response["message"] = "Task completed successfully."
        response["result"] = task_result.result

    elif task_result.state == "FAILURE":
        response["message"] = "Task failed."
        response["error"] = str(task_result.result)

    elif task_result.state == "RETRY":
        response["message"] = "Task is retrying."
        if task_result.info:
            response["details"] = str(task_result.info)

    elif task_result.state == "STARTED":
        response["message"] = "Task is currently running."

    elif task_result.state == "PENDING":
        response["message"] = (
            "Task is pending. It may be queued, not yet picked up by a worker, "
            "or the task ID may be unknown."
        )

    else:
        response["message"] = f"Task is in state {task_result.state}."

    return response


@router.post("/pipeline/{session_key}", status_code=status.HTTP_202_ACCEPTED)
def trigger_full_session_pipeline(session_key: int):
    """
    Trigger the full historical session pipeline:
    ingest -> stint pace -> tire life -> pit window scoring.
    """
    try:
        task = run_full_session_pipeline_task.delay(session_key)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue pipeline task for session_key={session_key}: {exc}",
        ) from exc

    return {
        "session_key": session_key,
        "task_id": task.id,
        "status": "queued",
        "message": f"Full analytics pipeline queued for session {session_key}.",
    }


@router.post("/replay/{session_key}", status_code=status.HTTP_202_ACCEPTED)
def trigger_replay_build(session_key: int, force: bool = False):
    """
    Queue replay bundle build for a session.
    """
    try:
        task = build_session_replay_task.delay(session_key, force=force)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue replay build for session_key={session_key}: {exc}",
        ) from exc

    return {
        "session_key": session_key,
        "task_id": task.id,
        "status": "queued",
        "message": f"Replay build queued for session {session_key}.",
    }


@router.get("/")
def list_sessions():
    """
    List ingested race sessions with replay status.
    """
    from app.db.base import SessionLocal
    from app.db import models

    db = SessionLocal()
    try:
        rows = (
            db.query(models.Session, models.Meeting, models.SessionReplay)
            .join(models.Meeting, models.Meeting.meeting_key == models.Session.meeting_key)
            .outerjoin(models.SessionReplay, models.SessionReplay.session_key == models.Session.session_key)
            .order_by(models.Session.date_start.desc())
            .all()
        )

        sessions = []
        for session, meeting, replay in rows:
            sessions.append(
                {
                    "session_key": session.session_key,
                    "meeting_name": meeting.meeting_name,
                    "location": meeting.location,
                    "year": meeting.year,
                    "date_start": session.date_start.isoformat() if session.date_start else None,
                    "replay_status": replay.status if replay else "not_built",
                }
            )

        return {"sessions": sessions}
    finally:
        db.close()


@router.post("/ingest/{session_key}", status_code=status.HTTP_202_ACCEPTED)
def trigger_ingestion(session_key: int):
    """
    Trigger background ingestion for a session only.

    This endpoint queues a Celery task and returns immediately.
    The returned task_id can be used to poll task status.
    """
    try:
        task = ingest_session_task.delay(session_key)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue ingestion task for session_key={session_key}: {exc}",
        ) from exc

    return {
        "session_key": session_key,
        "task_id": task.id,
        "status": "queued",
        "message": f"Ingestion task queued for session {session_key}.",
    }