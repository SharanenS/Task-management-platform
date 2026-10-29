import time

from kombu import Connection, Consumer, Exchange, Queue

from app.config import settings
from app.db import SessionLocal
from app.service import receive_event, submit_pending_actions

EXCHANGE = Exchange("work.domain", type="direct", durable=True)
QUEUE = Queue(
    "workflow.task.completed", exchange=EXCHANGE, routing_key="work.task.completed.v1", durable=True
)


def handle(body: dict[str, object], message: object) -> None:
    with SessionLocal() as session:
        receive_event(session, body)
        submit_pending_actions(session)
    message.ack()  # type: ignore[attr-defined]


def main() -> None:
    while True:
        try:
            with Connection(settings.rabbitmq_url, connect_timeout=5) as connection:
                with Consumer(connection, queues=[QUEUE], callbacks=[handle], accept=["json"]):
                    while True:
                        try:
                            connection.drain_events(timeout=5)
                        except TimeoutError:
                            with SessionLocal() as session:
                                submit_pending_actions(session)
        except Exception:
            time.sleep(2)


if __name__ == "__main__":
    main()
