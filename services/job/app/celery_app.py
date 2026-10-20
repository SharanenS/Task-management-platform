from celery import Celery
from kombu import Exchange, Queue

from app.config import settings
from app.publisher import QUEUE_NAME, ROUTING_KEY, TASK_NAME

exchange = Exchange("job.execution", type="direct", durable=True)
celery_app = Celery("job", broker=settings.rabbitmq_url, include=["app.tasks"])
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_backend=None,
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
    task_soft_time_limit=25,
    task_time_limit=30,
    broker_connection_timeout=5,
    broker_transport_options={"confirm_publish": True, "max_retries": 0},
    task_queues=(Queue(QUEUE_NAME, exchange=exchange, routing_key=ROUTING_KEY, durable=True),),
    task_routes={TASK_NAME: {"queue": QUEUE_NAME, "routing_key": ROUTING_KEY}},
)
