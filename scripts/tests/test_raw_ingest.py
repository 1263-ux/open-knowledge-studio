import json
import argparse
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import raw_ingest


def test_load_config_uses_environment_override(tmp_path, monkeypatch):
    config = tmp_path / "tools.json"
    config.write_text(json.dumps({"watch_python": "relative/watch.exe"}), encoding="utf-8")
    monkeypatch.setenv("OKS_WATCH_PYTHON", str(tmp_path / "override.exe"))
    loaded = raw_ingest.load_config(config)
    assert loaded["watch_python"] == str(tmp_path / "override.exe")
    assert loaded["document_python"] == sys.executable


def test_load_config_resolves_file_paths_from_repository(tmp_path, monkeypatch):
    for env_name in raw_ingest.ENV_OVERRIDES.values():
        monkeypatch.delenv(env_name, raising=False)
    config = tmp_path / "tools.json"
    config.write_text(json.dumps({"document_python": ".venv/Scripts/python.exe"}), encoding="utf-8")
    loaded = raw_ingest.load_config(config)
    assert loaded["document_python"] == str((raw_ingest.ROOT / ".venv/Scripts/python.exe").resolve())


def test_find_mineru_result_discovers_nested_leaf(tmp_path):
    leaf = tmp_path / "paper" / "auto"
    leaf.mkdir(parents=True)
    (leaf / "paper.md").write_text("body", encoding="utf-8")
    (leaf / "paper_content_list.json").write_text("[]", encoding="utf-8")
    assert raw_ingest.find_mineru_result(tmp_path) == leaf


def test_find_mineru_result_rejects_ambiguous_output(tmp_path):
    for name in ("one", "two"):
        leaf = tmp_path / name
        leaf.mkdir()
        (leaf / f"{name}.md").write_text("body", encoding="utf-8")
        (leaf / f"{name}_content_list.json").write_text("[]", encoding="utf-8")
    with pytest.raises(RuntimeError, match="found 2"):
        raw_ingest.find_mineru_result(tmp_path)


def test_doctor_report_combines_route_checks(monkeypatch):
    monkeypatch.setattr(raw_ingest, "probe_python", lambda name, *_: {"name": name, "status": "ready"})
    monkeypatch.setattr(raw_ingest, "probe_command", lambda name, *_: {"name": name, "status": "ready"})
    monkeypatch.setattr(raw_ingest, "probe_file", lambda name, *_: {"name": name, "status": "ready"})
    report = raw_ingest.doctor_report({
        "watch_python": "watch", "document_python": "doc", "mineru_python": "mineru",
        "formula_python": "formula",
        "ffmpeg": "ffmpeg", "ffprobe": "ffprobe",
    })
    assert report["ready"] is True
    assert len(report["checks"]) == 7


def test_local_bypass_env_preserves_proxy_exclusions(monkeypatch):
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.setenv("NO_PROXY", "example.com")
    env = raw_ingest.local_bypass_env()
    assert env["NO_PROXY"] == "example.com,127.0.0.1,localhost"
    assert env["no_proxy"] == "127.0.0.1,localhost"


def test_adapter_command_keeps_raw_flags(tmp_path):
    args = type("Args", (), {"title": "Demo", "overwrite": True, "benchmark": False})()
    command = raw_ingest.adapter_command("python", "markitdown", "sample.docx", tmp_path, args)
    assert command[:3] == ["python", str(raw_ingest.ADAPTER), "markitdown"]
    assert command[-3:] == ["--title", "Demo", "--overwrite"]


def ingest_args(source, output):
    return argparse.Namespace(
        source=str(source), output=output, title=None, overwrite=False,
        benchmark=False, transcript_only=False, max_frames=3,
        mineru_method="auto", mineru_backend="pipeline",
        formula_secondary=False, formula_max_regions=20,
        hotwords=None, initial_prompt=None, asr_model="auto",
        asr_language=None, video_profile="auto", ocr_roi=None,
        screen_change_threshold=6.0, screen_sample_seconds=1.0,
    )


@pytest.mark.parametrize(
    ("extractor", "source_type", "source_name", "config_key", "adapter_name"),
    [
        ("watch", "video", "sample.mp4", "watch_python", "watch"),
        ("rapidocr", "image", "sample.png", "watch_python", "image"),
        ("markitdown", "document", "sample.docx", "document_python", "markitdown"),
    ],
)
def test_execute_ingest_dispatches_non_pdf_routes(
    tmp_path, monkeypatch, extractor, source_type, source_name, config_key, adapter_name
):
    source = tmp_path / source_name
    source.write_bytes(b"fixture")
    commands = []
    monkeypatch.setattr(raw_ingest, "route_plan", lambda _: {
        "extractor": extractor, "source_type": source_type,
    })
    monkeypatch.setattr(raw_ingest, "run", lambda command, **_: (
        commands.append(list(command))
        or raw_ingest.subprocess.CompletedProcess(command, 0)
    ))
    monkeypatch.setattr(raw_ingest, "validate_bundle", lambda _: {"valid": True})
    config = {
        "watch_python": "watch-python", "document_python": "document-python",
        "mineru_python": "mineru-python", "ffmpeg": "ffmpeg", "ffprobe": "ffprobe",
    }
    raw_ingest.execute_ingest(ingest_args(source, tmp_path / "raw"), config)
    assert commands[0][0] == config[config_key]
    assert commands[0][2] == adapter_name


def test_execute_ingest_runs_mineru_then_adapter(tmp_path, monkeypatch):
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-fixture")
    commands = []
    environments = []
    monkeypatch.setattr(raw_ingest, "route_plan", lambda _: {
        "extractor": "mineru", "source_type": "document",
    })

    def fake_run(command, **kwargs):
        command = list(command)
        commands.append(command)
        environments.append(kwargs.get("env"))
        if "-o" in command:
            result = Path(command[command.index("-o") + 1]) / "paper" / "auto"
            result.mkdir(parents=True)
            (result / "paper.md").write_text("body", encoding="utf-8")
            (result / "paper_content_list.json").write_text("[]", encoding="utf-8")
        return raw_ingest.subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(raw_ingest, "run", fake_run)
    monkeypatch.setattr(raw_ingest, "validate_bundle", lambda _: {"valid": True})
    config = {
        "watch_python": "watch-python", "document_python": "document-python",
        "mineru_python": str(tmp_path / "mineru-venv/Scripts/python.exe"),
        "ffmpeg": "ffmpeg", "ffprobe": "ffprobe",
    }
    raw_ingest.execute_ingest(ingest_args(source, tmp_path / "raw"), config)
    assert "-b" in commands[0] and "pipeline" in commands[0]
    assert environments[0]["NO_PROXY"].endswith("127.0.0.1,localhost")
    assert commands[1][2] == "mineru"
