"""Machine provenance stays stable and outside knowledge repositories."""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from knowledge_studio import identity


@pytest.fixture
def record(tmp_path, monkeypatch):
    path = tmp_path / "config" / "machine.json"
    monkeypatch.delenv("OKS_MACHINE_ID", raising=False)
    monkeypatch.setattr(identity, "machine_identity_path", lambda: path)
    return path


def test_persisted_identity_is_stable_across_working_directories(record, tmp_path, monkeypatch):
    first = identity.get_machine_id()
    kb = tmp_path / "kb"
    kb.mkdir()
    monkeypatch.chdir(kb)
    assert identity.normalise_machine_id() == first
    assert list(kb.iterdir()) == []
    assert json.loads(record.read_text(encoding="utf-8")) == {
        "schema_version": identity.MACHINE_ID_SCHEMA, "machine_id": first,
    }


def test_override_precedence_does_not_write(record, monkeypatch):
    monkeypatch.setenv("OKS_MACHINE_ID", "managed-host")
    assert identity.get_machine_id() == "managed-host"
    assert identity.normalise_machine_id("explicit-host") == "explicit-host"
    assert not record.exists()


@pytest.mark.parametrize("value", ["../host", "a/b", "a\\b", "a:b", "a\nb", "a" * 121])
def test_invalid_override_fails_without_writing(record, monkeypatch, value):
    monkeypatch.setenv("OKS_MACHINE_ID", value)
    with pytest.raises(ValueError):
        identity.get_machine_id()
    assert not record.exists()


@pytest.mark.parametrize("content", ["{broken", "[]", '{"machine_id":"bad/path"}'])
def test_malformed_local_record_is_replaced(record, content):
    record.parent.mkdir(parents=True)
    record.write_text(content, encoding="utf-8")
    resolved = identity.get_machine_id()
    assert resolved.startswith("machine_")
    assert identity.get_machine_id() == resolved


def test_atomic_write_failure_is_not_reported_as_identity(record, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("disk unavailable")
    monkeypatch.setattr(identity.store, "_atomic_write", fail)
    with pytest.raises(OSError, match="disk unavailable"):
        identity.get_machine_id()
    assert not record.exists()


def test_concurrent_processes_converge(record):
    script = (
        "from pathlib import Path; from knowledge_studio import identity; "
        f"identity.machine_identity_path = lambda: Path({str(record)!r}); "
        "print(identity.get_machine_id())"
    )
    env = os.environ.copy()
    env.pop("OKS_MACHINE_ID", None)
    def run(_):
        result = subprocess.run(
            [sys.executable, "-c", script], env=env, capture_output=True,
            text=True, encoding="utf-8", timeout=30, check=True,
        )
        return result.stdout.strip()
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(pool.map(run, range(4)))
    assert len(set(values)) == 1
    assert values[0] == identity.get_machine_id()


def test_default_path_uses_user_config(monkeypatch, tmp_path):
    from knowledge_studio import config
    monkeypatch.setattr(config, "config_dir", lambda: tmp_path / "user-config")
    assert identity.machine_identity_path() == tmp_path / "user-config" / "machine.json"
