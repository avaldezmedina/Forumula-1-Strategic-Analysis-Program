from __future__ import annotations

import httpx
from sqlalchemy.exc import OperationalError

from app.workers.celery_app import celery_app
from app.db.base import SessionLocal
from app.db import models
from app.ingestion.client import OpenF1ClientError
from app.ingestion.ingest import ingest_full_session
from app.strategy.pace import compute_all_stint_summaries
from app.strategy.tire_life import compute_tire_life_estimate
from app.strategy.pit_window import compute_pit_window_scores_for_session
from app.replay.builder import build_session_replay


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


def _get_circuit_key_for_session(db, session_key: int) -> int:
    """
    Resolve circuit_key for a session through sessions -> meetings.
    """
    session_obj = (
        db.query(models.Session)
        .filter(models.Session.session_key == session_key)
        .first()
    )

    if session_obj is None:
        raise ValueError(f"No session found for session_key={session_key}")

    meeting = (
        db.query(models.Meeting)
        .filter(models.Meeting.meeting_key == session_obj.meeting_key)
        .first()
    )

    if meeting is None:
        raise ValueError(
            f"No meeting found for session_key={session_key}, "
            f"meeting_key={session_obj.meeting_key}"
        )

    if meeting.circuit_key is None:
        raise ValueError(
            f"Meeting {meeting.meeting_key} for session_key={session_key} "
            "does not have a circuit_key."
        )

    return meeting.circuit_key


def _get_compounds_for_circuit(db, circuit_key: int) -> list[str]:
    """
    Return compounds with persisted stint pace summaries for this circuit.
    """
    rows = (
        db.query(models.StintPaceSummary.compound)
        .join(
            models.Session,
            models.Session.session_key == models.StintPaceSummary.session_key,
        )
        .join(
            models.Meeting,
            models.Meeting.meeting_key == models.Session.meeting_key,
        )
        .filter(models.Meeting.circuit_key == circuit_key)
        .distinct()
        .all()
    )

    return sorted(row[0] for row in rows if row[0])


def _count_stint_summaries(db, session_key: int) -> int:
    return (
        db.query(models.StintPaceSummary)
        .filter(models.StintPaceSummary.session_key == session_key)
        .count()
    )


def _count_tire_life_estimates(db, circuit_key: int) -> int:
    return (
        db.query(models.TireLifeEstimate)
        .filter(models.TireLifeEstimate.circuit_key == circuit_key)
        .count()
    )


def _count_pit_window_scores(db, session_key: int) -> int:
    return (
        db.query(models.PitWindowScore)
        .filter(models.PitWindowScore.session_key == session_key)
        .count()
    )


def _ingest_session(db, session_key: int) -> dict:
    """
    Run ingestion using the actual ingest_full_session contract.

    After ingestion, verify that a Race session row exists. ingest_full_session()
    intentionally returns without persisting non-Race sessions, so the pipeline
    should fail early with a clear message instead of failing later during
    circuit resolution.
    """
    ingest_full_session(db, session_key)

    session_obj = (
        db.query(models.Session)
        .filter(models.Session.session_key == session_key)
        .first()
    )

    if session_obj is None:
        raise ValueError(
            f"No Race session was persisted for session_key={session_key}. "
            "Verify that this OpenF1 session_key corresponds to a Race session."
        )

    return {
        "status": "success",
        "stage": "ingest",
        "session_key": session_key,
    }


def _compute_stint_pace(db, session_key: int) -> dict:
    """
    Compute and persist stint pace summaries for one session.
    """
    compute_all_stint_summaries(db, session_key)

    return {
        "status": "success",
        "stage": "stint_pace",
        "session_key": session_key,
        "summary_count": _count_stint_summaries(db, session_key),
    }


def _compute_tire_life_for_circuit(db, circuit_key: int) -> dict:
    """
    Compute tire-life estimates for every compound represented in the
    circuit's persisted stint pace summaries.
    """
    compounds = _get_compounds_for_circuit(db, circuit_key)

    computed: list[str] = []
    skipped: list[dict[str, str]] = []

    for compound in compounds:
        try:
            compute_tire_life_estimate(db, circuit_key, compound)
            computed.append(compound)
        except ValueError as exc:
            # Expected analytical skip, e.g. insufficient sample size.
            # Do not retry; do not fail the whole circuit-level task.
            skipped.append(
                {
                    "compound": compound,
                    "reason": str(exc),
                }
            )

    return {
        "status": "success",
        "stage": "tire_life",
        "circuit_key": circuit_key,
        "compounds_seen": compounds,
        "compounds_computed": computed,
        "compounds_skipped": skipped,
        "estimate_count": _count_tire_life_estimates(db, circuit_key),
    }


