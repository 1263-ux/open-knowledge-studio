"""Tests for the shared snapshot, append, and read-modify-write contracts."""

import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def _load_hook_persistence():
    path = Path(__file__).parents[2] / "assets" / "hooks" / "_persistence.py"
    spec = importlib.util.spec_from_file_location("oks_hook_persistence", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_core_jsonl_append_is_complete_under_concurrency(tmp_path):
    from knowledge_studio.store import _append_jsonl

    path = tmp_path / "records" / "events.jsonl"
    lock = tmp_path / ".oks" / "locks" / "events.lock"
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: _append_jsonl(path, {"i": i}, lock_path=lock), range(32)))

    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert sorted(item["i"] for item in records) == list(range(32))


def test_core_read_modify_write_keeps_all_updates(tmp_path):
    from knowledge_studio.store import _atomic_write, _locked_atomic_update

    path = tmp_path / "state.json"
    lock = tmp_path / ".oks" / "locks" / "state.lock"
    _atomic_write(path, json.dumps({"count": 0}))

    def increment(current: str) -> str:
        state = json.loads(current)
        state["count"] += 1
        return json.dumps(state)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: _locked_atomic_update(path, increment, lock_path=lock), range(32)))

    assert json.loads(path.read_text(encoding="utf-8"))["count"] == 32


def test_standalone_hook_persistence_matches_contract(tmp_path):
    persistence = _load_hook_persistence()
    snapshot = tmp_path / ".oks" / "state.json"
    persistence.atomic_write_text(snapshot, '{"ok": true}\n')
    assert snapshot.read_text(encoding="utf-8") == '{"ok": true}\n'
    assert not list(snapshot.parent.glob("*.tmp"))

    records = tmp_path / "records" / "inject.jsonl"
    lock = tmp_path / ".oks" / "locks" / "inject.lock"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(
            lambda i: persistence.append_jsonl(records, {"i": i}, lock_path=lock),
            range(16),
        ))
    values = [json.loads(line)["i"] for line in records.read_text(encoding="utf-8").splitlines()]
    assert sorted(values) == list(range(16))


def _hook_script(name: str) -> Path:
    return Path(__file__).parents[2] / "assets" / "hooks" / name


def test_standalone_hooks_use_future_annotations_for_py39():
    """Hook scripts run under the host's python3 (may be 3.9). PEP 604 unions
    like ``Path | None`` require 3.10+ at definition time unless
    ``from __future__ import annotations`` defers them to strings.

    _persistence.py already had it; user-prompt-recall.py / post-tool-edit.py
    regressed once (ModuleNotFoundError + TypeError on 3.9). Pin the guard.
    """
    import py_compile

    for name in ("user-prompt-recall.py", "post-tool-edit.py"):
        source = _hook_script(name).read_text(encoding="utf-8")
        assert "from __future__ import annotations" in source, (
            f"{name} must start with `from __future__ import annotations` "
            f"so PEP 604 annotations survive Python 3.9 hosts"
        )
        py_compile.compile(str(_hook_script(name)), doraise=True)


def test_standalone_hooks_import_cleanly():
    """Loading the hook module must not raise (catches missing `_persistence`
    and bad annotations) under the test interpreter."""
    import sys

    hooks_dir = str(_hook_script("user-prompt-recall.py").parent)
    sys.path.insert(0, hooks_dir)
    try:
        for name in ("user-prompt-recall.py", "post-tool-edit.py"):
            path = _hook_script(name)
            mod_name = f"oks_hook_{path.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, path)
            module = importlib.util.module_from_spec(spec)
            assert spec.loader is not None
            spec.loader.exec_module(module)  # raises on import error
            sys.modules.pop(mod_name, None)
    finally:
        sys.path.remove(hooks_dir)
