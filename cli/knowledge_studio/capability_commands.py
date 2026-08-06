"""``oks capability`` — inspect available providers and diagnose environment.

``capability list`` reads ``providers/*/provider.yaml`` and shows what
actions are available.  ``capability doctor`` checks the local environment
(command existence, env vars, Python imports) and reports what's ready,
what's missing, and how to fix it.

Per CONSTITUTION P4, doctor performs only LOCAL checks — no MCP handshake,
no HTTP requests, no API authentication tests.  Remote capability
availability is verified by each Provider's own ``probe.py``.
"""

from __future__ import annotations

import os
import shutil
import sys
from importlib.resources import files
from pathlib import Path
from typing import Any


def _providers_root() -> Path:
    """Return the providers/ resource directory inside the installed package."""
    return Path(str(files("knowledge_studio.providers")))


def _parse_yaml_lines(lines: list[str]) -> dict[str, Any]:
    """Parse simple indented YAML into nested dicts.  Handles up to 3 levels
    of nesting — sufficient for provider.yaml.  No anchors, no lists-of-dicts,
    no multi-line strings."""
    result: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        indent = len(line) - len(line.lstrip())
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if not value:
            # Section header — collect all indented lines that follow
            sub_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                nxt_stripped = nxt.strip()
                if not nxt_stripped or nxt_stripped.startswith("#"):
                    j += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip())
                if nxt_indent <= indent:
                    break  # dedented — end of section
                sub_lines.append(nxt)
                j += 1
            result[key] = _parse_yaml_lines(sub_lines)
            i = j
        else:
            # Scalar value
            if value.startswith("[") and value.endswith("]"):
                value = [
                    v.strip().strip('"').strip("'")
                    for v in value[1:-1].split(",") if v.strip()
                ]
            result[key] = value
            i += 1
    return result


