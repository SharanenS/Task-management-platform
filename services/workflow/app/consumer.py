import time

from kombu import Connection, Consumer, Exchange, Queue

from app.config import settings
from app.db import SessionLocal
from app.observability import (
    correlation_id_ctx,
    parse_traceparent,
    telemetry,
    validate_correlation_id,
)
from app.service import receive_event, submit_pending_actions

EXCHANGE = Exchange("work.domain", type="direct", durable=True)
QUEUE = Queue(
    "workflow.task.completed", exchange=EXCHANGE, routing_key="work.task.completed.v1", durable=True
)


def handle(body: dict[str, object], message: object) -> None:
    msg_headers = getattr(message, "headers", {}) or {}
    raw_corr_id = msg_headers.get("x-correlation-id") or msg_headers.get("X-Correlation-ID")
    corr_id = validate_correlation_id(raw_corr_id)
    token_corr = correlation_id_ctx.set(corr_id)

    raw_tp = msg_headers.get("traceparent")
    parsed_tp = parse_traceparent(raw_tp)
    parent_trace_id = parsed_tp[0] if parsed_tp else None
    parent_span_id = parsed_tp[1] if parsed_tp else None

    span = telemetry.start_span(
        "workflow_consume_event",
        parent_trace_id=parent_trace_id,
        parent_span_id=parent_span_id,
    )
    with span:
        try:
            with SessionLocal() as session:
                receive_event(session, body)
                submit_pending_actions(session)
            message.ack()  # type: ignore[attr-defined]
            telemetry.logger.info("workflow_event_processed", outcome="success")
        except Exception as exc:
            span.set_status("ERROR")
            telemetry.logger.error(
                "workflow_event_processed", outcome="failure", error_code=exc.__class__.__name__
            )
            raise
        finally:
            correlation_id_ctx.reset(token_corr)


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
