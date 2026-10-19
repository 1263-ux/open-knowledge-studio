"""Run the frontend's model contracts as part of the ordinary pytest suite."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_studio_model_contracts():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable for frontend model contracts")
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, str(Path(__file__).with_name("mail_studio_model.cjs")), str(root / "assets" / "mail-web")],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