def _load_provider_yaml(path: Path) -> dict[str, Any] | None:
    """Load a provider.yaml as a plain nested dict. Returns None on failure."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    result = _parse_yaml_lines(lines)
    return result if result else None


def _scan_providers(root: Path) -> list[dict[str, Any]]:
    """Scan providers/*/provider.yaml and return parsed entries."""
    if not root.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        yaml_path = child / "provider.yaml"
        if not yaml_path.is_file():
            continue
        data = _load_provider_yaml(yaml_path)
        if data:
            data["_dir"] = str(child.name)
            entries.append(data)
    return entries


# ── capability list ───────────────────────────────────────────────

def capability_list(root: Path | None = None) -> dict[str, Any]:
    """Return structured capability inventory.

    Returns a dict with keys: ``actions`` (set of action names),
    ``providers`` (list of {id, execution, provides, maturity, limits}),
    and ``by_action`` (action → list of provider ids).
    """
    root = root or _providers_root()
    providers = _scan_providers(root)

    all_actions: set[str] = set()
    by_action: dict[str, list[str]] = {}
    provider_list: list[dict[str, Any]] = []

    for p in providers:
        pid = p.get("id", p["_dir"])
        execution = p.get("execution", "unknown")
        label = p.get("label", pid)
        entry = {
            "id": pid,
            "label": label,
            "execution": execution,
            "actions": [],
        }
        # Parse 'provides' section (simple key: maturity format)
        provides = p.get("provides", {})
        if isinstance(provides, dict):
            for action_name, action_info in provides.items():
                entry["actions"].append(action_name)
                all_actions.add(action_name)
                by_action.setdefault(action_name, []).append(pid)
        provider_list.append(entry)

    return {
        "actions": sorted(all_actions),
        "providers": provider_list,
        "by_action": {k: sorted(v) for k, v in sorted(by_action.items())},
    }


# ── capability doctor ─────────────────────────────────────────────

def _check_command(name: str) -> dict[str, Any]:
    """Check if a command exists on PATH."""
    found = shutil.which(name) is not None
    path = shutil.which(name) if found else None
    return {
        "type": "command",
        "name": name,
        "available": found,
        "path": str(path) if path else None,
        "suggestion": None if found else f"install '{name}' via your package manager",
    }


def _check_env_var(name: str) -> dict[str, Any]:
    """Check if an environment variable is set."""
    value = os.environ.get(name)
    available = bool(value)
    return {
        "type": "env_var",
        "name": name,
        "available": available,
        "value": "[set]" if available else None,
        "suggestion": (
            None if available
            else f"set {name}=<value> in your shell profile or .env"
        ),
    }


def _check_python_import(module_name: str, package_name: str | None = None) -> dict[str, Any]:
    """Check if a Python module can be imported."""
    pkg = package_name or module_name
    try:
        __import__(module_name)
        return {
            "type": "python_import",
            "name": pkg,
            "available": True,
            "suggestion": None,
        }
    except ImportError:
        return {
            "type": "python_import",
            "name": pkg,
            "available": False,
            "suggestion": f"pip install {pkg}",
        }


def _check_provider_health(provider: dict[str, Any]) -> list[dict[str, Any]]:
    """Run local health checks for one provider.  NO network calls."""
    checks: list[dict[str, Any]] = []
    pid = provider.get("id", provider.get("_dir", "unknown"))
    execution = provider.get("execution", "")

    requirements = provider.get("requirements", {})
    if isinstance(requirements, str):
        # YAML string — skip
        requirements = {}

    # Check commands
    commands = requirements.get("command", [])
    if isinstance(commands, str):
        commands = [commands]
    optional_commands = requirements.get("optional_commands", [])
    if isinstance(optional_commands, str):
        optional_commands = [optional_commands]

    for cmd in commands:
        checks.append(_check_command(cmd))
    for cmd in optional_commands:
        c = _check_command(cmd)
        c["required"] = False
        checks.append(c)

    # Check env vars
    env_vars = requirements.get("env", [])
    if isinstance(env_vars, str):
        env_vars = [env_vars]
    for env_var in env_vars:
        checks.append(_check_env_var(env_var))

    # Check Python imports (for managed providers)
    pypi_pkg = requirements.get("python_package", "")
    if pypi_pkg:
        checks.append(_check_python_import(pypi_pkg))

    # Special cases
    if pid == "agent-runtime":
        checks.append({
            "type": "note",
            "name": "agent-runtime",
            "available": True,
            "message": "Agent native capability — always available when Agent is running",
        })
    elif pid == "human":
        checks.append({
            "type": "note",
            "name": "human",
            "available": True,
            "message": "Human provider — always available when human is present",
        })
    elif execution == "external":
        # External providers: we only check env vars / API keys, not connectivity
        checks.append({
            "type": "note",
            "name": f"{pid}-remote",
            "available": None,
            "message": (
                f"Remote provider ({execution}) — local env check only. "
                f"Verify connectivity with 'oks capability probe {pid}' "
                f"or the Provider's probe.py."
            ),
        })

    return checks


def capability_doctor(root: Path | None = None) -> dict[str, Any]:
    """Diagnose local environment and report provider health.

    Returns ``{overall, providers: [{id, healthy, checks}]}``.
    PER CONSTITUTION P4: local checks only, no network calls.
    """
    root = root or _providers_root()
    providers = _scan_providers(root)

    results: list[dict[str, Any]] = []
    all_healthy = True

    for p in providers:
        pid = p.get("id", p.get("_dir", "unknown"))
        checks = _check_provider_health(p)
        has_failure = any(
            c.get("available") is False for c in checks
            if c.get("type") not in ("note",)
        )
        if has_failure:
            all_healthy = False

        results.append({
            "id": pid,
            "label": p.get("label", pid),
            "execution": p.get("execution", "unknown"),
            "healthy": not has_failure,
            "checks": checks,
        })

    return {
        "overall": "healthy" if all_healthy else "issues_found",
        "providers": results,
    }
