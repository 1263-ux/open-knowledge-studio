"""Managed background Mail lifecycle, independent of the launching process."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time
from urllib.request import urlopen

import pytest
from typer.testing import CliRunner

from knowledge_studio.cli import app
from knowledge_studio.mail_web import create_server
from knowledge_studio import mail_server


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def instance(tmp_path):
    (tmp_path / "wiki").mkdir()
    (tmp_path / "drafts").mkdir()
    (tmp_path / "mail").mkdir()
    return tmp_path


def test_detached_server_survives_launcher_exit_and_stops(instance):
    port = free_port()
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]),
               PYTHONDONTWRITEBYTECODE="1")
    script = ("import json; from pathlib import Path; from knowledge_studio.mail_server import start_background; "
              f"print(json.dumps(start_background(Path({str(instance)!r}),{port})))")
    try:
        launched = subprocess.run([sys.executable, "-B", "-X", "utf8", "-c", script],
                                  env=env, capture_output=True, text=True, encoding="utf-8", timeout=25)
        assert launched.returncode == 0, launched.stderr
        result = json.loads(launched.stdout)
        assert result["status"] == "running"
        assert mail_server.server_status(instance, port)["status"] == "running"
        with urlopen(f"http://127.0.0.1:{port}/api/mail/capabilities", timeout=3) as response:
            caps = json.load(response)
        assert caps["read_only"] is True
        assert caps["server_id"] == result["server_id"]
        assert not [p for p in (instance / "mail").rglob("*") if p.is_file()]
        assert mail_server.start_background(instance, port)["reused"] is True
        with pytest.raises(ValueError, match="mode differs"):
            mail_server.start_background(instance, port, mode="collaboration")
    finally:
        mail_server.stop_background(instance, port)
    assert mail_server.server_status(instance, port)["status"] == "stopped"


def test_foreign_foreground_server_is_never_adopted_or_stopped(instance, tmp_path):
    server = create_server(instance, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(ValueError, match="occupied|unmanaged"):
            mail_server.start_background(instance, server.server_port)
        assert mail_server.stop_background(instance, server.server_port)["status"] == "unmanaged"
        assert thread.is_alive()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_other_instance_cannot_reuse_or_stop_owner(instance, tmp_path):
    other = tmp_path / "other"
    (other / "wiki").mkdir(parents=True)
    (other / "mail").mkdir()
    port = free_port()
    try:
        mail_server.start_background(instance, port)
        with pytest.raises(ValueError, match="occupied|unmanaged"):
            mail_server.start_background(other, port)
        assert mail_server.stop_background(other, port)["status"] == "unmanaged"
        # Even a copied PID/token cannot make another instance own this server.
        forged = json.loads((instance / f".oks/mail-web/{port}.json").read_text("utf-8"))
        forged["root"] = str(other.resolve())
        record = other / f".oks/mail-web/{port}.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(forged), encoding="utf-8")
        assert mail_server.stop_background(other, port)["status"] == "unmanaged"
        assert mail_server.server_status(instance, port)["status"] == "running"
    finally:
        mail_server.stop_background(instance, port)


def test_cli_status_and_stop_are_nonblocking(instance):
    runner = CliRunner()
    for action in ["--status", "--stop"]:
        result = runner.invoke(app, ["mail", "serve", action, "--path", str(instance), "--port", str(free_port())])
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["status"] == "stopped"
    invalid = runner.invoke(app, ["mail", "serve", "--background", "--stop", "--path", str(instance)])
    assert invalid.exit_code == 2
    assert not (instance / ".oks").exists()


def test_runtime_state_symlink_cannot_redirect_writes(instance, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = instance / ".oks"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(ValueError, match="symlink|junction"):
        mail_server.start_background(instance, free_port())
    assert list(outside.iterdir()) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows Job lifecycle")
@pytest.mark.parametrize("breakaway", [False, True])
def test_server_survives_actual_launcher_job_termination(instance, breakaway):
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                    ("flags", wintypes.DWORD), ("min_ws", ctypes.c_size_t), ("max_ws", ctypes.c_size_t),
                    ("active", wintypes.DWORD), ("affinity", ctypes.c_size_t),
                    ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]

    class Extended(ctypes.Structure):
        _fields_ = [("basic", Basic), ("io", ctypes.c_ulonglong * 6),
                    ("memory", ctypes.c_size_t * 4)]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    assert job
    limits = Extended()
    limits.basic.flags = 0x2800  # KILL_ON_JOB_CLOSE | BREAKAWAY_OK, like the host.
    assert kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits))
    port = free_port()
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]), PYTHONDONTWRITEBYTECODE="1")
    script = ("import sys,json; from pathlib import Path; from knowledge_studio import mail_server; "
              + ("mail_server.subprocess.CREATE_BREAKAWAY_FROM_JOB=0; " if not breakaway else "") +
              "sys.stdin.readline(); "
              f"print(json.dumps(mail_server.start_background(Path({str(instance)!r}),{port})),flush=True); "
              "sys.stdin.readline(); print('UNEXPECTED_NORMAL_EXIT',flush=True)")
    launcher = subprocess.Popen([sys.executable, "-B", "-X", "utf8", "-c", script],
                                env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8")
    try:
        assert kernel.AssignProcessToJobObject(job, int(launcher._handle))
        launcher.stdin.write("start\n")
        launcher.stdin.flush()
        result = json.loads(launcher.stdout.readline())
        assert result["status"] == "running"
        assert launcher.poll() is None  # Still blocked on its open stdin pipe.
        kernel.CloseHandle(job)
        job = None
        launcher.wait(timeout=5)
        # Windows can report exit code 0 for Job-close termination. The blocked
        # launcher exited without executing its normal-exit sentinel instead.
        assert "UNEXPECTED_NORMAL_EXIT" not in launcher.stdout.read()
        if breakaway:
            assert mail_server.server_status(instance, port)["status"] == "running"
        else:
            deadline = time.monotonic() + 3
            while mail_server.server_status(instance, port)["status"] != "stopped" and time.monotonic() < deadline:
                time.sleep(0.1)
            assert mail_server.server_status(instance, port)["status"] == "stopped"
    finally:
        if job:
            kernel.CloseHandle(job)
        if launcher.poll() is None:
            launcher.terminate()
            launcher.wait(timeout=5)
        for stream in [launcher.stdin, launcher.stdout, launcher.stderr]:
            stream.close()
        mail_server.stop_background(instance, port)
