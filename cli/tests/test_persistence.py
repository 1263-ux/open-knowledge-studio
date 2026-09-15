"""Regression tests for shared persistence and standalone hook boundaries."""

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
        list(pool.map(lambda i: persistence.append_jsonl(records, {"i": i}, lock_path=lock), range(16)))
    values = [json.loads(line)["i"] for line in records.read_text(encoding="utf-8").splitlines()]
    assert sorted(values) == list(range(16))


def _hook_script(name: str) -> Path:
    return Path(__file__).parents[2] / "assets" / "hooks" / name


def test_standalone_hooks_use_future_annotations_for_py39():
    """Standalone hooks must remain importable by older host Python versions."""
    import py_compile

    for name in ("user-prompt-recall.py", "post-tool-edit.py"):
        source = _hook_script(name).read_text(encoding="utf-8")
        assert "from __future__ import annotations" in source
        py_compile.compile(str(_hook_script(name)), doraise=True)


def test_standalone_hooks_import_cleanly():
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
            spec.loader.exec_module(module)
            sys.modules.pop(mod_name, None)
    finally:
        sys.path.remove(hooks_dir)


def test_user_prompt_recall_reads_date_organized_mail(tmp_path):
    """The hook must discover Mail stored below date-organized inbox folders."""
    import sys

    hook_path = _hook_script("user-prompt-recall.py")
    sys.path.insert(0, str(hook_path.parent))
    try:
        spec = importlib.util.spec_from_file_location("_upr_test", hook_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        inbox = tmp_path / "mail" / "inbox" / "2026" / "08" / "31"
        inbox.mkdir(parents=True)
        (inbox / "20260831T120000-qoder.md").write_text(
            "---\nfrom: qoder\nread: false\n---\n\n# hi\nbody", encoding="utf-8"
        )
        # Exercise the compatibility reader explicitly; the package-backed
        # path expects canonical Mail metadata and is covered by Mail tests.
        mail_domain = module.mail_domain
        module.mail_domain = None
        mails = module._load_unread_mail(tmp_path, limit=3)
        module.mail_domain = mail_domain
        assert len(mails) == 1
        assert "qoder" in mails[0].get("from", "") or "qoder" in str(mails[0])
    finally:
        sys.path.remove(str(hook_path.parent))
