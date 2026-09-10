"""Packaged loopback Mail workspace; all persistence uses Mail Core."""
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from knowledge_studio import identity, mail
from knowledge_studio.mail_setup import asset_root, validate_root, agent_id
import uuid

ROOT = asset_root() / "mail-web"
FILES = {"/": ("index.html", "text/html"), "/style.css": ("style.css", "text/css"), "/app.js": ("app.js", "text/javascript")}
FILES["/layout.css"] = ("layout.css", "text/css")
UI_AGENT = "human"


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def mark_legacy_read(content):
    parts = content.split('---', 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError('invalid legacy mail frontmatter')
    updated, count = re.subn(r'(?m)^(read:[ \t]*)false([ \t]*\r?)$', r'\g<1>true\2', parts[1])
    return '---'.join([parts[0], updated, parts[2]]) if count else None


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

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.send_json(403, {"error": "loopback Host required"})
            return
        route = self.path.split("?", 1)[0]
        if route == "/api/mail/thread":
            thread_id = parse_qs(urlsplit(self.path).query).get("id", [""])[0]
            rows = mail.thread_messages(self.server.kb_root, thread_id, UI_AGENT)
            if not rows:
                self.send_json(404, {"error": "thread not found"})
                return
            messages = []
            for row in rows:
                meta = row["meta"]
                state = row.get("state") or {}
                messages.append({**meta, "body": row["body"], "read_at": state.get("read_at")})
            self.send_json(200, {"thread_id": thread_id, "messages": messages})
            return
        if route == "/api/mail/connection-guide":
            self.send_json(200, {"knowledge_base": str(self.server.kb_root),
                "instructions": "Use the oks-mail Skill or oks mail setup --help. Discover the requested host's skills directory, bind a named Agent to this knowledge base, and verify its mailbox through the installed helper. Do not claim an online connection from installation alone. Never overwrite unrelated skills. Report what is installed and what remains unavailable."})
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
        if route not in {"/api/mail/send", "/api/mail/reply", "/api/mail/read", "/api/mail/archive"}:
            self.send_error(404)
            return
        try:
            payload = self.read_json()
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
                    session_policy="next_prompt",
                )
                self.send_json(201, {"status": "saved", "message_id": result["message_id"], "thread_id": thread_id})
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
                    if message["path"].parent == mail.messages_dir(self.server.kb_root):
                        mail.update_recipient_state(
                            self.server.kb_root, UI_AGENT, str(message["meta"].get("message_id")),
                            archived_at=archived_at, thread_state="closed",
                        )
                    else:
                        mail.store._locked_atomic_update(
                            message["path"], mark_legacy_read,
                            lock_path=self.server.kb_root / '.oks' / 'locks' / 'mail.lock',
                        )
                self.send_json(200, {"status": "archived", "target": target, "count": len(selected)})
                return
            if route == "/api/mail/read":
                message = visible_message(self.server.kb_root, str(payload.get("message_id", "")).strip())
                if not message:
                    raise ValueError("message not found")
                message_id = str(message["meta"].get("message_id", ""))
                if message["path"].parent == mail.messages_dir(self.server.kb_root):
                    state = mail.update_recipient_state(self.server.kb_root, UI_AGENT, message_id, read_at=mail.iso_now())
                else:
                    mail.store._locked_atomic_update(message['path'], mark_legacy_read, lock_path=self.server.kb_root / '.oks' / 'locks' / 'mail.lock')
                    state = {"read_at": mail.iso_now()}
                self.send_json(200, {"status": "read", "message_id": message_id, "state": state})
                return
            self.send_error(404)
        except (ValueError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})

def create_server(root: Path, port: int = 3182) -> ThreadingHTTPServer:
    root = validate_root(root)
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.kb_root = root
    server.session_id = "mail-ui-" + uuid.uuid4().hex
    return server


