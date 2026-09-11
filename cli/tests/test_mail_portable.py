import json
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from typer.testing import CliRunner

from knowledge_studio.cli import app
from knowledge_studio import mail
from knowledge_studio.mail_setup import install_skill
from knowledge_studio.mail_web import create_server


@pytest.fixture
def kb(tmp_path, monkeypatch):
    root = tmp_path / "共享知识库"
    (root / "mail").mkdir(parents=True)
    (root / "wiki").mkdir()
    monkeypatch.setenv("OKS_MACHINE_ID", "portable-test-machine")
    return root


def test_skill_setup_is_bound_and_non_destructive(kb, tmp_path):
    folder = tmp_path / "host" / "skills"
    result = CliRunner().invoke(app, ["mail", "setup", "--path", str(kb), "--agent", "reviewer", "--skills-dir", str(folder)])
    assert result.exit_code == 0, result.output
    dest = folder / "oks-mail"
    assert json.loads((dest / "binding.json").read_text(encoding="utf-8"))["agent_id"] == "reviewer"
    assert install_skill(kb, "reviewer", folder) == dest
    with pytest.raises(ValueError, match="Existing skill differs"):
        install_skill(kb, "other", folder)
    assert json.loads((dest / "binding.json").read_text(encoding="utf-8"))["agent_id"] == "reviewer"


@pytest.mark.parametrize("identity", ["human", "all", "unknown", "../escape", "", "x/y"])
def test_invalid_agent_binding(kb, tmp_path, identity):
    with pytest.raises(ValueError):
        install_skill(kb, identity, tmp_path / "skills")


def test_independent_skill_sessions_roundtrip(kb, tmp_path):
    # Uses the actual installed oks executable; PYTHONPATH selects this checkout.
    a = install_skill(kb, "writer", tmp_path / "writer-skills") / "scripts" / "mail.py"
    b = install_skill(kb, "reviewer", tmp_path / "reviewer-skills") / "scripts" / "mail.py"
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]), PYTHONIOENCODING="utf-8", OKS_ROOT=str(tmp_path / "wrong"), OKS_AGENT_ID="human")

    def run(helper, *args, success=True):
        result = subprocess.run([sys.executable, str(helper), *args], env=env, cwd=tmp_path,
                                capture_output=True, text=True, encoding="utf-8", timeout=30)
        assert (result.returncode == 0) == success, result.stdout + result.stderr
        return result.stdout

    first = json.loads(run(a, "--session", "writer-s1", "send", "--to", "@reviewer", "--title", "中文讨论", "--body", "保留上下文", "--format", "json"))
    snapshot = json.loads(run(b, "snapshot"))
    thread = snapshot["threads"][0]
    assert thread["thread_id"] == first["thread_id"]
    assert "保留上下文" in run(b, "thread", first["thread_id"])
    run(b, "--session", "reviewer-s1", "reply", first["thread_id"], "--body", "检查完毕", "--format", "json")
    run(a, "--session", "writer-s2", "reply", first["thread_id"], "--body", "新会话继续", "--format", "json")
    rows = json.loads(run(b, "snapshot"))["threads"][0]["messages"]
    assert len(rows) == 3
    assert {r["origin_session_id"] for r in rows} == {"writer-s1", "reviewer-s1", "writer-s2"}
    assert all(r["sender_kind"] == "agent" for r in rows)
    assert {r["from"].lstrip("@") for r in rows} == {"writer", "reviewer"}
    run(a, "send", "--to", "reviewer", "--body", "missing session", success=False)
    run(a, "snapshot", "--path", str(tmp_path / "wrong"), success=False)


