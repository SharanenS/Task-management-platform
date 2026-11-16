from pathlib import Path

from gateway.app import schema


def test_committed_public_schema_matches_executable_schema():
    root = Path(__file__).resolve().parents[2]
    assert (root / "services/gateway/schema.graphql").read_text(
        encoding="utf-8"
    ) == schema.as_str() + "\n"
