from uuid import UUID

from celery import Celery
from kombu.exceptions import OperationalError

from app.service import PublishFailure

TASK_NAME = "job.execute_project_task_export"
QUEUE_NAME = "job.execution"
ROUTING_KEY = "job.execute"


class CeleryPublisher:
    def __init__(self, celery: Celery) -> None:
        self.celery = celery

    def publish(self, job_id: UUID) -> None:
        try:
            self.celery.send_task(
                TASK_NAME,
                args=[str(job_id)],
                queue=QUEUE_NAME,
                routing_key=ROUTING_KEY,
                serializer="json",
                retry=False,
                delivery_mode=2,
                confirm_publish=True,
            )
        except OperationalError as error:
            raise PublishFailure(ambiguous=False) from error
        except TimeoutError as error:
            raise PublishFailure(ambiguous=True) from error


def publisher() -> CeleryPublisher:
    from app.celery_app import celery_app

    return CeleryPublisher(celery_app)