def test_web_generic_recipient_and_origin(kb):
    server = create_server(kb, 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def request(route, payload=None, headers=None):
        req = Request(base + route, data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json", **(headers or {})})
        return urlopen(req, timeout=5)

    try:
        with request("/") as response:
            assert b"recipient" in response.read()
        with request("/api/mail/send", {"to": "custom-agent,reviewer", "title": "Hi", "body": "hello"}) as response:
            result = json.load(response)
        assert len(mail.snapshot_data(kb, "custom-agent")["threads"]) == 1
        long_body = "全文" * 3000
        mail.write_message(kb, sender="custom-agent", recipients="human", body=long_body, thread_id=result["thread_id"])
        with request("/api/mail/thread?id=" + result["thread_id"]) as response:
            full = json.load(response)
        assert full["messages"][-1]["body"] == long_body
        mail.write_message(kb, sender="custom-agent", recipients="human", body="reply", thread_id=result["thread_id"])
        with request("/api/mail/reply", {"thread_id": result["thread_id"], "body": "continue"}) as response:
            assert response.status == 201
        with request("/api/mail/invite", {"thread_id": result["thread_id"], "to": "new-agent", "body": "请加入这段对话"}) as response:
            invited = json.load(response)
        assert invited["thread_id"] == result["thread_id"]
        assert "@new-agent" in invited["recipients"]
        invited_thread = mail.thread_messages(kb, result["thread_id"], "new-agent")
        assert len(invited_thread) == 1
        assert invited_thread[-1]["meta"]["from"] == "human"
        assert invited_thread[-1]["body"] == "请加入这段对话"
        for invalid_invite in ["new-agent", "all", "human", "unknown"]:
            with pytest.raises(HTTPError) as error:
                request("/api/mail/invite", {"thread_id": result["thread_id"], "to": invalid_invite, "body": "再次邀请"})
            assert error.value.code == 400
        for invalid_payload in [
            {"thread_id": result["thread_id"], "to": "another-agent", "body": ""},
            {"thread_id": "missing-thread", "to": "another-agent", "body": "加入"},
        ]:
            with pytest.raises(HTTPError) as error:
                request("/api/mail/invite", invalid_payload)
            assert error.value.code == 400
        sender_only = mail.write_message(
            kb, sender="sender-only", recipients="human", body="我先发起这段对话", title="仅发件人"
        )
        with pytest.raises(HTTPError) as error:
            request("/api/mail/invite", {"thread_id": sender_only["thread_id"], "to": "sender-only", "body": "重复邀请"})
        assert error.value.code == 400
        for route, payload, headers in [
            ("/api/mail/send", {"to": "../escape", "title": "bad", "body": "bad"}, {}),
            ("/api/mail/send", {"to": "x", "title": "bad", "body": "bad"}, {"Origin": "http://evil.invalid"}),
            ("/api/mail/snapshot", None, {"Host": "evil.invalid"}),
            ("/api/mail/process", {"message_id": "x"}, {}),
        ]:
            with pytest.raises(HTTPError) as error:
                request(route, payload, headers)
            assert error.value.code in {400, 403, 404}
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_web_connection_status_and_skill_setup(kb, tmp_path):
    server = create_server(kb, 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def request(route, payload=None):
        req = Request(
            base + route,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        return urlopen(req, timeout=5)

    try:
        with request("/api/mail/status") as response:
            status = json.load(response)
        assert status["schema"] == "mail.connection-status.v1"
        assert status["current_machine_id"] == "portable-test-machine"
        assert any(item["agent_id"] == "@human" for item in status["sessions"])

        mail.register_session(kb, "reviewer-s1", "reviewer", machine_id="portable-test-machine")
        with request("/api/mail/status") as response:
            status = json.load(response)
        assert status["agents"][0]["agent_id"] == "@reviewer"
        assert status["agents"][0]["online"] is True

        skills_dir = tmp_path / "host" / "skills"
        with request("/api/mail/setup", {"agent": "reviewer", "skills_dir": str(skills_dir)}) as response:
            result = json.load(response)
        assert result["status"] == "installed"
        assert json.loads((skills_dir / "oks-mail" / "binding.json").read_text(encoding="utf-8"))["agent_id"] == "reviewer"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_web_archive_roundtrip_for_canonical_and_legacy(kb):
    inbox = kb / "mail" / "inbox"
    inbox.mkdir(parents=True)
    legacy_thread = "legacy-thread-roundtrip"
    for message_id, body, read_marker in [
        ("legacy-one", "旧消息一", "false"),
        ("legacy-two", "旧消息二", "false"),
        ("legacy-read", "旧消息已读", "true"),
    ]:
        (inbox / f"{message_id}.md").write_text(
            "---\n"
            f"message_id: {message_id}\n"
            f"thread_id: {legacy_thread}\n"
            "from: @legacy-agent\n"
            "to: @human\n"
            "timestamp: 2026-09-12T00:00:00+00:00\n"
            f"read: {read_marker}\n"
            "type: text\n"
            "---\n"
            f"# 旧对话\n\n{body}\n",
            encoding="utf-8",
        )
    canonical = mail.write_message(
        kb, sender="canonical-agent", recipients="human", title="新格式", body="新格式消息"
    )
    server = create_server(kb, 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def request(route, payload=None):
        req = Request(
            base + route,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        return urlopen(req, timeout=5)

    try:
        with request("/api/mail/snapshot") as response:
            before = json.load(response)
        assert next(t for t in before["threads"] if t["thread_id"] == legacy_thread)["state"] == "open"
        with request("/api/mail/archive", {"thread_id": legacy_thread}) as response:
            assert json.load(response)["status"] == "archived"
        with request("/api/mail/snapshot") as response:
            archived = next(t for t in json.load(response)["threads"] if t["thread_id"] == legacy_thread)
        assert archived["state"] == "archived"
        assert all(message["archived_at"] for message in archived["messages"])
        assert "archived_at:" not in (inbox / "legacy-one.md").read_text(encoding="utf-8")
        with request("/api/mail/unarchive", {"thread_id": legacy_thread}) as response:
            assert json.load(response)["status"] == "unarchived"
        with request("/api/mail/snapshot") as response:
            restored = next(t for t in json.load(response)["threads"] if t["thread_id"] == legacy_thread)
        assert restored["state"] == "open"
        restored_messages = {message["message_id"]: message for message in restored["messages"]}
        assert all(restored_messages[key]["archived_at"] is None for key in ["legacy-one", "legacy-two", "legacy-read"])
        assert restored_messages["legacy-one"]["read_at"] is None
        assert restored_messages["legacy-two"]["read_at"] is None
        assert restored_messages["legacy-read"]["read_at"] == "2026-09-12T00:00:00+00:00"
        other_agent = next(t for t in mail.snapshot_data(kb, "legacy-agent")["threads"] if t["thread_id"] == legacy_thread)
        assert other_agent["state"] == "open"

        with request("/api/mail/read", {"message_id": "legacy-one"}) as response:
            assert json.load(response)["state"]["read_at"]
        read_state = mail.load_state(kb, "human", "legacy-one")
        assert read_state["read_at"]
        with request("/api/mail/archive", {"thread_id": legacy_thread}) as response:
            assert json.load(response)["status"] == "archived"
        with request("/api/mail/unarchive", {"thread_id": legacy_thread}) as response:
            assert json.load(response)["status"] == "unarchived"
        with request("/api/mail/snapshot") as response:
            after_read_roundtrip = next(t for t in json.load(response)["threads"] if t["thread_id"] == legacy_thread)
        after_read_messages = {message["message_id"]: message for message in after_read_roundtrip["messages"]}
        assert after_read_messages["legacy-one"]["read_at"]

        with request("/api/mail/archive", {"thread_id": canonical["thread_id"]}) as response:
            assert json.load(response)["status"] == "archived"
        with request("/api/mail/unarchive", {"thread_id": canonical["thread_id"]}) as response:
            assert json.load(response)["status"] == "unarchived"
        with request("/api/mail/snapshot") as response:
            canonical_restored = next(t for t in json.load(response)["threads"] if t["thread_id"] == canonical["thread_id"])
        assert canonical_restored["state"] == "open"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def test_web_session_id_is_stable_for_bound_port(kb):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    first = create_server(kb, port)
    try:
        first_session = first.session_id
        session_path = mail.sessions_dir(kb) / f"{first_session}.json"
        first_record = json.loads(session_path.read_text(encoding="utf-8"))
    finally:
        first.server_close()
    second = create_server(kb, port)
    try:
        token = hashlib.sha256("portable-test-machine".encode("utf-8")).hexdigest()[:12]
        assert second.session_id == f"mail-ui-{port}-{token}"
        assert second.session_id == first_session
        second_record = json.loads(session_path.read_text(encoding="utf-8"))
        assert second_record["started_at"] == first_record["started_at"]
        assert len(list(mail.sessions_dir(kb).glob("mail-ui-*.json"))) == 1
    finally:
        second.server_close()


def test_web_session_id_separates_machines(kb, monkeypatch):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    first = create_server(kb, port)
    first_id = first.session_id
    first.server_close()
    monkeypatch.setenv("OKS_MACHINE_ID", "another-portable-machine")
    second = create_server(kb, port)
    try:
        assert second.session_id != first_id
        assert len(list(mail.sessions_dir(kb).glob("mail-ui-*.json"))) == 2
    finally:
        second.server_close()


def test_cli_archive_legacy_is_recipient_scoped(kb, monkeypatch):
    inbox = kb / "mail" / "inbox"
    inbox.mkdir(parents=True)
    message_id = "legacy-cli-archive"
    thread_id = "legacy-cli-thread"
    path = inbox / f"{message_id}.md"
    path.write_text(
        "---\n"
        f"message_id: {message_id}\n"
        f"thread_id: {thread_id}\n"
        "from: @legacy-agent\n"
        "to: @human, @reviewer\n"
        "timestamp: 2026-09-12T00:00:00+00:00\n"
        "read: false\n"
        "type: text\n"
        "---\n\n# 旧格式\n\n内容\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OKS_AGENT_ID", "human")
    result = CliRunner().invoke(app, ["mail", "archive", thread_id, "--path", str(kb)])
    assert result.exit_code == 0, result.output
    state = mail.load_state(kb, "human", message_id)
    assert state["archived_at"]
    assert state["read_at"] is None
    assert "read: false" in path.read_text(encoding="utf-8")
    other = mail.snapshot_data(kb, "reviewer")["threads"][0]
    assert other["state"] == "open"
