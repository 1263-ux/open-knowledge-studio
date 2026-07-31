"""OKS connector — Level-1 extractors, Raw Bundle adapter, and Feishu worker.

Installed under a single top-level name so that generic module names inside
this tree (``i18n``, ``constants``, ``network``, ``route``, ``validator``, ...)
never land in site-packages, where they would collide with unrelated user
packages.

Modules here import each other by bare name (``from i18n import t``), which
works in a source checkout because this directory is on ``sys.path``. The same
injection happens here so the layout keeps working once installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
