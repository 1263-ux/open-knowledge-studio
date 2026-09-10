"""Small local runtime adapter for Mail.

The filesystem remains the source of truth.  A host may replace this adapter
with a push-capable implementation, while ``FileMailRuntime`` provides a
portable wait/notify contract for Claude, Pi, Codex, and DSH integrations.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from knowledge_studio import mail


RUNTIME_SCHEMA = "mail.runtime.v1"


class FileMailRuntime:
    """Poll canonical Mail files and expose a host-neutral runtime seam."""

    def __init__(self, root: Path, agent_id: str, session_id: str = "", machine_id: str = "") -> None:
        self.root = root
        self.agent_id = agent_id
        self.session_id = session_id or "default"
        self.machine_id = mail.machine_id(machine_id)

    def register(self, *, cwd: str = "", scope: str = "") -> dict[str, Any]:
        path = mail.register_session(self.root, self.session_id, self.agent_id, cwd, scope, self.machine_id)
        return {"schema": RUNTIME_SCHEMA, "session_id": self.session_id, "agent": mail._normalise_agent(self.agent_id), "machine_id": self.machine_id, "path": str(path)}

    def heartbeat(self) -> dict[str, Any]:
        return self.register()

    def list_peers(self) -> list[dict[str, Any]]:
        peers: list[dict[str, Any]] = []
        directory = mail.sessions_dir(self.root)
        if not directory.is_dir():
            return peers
        for path in sorted(directory.glob("*.json")):
            try:
                record = __import__("json").loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            peers.append({
                "session_id": str(record.get("session_id", path.stem)),
                "agent_id": str(record.get("agent_id", "@unknown")),
                "machine_id": str(record.get("machine_id", "unknown")),
                "status": str(record.get("status", "active")),
                "last_seen_at": record.get("last_seen_at"),
                "scope": str(record.get("scope", "")),
            })
        return peers

    def send(self, *, body: str, to: str, title: str = "", notify: bool = False, session_policy: str = "next_prompt", **kwargs: Any) -> dict[str, Any]:
        result = mail.write_message(
            self.root,
            body=body,
            sender=self.agent_id,
            recipients=to,
            title=title,
            origin_session_id=self.session_id,
            origin_machine_id=self.machine_id,
            notify=notify,
            session_policy=session_policy,
            **kwargs,
        )
        return {"schema": RUNTIME_SCHEMA, "status": "queued", "wake_supported": False, **result}

    def delegate(self, *, task: str, to: str, title: str = "", context: str = "", acceptance: str = "", notify: bool = False, evidence_refs: Any = None) -> dict[str, Any]:
        """Submit an intent-level handoff while keeping the file protocol stable."""
        result = mail.delegate_message(
            self.root,
            task=task,
            sender=self.agent_id,
            sender_kind="agent",
            recipients=to,
            title=title,
            context=context,
            acceptance=acceptance,
            origin_session_id=self.session_id,
            origin_machine_id=self.machine_id,
            evidence_refs=evidence_refs,
            notify=notify,
        )
        return {"schema": RUNTIME_SCHEMA, "operation": "delegate", "status": "queued", "wake_supported": False, **result}

    def wait(self, *, timeout: int = 0, limit: int = 10) -> dict[str, Any]:
        # A wait is an active Host Session operation.  Register it before the
        # first scan so every receipt has a matching durable Session identity.
        self.register()
        deadline = time.monotonic() + max(0, min(int(timeout), 300))
        while True:
            found = []
            found_messages = []
            for message in mail.iter_messages(self.root, self.agent_id):
                state = message.get("state") or {}
                message_id = str(message["meta"].get("message_id", ""))
                if not message_id or state.get("archived_at"):
                    continue
                if self.session_id == "default" and not mail._message_unread(message):
                    continue
                if mail.has_delivery_receipt(self.root, self.session_id, message_id):
                    continue
                found.append({
                    "message_id": message_id,
                    "thread_id": str(message["meta"].get("thread_id", "")),
                    "from": str(message["meta"].get("from", "unknown")),
                    "to": list(message["meta"].get("to", [])),
                    "origin_session_id": str(message["meta"].get("origin_session_id", "")),
                    "origin_machine_id": str(message["meta"].get("origin_machine_id", "unknown")),
                    "title": message.get("title", "(no title)"),
                    "body": message.get("body", ""),
                    "timestamp": str(message["meta"].get("timestamp", "")),
                    "notify": str(message["meta"].get("notify", "false")).lower() == "true",
                    "session_policy": str(message["meta"].get("session_policy", "next_prompt")),
                    "evidence_refs": mail.normalise_evidence_refs(message["meta"].get("evidence_refs", [])),
                    "state": state,
                })
                found_messages.append(message)
                if len(found) >= max(1, min(limit, 50)):
                    break
            if found:
                for item, message in zip(found, found_messages):
                    receipt = mail.record_delivery(
                        self.root,
                        self.session_id,
                        message,
                        agent_id=self.agent_id,
                        machine_id=self.machine_id,
                    )
                    item["receipt"] = {
                        "status": receipt.get("status", "presented"),
                        "session_id": receipt.get("session_id", self.session_id),
                        "machine_id": receipt.get("machine_id", self.machine_id),
                        "acknowledged_at": receipt.get("acknowledged_at"),
                    }
                return {
                    "schema": RUNTIME_SCHEMA,
                    "status": "messages",
                    "agent": mail._normalise_agent(self.agent_id),
                    "session_id": self.session_id,
                    "machine_id": self.machine_id,
                    "messages": found,
                }
            if time.monotonic() >= deadline:
                return {"schema": RUNTIME_SCHEMA, "status": "messages" if found else "timeout", "agent": mail._normalise_agent(self.agent_id), "session_id": self.session_id, "machine_id": self.machine_id, "messages": found}
            time.sleep(0.25)

    def ack(self, message_id: str) -> dict[str, Any]:
        return mail.acknowledge_delivery(
            self.root,
            self.session_id,
            message_id,
            agent_id=self.agent_id,
            machine_id=self.machine_id,
        )

    def notify(self, message_id: str) -> dict[str, Any]:
        path = mail.messages_dir(self.root) / f"{mail.safe_id(message_id)}.md"
        message = mail.parse_message(path)
        if not message:
            raise FileNotFoundError(message_id)
        notification = mail.queue_notification(self.root, self.agent_id, message)
        return {
            "schema": RUNTIME_SCHEMA,
            "status": "queued",
            "wake_supported": False,
            "notification": notification,
        }
