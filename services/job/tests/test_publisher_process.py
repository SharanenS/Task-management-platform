import uuid
from types import SimpleNamespace

import pytest

from app import publisher_process
from app.publisher import PublishFailure


class Context:
    def __enter__(self) -> object:
        return object()

    def __exit__(self, *_: object) -> None:
        return None


class Adapter:
    def __init__(self, failure: PublishFailure | None = None) -> None:
        self.failure = failure
        self.calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    def publish(self, job_id: uuid.UUID, event_id: uuid.UUID) -> None:
        self.calls.append((job_id, event_id))
        if self.failure:
            raise self.failure


def test_empty_poll_is_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(publisher_process, "SessionLocal", Context)
    monkeypatch.setattr(publisher_process, "claim_publications", lambda _session: [])
    assert publisher_process.publish_batch(Adapter()) == 0


def test_success_publishes_only_ids_and_settles(monkeypatch: pytest.MonkeyPatch) -> None:
    job_id, event_id = uuid.uuid4(), uuid.uuid4()
    event = SimpleNamespace(job_id=job_id, id=event_id, lease_token="fixed-test-token")
    settled: list[tuple[uuid.UUID, str]] = []
    monkeypatch.setattr(publisher_process, "SessionLocal", Context)
    monkeypatch.setattr(publisher_process, "claim_publications", lambda _session: [event])
    monkeypatch.setattr(
        publisher_process,
        "settle_publication_success",
        lambda _session, identifier, token: settled.append((identifier, token)),
    )
    adapter = Adapter()
    assert publisher_process.publish_batch(adapter) == 1
    assert adapter.calls == [(job_id, event_id)]
    assert settled == [(event_id, "fixed-test-token")]


@pytest.mark.parametrize(
    "classification", ["CONNECTION_FAILED", "CONFIRMATION_REJECTED", "CONFIRMATION_AMBIGUOUS"]
)
def test_classified_failure_is_scheduled_without_raw_error(
    monkeypatch: pytest.MonkeyPatch, classification: str
) -> None:
    event = SimpleNamespace(job_id=uuid.uuid4(), id=uuid.uuid4(), lease_token="token")
    failures: list[str] = []
    monkeypatch.setattr(publisher_process, "SessionLocal", Context)
    monkeypatch.setattr(publisher_process, "claim_publications", lambda _session: [event])
    monkeypatch.setattr(
        publisher_process,
        "settle_publication_failure",
        lambda _session, _identifier, _token, code: failures.append(code),
    )
    publisher_process.publish_batch(Adapter(PublishFailure(classification)))
    assert failures == [classification]


def test_stop_signal_is_graceful() -> None:
    publisher_process.stopping = False
    publisher_process.request_stop()
    assert publisher_process.stopping
