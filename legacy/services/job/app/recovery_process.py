import signal
import time
from collections.abc import Callable

from sqlalchemy import text

from app.db import SessionLocal
from app.service import recover_expired_executions

POLL_INTERVAL_SECONDS = 1.0
stopping = False


def request_stop(*_: object) -> None:
    global stopping
    stopping = True


def recover_batch() -> int:
    with SessionLocal() as session:
        return len(recover_expired_executions(session))


def run(*, sleeper: Callable[[float], None] = time.sleep) -> None:
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    while not stopping:
        if recover_batch() == 0:
            sleeper(POLL_INTERVAL_SECONDS)


def health() -> None:
    with SessionLocal() as session:
        session.execute(text("SELECT 1"))


if __name__ == "__main__":
    run()
