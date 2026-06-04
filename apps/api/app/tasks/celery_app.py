from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "autoflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.workflow_tasks", "app.tasks.maintenance_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Échoue vite si Redis est indisponible au lieu de bloquer la requête HTTP
    broker_connection_timeout=3,
    broker_transport_options={"max_retries": 1},
    beat_schedule={
        "purge-expired-events": {
            "task": "purge_expired_events",
            "schedule": crontab(hour=3, minute=17),
        }
    },
)
