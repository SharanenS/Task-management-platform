import signal
import time
from collections.abc import Callable

from sqlalchemy import text

from app.db import SessionLocal
from app.publisher import PublishFailure, publisher
from app.service import claim_publications, settle_publication_failure, settle_publication_success

stopping = False
POLL_INTERVAL_SECONDS = 1.0


def request_stop(*_: object) -> None:
    global stopping
    stopping = True


def publish_batch(adapter: object) -> int:
    with SessionLocal() as session:
        events = claim_publications(session)
    for event in events:
        token = event.lease_token
        if token is None:
            continue
        try:
            adapter.publish(event.job_id, event.id)  # type: ignore[attr-defined]
        except PublishFailure as error:
            with SessionLocal() as session:
                settle_publication_failure(session, event.id, token, error.classification)
        else:
            with SessionLocal() as session:
                settle_publication_success(session, event.id, token)
    return len(events)


def run(*, sleeper: Callable[[float], None] = time.sleep) -> None:
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    adapter = publisher()
    while not stopping:
        count = publish_batch(adapter)
        if count == 0:
            sleeper(POLL_INTERVAL_SECONDS)


def health() -> None:
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))


if __name__ == "__main__":
    run()
