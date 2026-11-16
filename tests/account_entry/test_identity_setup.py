"""Exercise fresh-import and existing-client setup without real credentials or services."""

import copy
import importlib.util
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVER_DEFAULTS = {"introspection.token.claim": "true", "userinfo.token.claim": "false"}


class Response(io.BytesIO):
    def __init__(self, value=None, status=200):
        super().__init__(json.dumps(value).encode())
        self.status = status


def provider(monkeypatch, tmp_path, *, initially_present=True, drift=None, duplicate=False):
    spec = importlib.util.spec_from_file_location(
        "account_entry_operations", ROOT / "scripts/account-entry-development.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    expected = json.loads(
        (ROOT / "infrastructure/auth/api-audience.json").read_text(encoding="utf-8")
    )
    directory = tmp_path / "infrastructure/auth"
    directory.mkdir(parents=True)
    (directory / "api-audience.json").write_text(json.dumps(expected), encoding="utf-8")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(
        module.auth, "credentials", lambda: {"AUTH_BOOTSTRAP_PASSWORD": "fixture-only-value"}
    )
    actual = copy.deepcopy(expected)
    actual["config"].update(SERVER_DEFAULTS)
    if drift:
        actual["config"].update(drift)
    state = {"present": initially_present, "posts": 0, "revoked": 0, "mapper_reads": 0}

    def urlopen(req, timeout):
        assert timeout == 5
        url = urlsplit(req.full_url)
        assert url.scheme == "http" and url.netloc == "127.0.0.1:8180"
        if url.path.endswith("/token"):
            return Response({"access_token": "fixture-token", "refresh_token": "fixture-refresh"})
        if url.path.endswith("/logout"):
            state["revoked"] += 1
            return Response(status=204)
        assert req.get_header("Authorization") == "Bearer fixture-token"
        if url.path.endswith("/clients"):
            return Response(
                [
                    {
                        "id": "owned-client",
                        "clientId": "taskspace-portals-web",
                        "publicClient": True,
                        "redirectUris": ["http://127.0.0.1:3020/auth/callback"],
                    }
                ]
            )
        assert url.path.endswith("/clients/owned-client/protocol-mappers/models")
        if req.get_method() == "POST":
            assert not state["present"]
            assert json.loads(req.data) == expected
            state["posts"] += 1
            state["present"] = True
            return Response(status=201)
        state["mapper_reads"] += 1
        values = [actual] if state["present"] else []
        return Response(values * (2 if duplicate else 1))

    monkeypatch.setattr(module.request, "urlopen", urlopen)
    return module, state


def test_freshly_imported_mapper_matches_normalized_provider_defaults(monkeypatch, tmp_path):
    module, state = provider(monkeypatch, tmp_path)
    module.configure_audience()
    module.configure_audience()
    assert state["posts"] == 0
    assert state["revoked"] == 2


def test_original_manifest_reproduces_the_strict_comparison_failure(monkeypatch, tmp_path):
    module, state = provider(monkeypatch, tmp_path)
    path = tmp_path / "infrastructure/auth/api-audience.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    for key in SERVER_DEFAULTS:
        value["config"].pop(key)
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(module.IdentityConfigurationError, match="audience_configuration_mismatch"):
        module.configure_audience()
    assert state["posts"] == 0 and state["revoked"] == 1


@pytest.mark.parametrize(
    "drift",
    [
        {"included.custom.audience": "another-api"},
        {"access.token.claim": "false"},
        {"id.token.claim": "true"},
        {"userinfo.token.claim": "true"},
        {"introspection.token.claim": "false"},
        {"unexpected.claim": "true"},
    ],
)
def test_real_mapper_drift_is_rejected_without_overwriting(monkeypatch, tmp_path, drift):
    module, state = provider(monkeypatch, tmp_path, drift=drift)
    with pytest.raises(module.IdentityConfigurationError, match="audience_configuration_mismatch"):
        module.configure_audience()
    assert state["posts"] == 0 and state["revoked"] == 1


def test_duplicate_named_mapper_is_not_accepted(monkeypatch, tmp_path):
    module, state = provider(monkeypatch, tmp_path, duplicate=True)
    with pytest.raises(module.IdentityConfigurationError, match="audience_configuration_mismatch"):
        module.configure_audience()
    assert state["posts"] == 0 and state["revoked"] == 1


def test_mapper_creation_verifies_provider_readback(monkeypatch, tmp_path):
    module, state = provider(monkeypatch, tmp_path, initially_present=False)
    module.configure_audience()
    assert state["posts"] == 1 and state["mapper_reads"] == 2 and state["revoked"] == 1


def test_invalid_new_mapper_readback_is_rejected(monkeypatch, tmp_path):
    module, state = provider(
        monkeypatch, tmp_path, initially_present=False, drift={"access.token.claim": "false"}
    )
    with pytest.raises(module.IdentityConfigurationError, match="audience_configuration_mismatch"):
        module.configure_audience()
    assert state["posts"] == 1 and state["mapper_reads"] == 2 and state["revoked"] == 1
