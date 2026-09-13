"""Packaged loopback Mail workspace; all persistence uses Mail Core."""
import json
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from knowledge_studio import identity, mail
from knowledge_studio.mail_activity import activity_data, delivery_records
from knowledge_studio.mail_setup import asset_root, validate_root, agent_id
from knowledge_studio import team_sync

ROOT = asset_root() / "mail-web"
FILES = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"), "/app.js": ("app.js", "text/javascript"), "/favicon.svg": ("favicon.svg", "image/svg+xml")}
FILES["/layout.css"] = ("layout.css", "text/css")
UI_AGENT = "human"


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def visible_message(root, message_id):
    return next(
        (item for item in mail.iter_messages(root, UI_AGENT)
         if str(item["meta"].get("message_id", "")) == str(message_id)),
        None,
    )


def reply_recipients(root, thread_id):
    messages = mail.thread_messages(root, thread_id, UI_AGENT)
    if not messages:
        raise ValueError("thread not found")
    latest = messages[-1]
    recipients = sorted(
        {
            value for value in ({str(latest["meta"].get("from", ""))} | set(latest["meta"].get("to", [])))
            if value not in {"@human", "@all", "human", "all", ""}
        }
    )
    if not recipients:
        raise ValueError("thread has no reply recipient")
    return recipients, latest


def _mail_verification(root):
    """Derive Mail verification only from an observed lifecycle, never a heartbeat.

    Evidence is KB-wide: an Agent proves itself by acknowledging one delivery
    or by authoring a reply inside a Thread, whether or not the human can see
    that Thread.  Presence still never implies online or executable.
    """
    messages = list(mail.iter_messages(root))
    deliveries = delivery_records(root, messages)
    verified = {}
    for row in messages:
        meta = row["meta"]
        message_id = str(meta.get("message_id", ""))
        sender = mail._normalise_agent(str(meta.get("from", "")))
        # A reply inside a Thread is lifecycle evidence for its author.
        if str(meta.get("reply_to", "") or "") and sender not in {"@human", "@unknown"}:
            verified.setdefault(sender, {"message_id": message_id, "evidence": "reply"})
        for recipient in meta.get("to", []):
            agent = mail._normalise_agent(str(recipient))
            if agent in {"@human", "@all", "@unknown"}:
                continue
            recipient_delivery = next((item for item in deliveries.get(message_id, []) if item.get("agent_id") == agent), None)
            sessions = recipient_delivery.get("sessions", []) if recipient_delivery else []
            ack = next((session for session in sessions if session.get("acknowledged_at")), None)
            if ack:
                verified[agent] = {"message_id": message_id, "session_id": ack.get("session_id"), "evidence": "acknowledged"}
    return verified


