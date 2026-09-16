"""Local OKS execution identity resolution.

Machine identity is deliberately kept outside a Git-backed knowledge base.  It
identifies one local OKS installation for provenance; it is not authentication
or an authorization credential.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

from knowledge_studio import store


MACHINE_ID_ENV = "OKS_MACHINE_ID"
MACHINE_ID_SCHEMA = "oks.machine.v1"
_MACHINE_ID_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,120}$")


def machine_identity_path() -> Path:
    """Return the user-level identity path, outside any KB checkout."""
    from knowledge_studio.config import config_dir

    return config_dir() / "machine.json"


def _normalise_machine_id(value: str) -> str:
    candidate = str(value or "").strip()
    if not _MACHINE_ID_RE.fullmatch(candidate):
        raise ValueError(
            "machine_id must contain only letters, numbers, '.', '_', '@', or '-' "
            "and be at most 120 characters"
        )
    return candidate


def _read_persisted(path: Path) -> str:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(record, dict):
        return ""
    value = str(record.get("machine_id", "") or "").strip()
    return _normalise_machine_id(value) if value and _MACHINE_ID_RE.fullmatch(value) else ""


def get_machine_id() -> str:
    """Resolve the stable local Machine identity.

    An explicit environment value is useful for managed Hosts and isolated
    tests.  Otherwise a random opaque value is generated once in the user-level
    OKS directory and reused across KBs and sessions.
    """
    override = os.environ.get(MACHINE_ID_ENV, "").strip()
    if override:
        return _normalise_machine_id(override)

    path = machine_identity_path()
    if path.is_file():
        persisted = _read_persisted(path)
        if persisted:
            return persisted

    # Two first-use processes must converge on one local identity.  The lock
    # lives beside the user-level record and never enters a KB checkout.
    with store._file_lock(path.with_name(".machine.lock")):
        if path.is_file():
            persisted = _read_persisted(path)
            if persisted:
                return persisted
        machine_id = f"machine_{uuid.uuid4().hex[:16]}"
        store._atomic_write(
            path,
            json.dumps(
                {
                    "schema_version": MACHINE_ID_SCHEMA,
                    "machine_id": machine_id,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        return machine_id


def normalise_machine_id(value: str = "") -> str:
    """Validate an explicit ID or resolve the current local Machine ID."""
    return _normalise_machine_id(value) if str(value or "").strip() else get_machine_id()