def _compute_pit_windows(db, session_key: int) -> dict:
    """
    Compute and persist pit-window scores for one session.
    """
    compute_pit_window_scores_for_session(db, session_key)

    return {
        "status": "success",
        "stage": "pit_window",
        "session_key": session_key,
        "score_count": _count_pit_window_scores(db, session_key),
    }


def _build_replay(db, session_key: int, force: bool = False) -> dict:
    """
    Build precomputed replay bundle for one session.
    """
    result = build_session_replay(db, session_key, force=force)
    return {
        "status": result.get("status", "success"),
        "stage": "replay",
        "session_key": session_key,
        **{k: v for k, v in result.items() if k not in {"status", "session_key"}},
    }


@celery_app.task(bind=True, max_retries=3)
def ingest_session_task(self, session_key: int) -> dict:
    """
    Ingest one full session.

    Retries only transient OpenF1/API-related failures.
    """
    db = SessionLocal()

    try:
        result = _ingest_session(db, session_key)
        db.commit()
        return result

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
def compute_stint_pace_task(self, session_key: int) -> dict:
    """
    Compute stint pace summaries for a session.

    Retries only transient database operational failures.
    """
    db = SessionLocal()

    try:
        result = _compute_stint_pace(db, session_key)
        db.commit()
        return result

    except OperationalError as exc:
        db.rollback()

        countdown = min(60, 2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def compute_tire_life_task(self, circuit_key: int) -> dict:
    """
    Recompute tire-life estimates for all available compounds at a circuit.

    Retries only transient database operational failures.
    """
    db = SessionLocal()

    try:
        result = _compute_tire_life_for_circuit(db, circuit_key)
        db.commit()
        return result

    except OperationalError as exc:
        db.rollback()

        countdown = min(60, 2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def compute_pit_window_task(self, session_key: int) -> dict:
    """
    Compute pit-window scores for all eligible laps in a session.

    Retries only transient database operational failures.
    """
    db = SessionLocal()

    try:
        result = _compute_pit_windows(db, session_key)
        db.commit()
        return result

    except OperationalError as exc:
        db.rollback()

        countdown = min(60, 2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def build_session_replay_task(self, session_key: int, force: bool = False) -> dict:
    """
    Build precomputed replay bundle for one session.

    Retries transient OpenF1/API and database operational failures.
    """
    db = SessionLocal()

    try:
        result = _build_replay(db, session_key, force=force)
        db.commit()
        return result

    except OpenF1ClientError as exc:
        db.rollback()

        if _is_retryable_openf1_error(exc):
            countdown = min(60, 2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)

        raise

    except OperationalError as exc:
        db.rollback()

        countdown = min(60, 2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def run_full_session_pipeline_task(self, session_key: int) -> dict:
    """
    Run the full historical analytics pipeline for one session.

    Pipeline:
    1. ingest raw session data
    2. resolve circuit_key
    3. compute stint pace summaries
    4. compute circuit-level tire-life estimates
    5. compute pit-window scores
    6. build replay bundle

    Retries only:
    - transient OpenF1/API failures during ingestion
    - transient database operational failures
    """
    db = SessionLocal()

    try:
        ingest_result = _ingest_session(db, session_key)
        db.commit()

        circuit_key = _get_circuit_key_for_session(db, session_key)

        stint_result = _compute_stint_pace(db, session_key)
        db.commit()

        tire_life_result = _compute_tire_life_for_circuit(db, circuit_key)
        db.commit()

        pit_window_result = _compute_pit_windows(db, session_key)
        db.commit()

        # Replay build fetches large volumes of location data from OpenF1 and
        # can be slow.  Run it as a separate queued task so that a 429 during
        # location fetching doesn't cause the entire analytics pipeline to retry
        # from scratch.
        build_session_replay_task.delay(session_key)
        replay_result = {
            "status": "queued",
            "stage": "replay",
            "session_key": session_key,
            "message": "Replay build queued as a background task.",
        }

        return {
            "status": "success",
            "stage": "full_pipeline",
            "session_key": session_key,
            "circuit_key": circuit_key,
            "steps": {
                "ingest": ingest_result,
                "stint_pace": stint_result,
                "tire_life": tire_life_result,
                "pit_window": pit_window_result,
                "replay": replay_result,
            },
        }

    except OpenF1ClientError as exc:
        db.rollback()

        if _is_retryable_openf1_error(exc):
            countdown = min(60, 2 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)

        raise

    except OperationalError as exc:
        db.rollback()

        countdown = min(60, 2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()