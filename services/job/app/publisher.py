from uuid import UUID

from celery import Celery
from kombu.exceptions import ChannelError, OperationalError


class PublishFailure(Exception):
    def __init__(
        self, classification: str = "PUBLICATION_FAILED", *, ambiguous: bool | None = None
    ) -> None:
        super().__init__("Job publication failed.")
        self.classification = "CONFIRMATION_AMBIGUOUS" if ambiguous else classification
        self.ambiguous = self.classification == "CONFIRMATION_AMBIGUOUS"


TASK_NAME = "job.execute_project_task_export"
QUEUE_NAME = "job.execution"
ROUTING_KEY = "job.execute"


class CeleryPublisher:
    def __init__(self, celery: Celery) -> None:
        self.celery = celery

    def publish(self, job_id: UUID, event_id: UUID | None = None) -> None:
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
                **({"task_id": str(event_id)} if event_id else {}),
            )
        except OperationalError as error:
            raise PublishFailure("CONNECTION_FAILED") from error
        except ChannelError as error:
            raise PublishFailure("CONFIRMATION_REJECTED") from error
        except TimeoutError as error:
            raise PublishFailure("CONFIRMATION_AMBIGUOUS") from error


def publisher() -> CeleryPublisher:
    from app.celery_app import celery_app

    return CeleryPublisher(celery_app)
