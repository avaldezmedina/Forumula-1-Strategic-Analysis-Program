from celery import Celery
from app.config import settings

celery_app = Celery(
    "f1_strategy",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    # TODO: research what task_acks_late means and why it matters
    # for reliability when a worker crashes mid-task
    task_acks_late=True,
)