def connection_status(root):
    """Return observed provenance plus explicit Mail lifecycle verification."""
    sessions = []
    agents = {}
    machines = set()
    verification = _mail_verification(root)
    directory = mail.sessions_dir(root)
    if directory.is_dir():
        for path in sorted(directory.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(record, dict):
                continue
            agent = mail._normalise_agent(str(record.get("agent_id", "@unknown")))
            session_id = str(record.get("session_id", path.stem))
            machine = str(record.get("machine_id", "unknown") or "unknown")
            last_seen = str(record.get("last_seen_at", "") or "")
            item = {
                "session_id": session_id,
                "agent_id": agent,
                "machine_id": machine,
                "verification_status": "verified" if agent in verification else "observed",
                "last_observed_at": last_seen,
                "scope": str(record.get("scope", "") or ""),
            }
            if agent in verification:
                item["verification_evidence"] = verification[agent]
            sessions.append(item)
            machines.add(machine)
            if agent != "@human":
                summary = agents.setdefault(agent, {
                    "agent_id": agent,
                    "session_count": 0,
                    "machine_ids": set(),
                    "last_observed_at": "",
                })
                summary["session_count"] += 1
                summary["machine_ids"].add(machine)
                if last_seen > summary["last_observed_at"]:
                    summary["last_observed_at"] = last_seen

    # Message provenance can show a machine even when its Session record has
    # expired or was never registered on this clone.
    for message in mail.iter_messages(root, UI_AGENT):
        sender = mail._normalise_agent(str(message["meta"].get("from", "")))
        if sender not in {"@human", "@unknown"}:
            summary = agents.setdefault(sender, {
                "agent_id": sender,
                "session_count": 0,
                "machine_ids": set(),
                "last_observed_at": "",
            })
            timestamp = str(message["meta"].get("timestamp", "") or "")
            if timestamp > summary["last_observed_at"]:
                summary["last_observed_at"] = timestamp
        machine = str(message["meta"].get("origin_machine_id", "") or "")
        if machine and machine != "unknown":
            machines.add(machine)

    serialised_agents = []
    for summary in sorted(agents.values(), key=lambda item: item["agent_id"]):
        summary = dict(summary)
        summary["machine_ids"] = sorted(summary["machine_ids"])
        summary["verification_status"] = "verified" if summary["agent_id"] in verification else "observed"
        if summary["agent_id"] in verification:
            summary["verification_evidence"] = verification[summary["agent_id"]]
        serialised_agents.append(summary)
    return {
        "schema": "mail.connection-status.v1",
        "knowledge_base": str(root),
        "current_machine_id": identity.normalise_machine_id(),
        "sessions": sessions,
        "agents": serialised_agents,
        "machines": sorted(machines),
        "machine_count": len(machines),
        "sync": {
            "transport": "git",
            "state": "local-files",
            "message": "Mail 文件通过 Git 在机器之间交换；成员页可显式一键同步，不会后台 push/pull。",
        },
    }


def memory_status(root):
    """Return a read-only, bounded projection of the knowledge lifecycle."""
    def files_under(relative, *, exclude=()):
        base = root / relative
        if not base.is_dir():
            return []
        return [
            path for path in base.rglob("*")
            if path.is_file() and path.suffix.lower() == ".md"
            and not any(part in exclude for part in path.relative_to(base).parts)
        ]

    raw = files_under("raw", exclude={"executions", ".logs"})
    drafts = files_under("drafts")
    wiki = files_under("wiki")
    latest = sorted(wiki + drafts, key=lambda path: path.stat().st_mtime, reverse=True)[:12]
    return {
        "schema": "memory.snapshot.v1",
        "counts": {"raw": len(raw), "drafts": len(drafts), "wiki": len(wiki)},
        "lifecycle": ["raw", "candidate", "human_review", "wiki", "recall", "explicit_feedback"],
        "recent": [
            {"path": path.relative_to(root).as_posix(), "kind": "wiki" if "wiki" in path.relative_to(root).parts else "candidate"}
            for path in latest
        ],
    }

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.send_json(403, {"error": "loopback Host required"})
            return
        route = self.path.split("?", 1)[0]
        if route == "/api/mail/activity":
            self.send_json(200, activity_data(self.server.kb_root, UI_AGENT))
            return
        if route == "/api/mail/thread":
            thread_id = parse_qs(urlsplit(self.path).query).get("id", [""])[0]
            rows = mail.thread_messages(self.server.kb_root, thread_id, UI_AGENT)
            if not rows:
                self.send_json(404, {"error": "thread not found"})
                return
            deliveries = delivery_records(self.server.kb_root, rows)
            messages = []
            for row in rows:
                meta = row["meta"]
                state = row.get("state") or {}
                messages.append({**meta, "body": row["body"], "read_at": state.get("read_at"),
                                 "deliveries": deliveries.get(str(meta.get("message_id")), [])})
            self.send_json(200, {"thread_id": thread_id, "messages": messages,
                                 "title": rows[0].get("title", "未命名对话"),
                                 "state": "archived" if all((row.get("state") or {}).get("archived_at") for row in rows) else "open"})
            return
        if route == "/api/mail/status":
            self.send_json(200, connection_status(self.server.kb_root))
            return
        if route == "/api/mail/team":
            self.send_json(200, team_sync.status(self.server.kb_root))
            return
        if route in {"/api/memory", "/api/mail/memory"}:
            self.send_json(200, memory_status(self.server.kb_root))
            return
        if route == "/api/mail/snapshot":
            self.send_json(200, mail.snapshot_data(self.server.kb_root, UI_AGENT))
            return
        entry = FILES.get(route)
        if not entry:
            self.send_error(404)
            return
        data = (ROOT / entry[0]).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", entry[1] + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, value):
        data = json_bytes(value)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > 65536:
            raise ValueError("request body must be between 1 and 65536 bytes")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def do_POST(self):
        allowed_origin = f"http://127.0.0.1:{self.server.server_port}"
        if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}' or self.headers.get('Origin', allowed_origin) != allowed_origin or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.send_json(403, {'error': 'same-origin JSON requests required'})
            return
        route = self.path.split("?", 1)[0]
        if route not in {"/api/mail/send", "/api/mail/reply", "/api/mail/invite", "/api/mail/read", "/api/mail/archive", "/api/mail/unarchive", "/api/mail/team/sync"}:
            self.send_error(404)
            return
        try:
            payload = self.read_json()
            if route == "/api/mail/team/sync":
                result = team_sync.sync(
                    self.server.kb_root,
                    push=bool(payload.get("push", False)),
                    message=str(payload.get("message", "同步 OKS 团队资料")),
                )
                self.send_json(200, result)
                return
            if route == "/api/mail/send":
                title = str(payload.get("title", "")).strip()
                body = str(payload.get("body", "")).strip()
                recipient = str(payload.get("to", "")).strip()
                if not title or not body or not recipient:
                    raise ValueError("title, body and recipient are required")
                recipient = ["@" + agent_id(value) for value in recipient.split(",")]
                if len(title) > 120 or len(body) > 12000:
                    raise ValueError("title/body too long")
                result = mail.write_message(
                    self.server.kb_root,
                    body=body,
                    sender=UI_AGENT,
                    sender_kind="human",
                    recipients=recipient,
                    title=title,
                    origin_session_id=self.server.session_id,
                    origin_machine_id=identity.normalise_machine_id(),
                    delivery_reason="direct",
                    record_kind="message",
                    session_policy="next_prompt",
                )
                self.send_json(201, {"status": "saved", "message_id": result["message_id"], "thread_id": result["thread_id"]})
                return
            if route == "/api/mail/reply":
                thread_id = str(payload.get("thread_id", "")).strip()
                body = str(payload.get("body", "")).strip()
                if not thread_id or not body:
                    raise ValueError("thread_id and body are required")
                recipients, latest = reply_recipients(self.server.kb_root, thread_id)
                result = mail.write_message(
                    self.server.kb_root,
                    body=body,
                    sender=UI_AGENT,
                    sender_kind="human",
                    recipients=recipients,
                    title=f"Re: {latest['title']}",
                    thread_id=thread_id,
                    reply_to=str(latest["meta"].get("message_id", "")),
                    origin_session_id=self.server.session_id,
                    origin_machine_id=identity.normalise_machine_id(),
                    delivery_reason="thread_reply",
                    record_kind="note",
                    session_policy="next_prompt",
                )
                self.send_json(201, {"status": "saved", "message_id": result["message_id"], "thread_id": thread_id})
                return
            if route == "/api/mail/invite":
                thread_id = str(payload.get("thread_id", "")).strip()
                recipient = agent_id(str(payload.get("to", "")).strip())
                body = str(payload.get("body", "")).strip()
                if not thread_id or not body:
                    raise ValueError("thread_id, recipient and body are required")
                if recipient.lower() in {"human", "all", "unknown"}:
                    raise ValueError("Invite a named Agent, not human, all or unknown")
                messages = mail.thread_messages(self.server.kb_root, thread_id, UI_AGENT)
                if not messages:
                    raise ValueError("thread not found")
                latest = messages[-1]
                invited = "@" + recipient
                participants = {
                    "@" + value.lstrip("@").strip()
                    for message in messages
                    for value in ({str(message["meta"].get("from", ""))} | set(message["meta"].get("to", [])))
                    if value and value.lstrip("@").strip().lower() not in {"human", "all", "unknown"}
                }
                if invited.casefold() in {value.casefold() for value in participants}:
                    raise ValueError("Agent is already in this Thread")
                recipients = sorted(participants)
                result = mail.write_message(
                    self.server.kb_root,
                    body=body,
                    sender=UI_AGENT,
                    sender_kind="human",
                    recipients=sorted(set(recipients + [invited])),
                    title=f"邀请 {recipient} 加入对话",
                    thread_id=thread_id,
                    reply_to=str(latest["meta"].get("message_id", "")),
                    origin_session_id=self.server.session_id,
                    origin_machine_id=identity.normalise_machine_id(),
                    delivery_reason="direct",
                    record_kind="note",
                    session_policy="next_prompt",
                )
                self.send_json(201, {"status": "saved", "message_id": result["message_id"], "thread_id": thread_id, "recipients": result["recipients"]})
                return
            if route == "/api/mail/archive":
                thread_id = str(payload.get("thread_id", "")).strip()
                message_id = str(payload.get("message_id", "")).strip()
                target = thread_id or message_id
                if not target:
                    raise ValueError("thread_id or message_id is required")
                selected = [
                    item for item in mail.iter_messages(self.server.kb_root, UI_AGENT)
                    if item["meta"].get("thread_id") == target or item["meta"].get("message_id") == target
                ]
                if not selected:
                    raise ValueError("mail or thread not found")
                archived_at = mail.iso_now()
                for message in selected:
                    message_id = str(message["meta"].get("message_id"))
                    changes = {"archived_at": archived_at, "thread_state": "closed"}
                    if message["path"].parent != mail.messages_dir(self.server.kb_root):
                        # A legacy Markdown file is shared by all recipients.
                        # Seed a new recipient projection from its old read
                        # marker, but never rewrite the shared file.
                        state_path = mail.recipient_state_path(self.server.kb_root, UI_AGENT, message_id)
                        if not state_path.is_file() and str(message["meta"].get("read", "false")).lower() == "true":
                            changes["read_at"] = (
                                message["meta"].get("read_at")
                                or message["meta"].get("timestamp")
                                or mail.iso_now()
                            )
                    if message["path"].parent == mail.messages_dir(self.server.kb_root):
                        mail.update_recipient_state(
                            self.server.kb_root, UI_AGENT, message_id, **changes,
                        )
                    else:
                        mail.update_recipient_state(
                            self.server.kb_root, UI_AGENT, message_id, **changes,
                        )
                self.send_json(200, {"status": "archived", "target": target, "count": len(selected)})
                return
            if route == "/api/mail/unarchive":
                thread_id = str(payload.get("thread_id", "")).strip()
                message_id = str(payload.get("message_id", "")).strip()
                target = thread_id or message_id
                if not target:
                    raise ValueError("thread_id or message_id is required")
                selected = [
                    item for item in mail.iter_messages(self.server.kb_root, UI_AGENT)
                    if item["meta"].get("thread_id") == target or item["meta"].get("message_id") == target
                ]
                if not selected:
                    raise ValueError("mail or thread not found")
                for message in selected:
                    message_id = str(message["meta"].get("message_id"))
                    mail.update_recipient_state(
                        self.server.kb_root, UI_AGENT, message_id,
                        archived_at=None, thread_state="open",
                    )
                self.send_json(200, {"status": "unarchived", "target": target, "count": len(selected)})
                return
            if route == "/api/mail/read":
                message = visible_message(self.server.kb_root, str(payload.get("message_id", "")).strip())
                if not message:
                    raise ValueError("message not found")
                message_id = str(message["meta"].get("message_id", ""))
                if message["path"].parent == mail.messages_dir(self.server.kb_root):
                    state = mail.update_recipient_state(self.server.kb_root, UI_AGENT, message_id, read_at=mail.iso_now())
                else:
                    # Legacy Markdown is shared by all recipients; persist the
                    # read transition in this Agent's projection only.
                    state = mail.update_recipient_state(self.server.kb_root, UI_AGENT, message_id, read_at=mail.iso_now())
                self.send_json(200, {"status": "read", "message_id": message_id, "state": state})
                return
            self.send_error(404)
        except team_sync.TeamSyncError as exc:
            self.send_json(409, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})

def create_server(root: Path, port: int = 3182) -> ThreadingHTTPServer:
    root = validate_root(root)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.kb_root = root
    machine_id = identity.normalise_machine_id()
    machine_token = hashlib.sha256(machine_id.encode("utf-8")).hexdigest()[:12]
    server.session_id = f"mail-ui-{server.server_port}-{machine_token}"
    mail.register_session(
        root,
        server.session_id,
        UI_AGENT,
        scope="mail-web",
        machine_id=machine_id,
    )
    return server
