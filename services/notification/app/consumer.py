import time

from kombu import Connection, Consumer, Exchange, Queue

from app.config import settings
from app.db import SessionLocal
from app.service import NotificationError, receive_event

WORK_EXCHANGE = Exchange("work.domain", type="direct", durable=True)
JOB_EXCHANGE = Exchange("job.domain", type="direct", durable=True)
QUEUES = [
    Queue("notification.task.assigned", WORK_EXCHANGE, "work.task.assigned.v1", durable=True),
    Queue("notification.report.terminal", JOB_EXCHANGE, "job.report.terminal.v1", durable=True),
]


def handle(body: object, message: object) -> None:
    try:
        if not isinstance(body, dict):
            raise NotificationError("INVALID_EVENT", "The notification event is invalid.")
        with SessionLocal() as session:
            receive_event(session, body)
        message.ack()  # type: ignore[attr-defined]
    except NotificationError:
        message.reject(requeue=False)  # type: ignore[attr-defined]


def main() -> None:
    while True:
        try:
            with Connection(settings.rabbitmq_url, connect_timeout=5) as connection:
                with Consumer(connection, queues=QUEUES, callbacks=[handle], accept=["json"]):
                    while True:
                        connection.drain_events(timeout=5)
        except TimeoutError:
            continue
        except Exception:
            time.sleep(2)


if __name__ == "__main__":
    main()
