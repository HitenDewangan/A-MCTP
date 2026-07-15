from celery import Celery

from .config import settings
from .database import init_db

celery_app = Celery(
    "amctp",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=3600,
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# The worker is a separate process (often a separate container) from the
# FastAPI app -- it needs its own call to create the schema, since it never
# hits FastAPI's @app.on_event("startup") handler.
init_db()
