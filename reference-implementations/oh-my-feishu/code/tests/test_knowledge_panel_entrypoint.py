"""The optional entrypoint wires a reader and closes its server cleanly."""
import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import feishu_base_worker as worker
from knowledge_studio import mail_web


def test_panel_entrypoint_is_explicitly_read_only_and_closes(tmp_path, monkeypatch):
    knowledge_reader = importlib.import_module("feishu_worker.knowledge_reader")
    review_events = importlib.import_module("feishu_worker.review_events")
    config = object()
    events = []
    monkeypatch.setattr(worker, "parse_args", lambda: SimpleNamespace(command="knowledge-panel", port=3186))
    monkeypatch.setattr(worker, "load_config", lambda args: config)
    monkeypatch.setattr(worker, "configured_knowledge_root", lambda config: tmp_path)
    monkeypatch.setattr(review_events, "_load_studio_store", lambda: None)

    class Source:
        def __init__(self, incoming, root):
            assert incoming is config

    class Server:
        server_port = 3186

        def serve_forever(self):
            events.append("serve")
            raise KeyboardInterrupt

        def server_close(self):
            events.append("close")

    def create(root, port, *, mode, knowledge_source):
        assert root == tmp_path and port == 3186
        assert mode == "reader" and isinstance(knowledge_source, Source)
        return Server()

    monkeypatch.setattr(knowledge_reader, "KnowledgeReader", Source)
    monkeypatch.setattr(mail_web, "create_server", create)
    assert worker.main() == 0
    assert events == ["serve", "close"]
