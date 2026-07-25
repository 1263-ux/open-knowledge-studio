#!/usr/bin/env python3
"""Run an explicitly selected extractor and emit an OKS Raw bundle.

The Agent remains the orchestrator: it selects a subcommand before invoking
this Level-1 capability.  The adapter may call mature external extractors, but
it never summarizes, corrects, grades, or promotes source content to Draft or
Wiki.  Its contract is faithful extraction plus provenance and evidence.
"""

from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import importlib.util
import ipaddress
import json
import os
import re
import socket
import ssl
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import asdict
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener


SCHEMA_VERSION = "raw-multimodal/v0.1"
FETCH_RECEIPT_VERSION = "oks-fetch-receipt/v0.1"
PLUGIN_VERSION = "0.1.0"
_WATCH_OVERRIDE_LOCK = threading.Lock()


def emit_json(value: Any, *, indent: int | None = None) -> None:
    """Write UTF-8 JSON without depending on the Windows console code page."""
    payload = json.dumps(value, ensure_ascii=False, indent=indent) + "\n"
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(payload.encode("utf-8"))
        buffer.flush()
        return
    sys.stdout.write(payload)
    sys.stdout.flush()


def emit_progress(enabled: bool, phase: str, fraction: float, eta_seconds: int | None) -> None:
    """Emit machine-readable progress on stderr without corrupting CLI JSON output."""
    if not enabled:
        return
    payload = {
        "event": "progress",
        "phase": phase,
        "percent": round(max(0.0, min(1.0, fraction)) * 100, 1),
        "estimated_remaining_seconds": eta_seconds,
    }
    sys.stderr.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oks-connector", description=__doc__)
    parser.add_argument(
        "--version",
        action="version",
        version=f"oks-connector {PLUGIN_VERSION}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    mineru = subparsers.add_parser(
        "mineru", help="Package an existing MinerU result directory."
    )
    mineru.add_argument("result_dir", type=Path)
    mineru.add_argument("--source", type=Path, required=True)
    mineru.add_argument("--output", type=Path, required=True)
    mineru.add_argument("--title")
    mineru.add_argument("--extractor-version", default="unknown")
    mineru.add_argument("--formula-candidates", type=Path)
    mineru.add_argument("--warning", action="append", default=[])
    mineru.add_argument("--benchmark", action="store_true")
    mineru.add_argument("--overwrite", action="store_true")

    markitdown = subparsers.add_parser(
        "markitdown",
        help="Run MarkItDown or package an existing MarkItDown Markdown result.",
    )
    markitdown.add_argument("source", type=Path)
    markitdown.add_argument("--markdown", type=Path)
    markitdown.add_argument("--output", type=Path, required=True)
    markitdown.add_argument("--title")
    markitdown.add_argument("--extractor-version", default="unknown")
    markitdown.add_argument("--warning", action="append", default=[])
    markitdown.add_argument("--benchmark", action="store_true")
    markitdown.add_argument("--overwrite", action="store_true")

    watch = subparsers.add_parser(
        "watch", help="Run Watch Skill and package its evidence as Raw."
    )
    watch.add_argument("source")
    watch.add_argument("--source-file", type=Path)
    watch.add_argument("--output", type=Path, required=True)
    watch.add_argument("--title")
    watch.add_argument("--extractor-version", default="unknown")
    watch.add_argument("--max-frames", type=int, default=12)
    watch.add_argument("--hotwords")
    watch.add_argument("--initial-prompt")
    watch.add_argument("--asr-model", default="auto")
    watch.add_argument("--asr-language")
    watch.add_argument(
        "--video-profile", choices=("auto", "speech", "shots", "screen"), default="auto"
    )
    watch.add_argument("--ocr-roi")
    watch.add_argument("--screen-change-threshold", type=float, default=6.0)
    watch.add_argument("--screen-sample-seconds", type=float, default=1.0)
    watch.add_argument(
        "--evidence-tier", choices=("quick", "forensic"), default="forensic",
        help="quick keeps transcript-only extraction; forensic uses subtitle topic anchors before visual evidence.",
    )
    watch.add_argument("--progress", action="store_true", help="Write JSONL progress events to stderr.")
    watch.add_argument("--timeout-seconds", type=float, help="Deadline supplied by ingest for progress ETA reporting.")
    watch.add_argument("--transcript-only", action="store_true")
    watch.add_argument("--no-local-whisper", action="store_true")
    watch.add_argument(
        "--subtitle-langs",
        default="zh.*,ai-zh,en.*",
        help="Caption language patterns passed to Watch/yt-dlp.",
    )
    watch.add_argument("--warning", action="append", default=[])
    watch.add_argument("--benchmark", action="store_true")
    watch.add_argument("--overwrite", action="store_true")

    watch_result = subparsers.add_parser(
        "watch-result", help="Package an exported Watch Skill JSON result."
    )
    watch_result.add_argument("result", type=Path)
    watch_result.add_argument("--source", required=True)
    watch_result.add_argument("--source-file", type=Path)
    watch_result.add_argument("--output", type=Path, required=True)
    watch_result.add_argument("--title")
    watch_result.add_argument("--extractor-version", default="unknown")
    watch_result.add_argument("--warning", action="append", default=[])
    watch_result.add_argument("--benchmark", action="store_true")
    watch_result.add_argument("--overwrite", action="store_true")

    image = subparsers.add_parser(
        "image", help="Run RapidOCR and package one image as Raw."
    )
    image.add_argument("source", type=Path)
    image.add_argument("--output", type=Path, required=True)
    image.add_argument("--title")
    image.add_argument("--extractor-version", default="unknown")
    image.add_argument("--min-confidence", type=float, default=0.5)
    image.add_argument("--ocr-roi", help="OCR region x1,y1,x2,y2 in source pixels.")
    image.add_argument("--warning", action="append", default=[])
    image.add_argument("--benchmark", action="store_true")
    image.add_argument("--overwrite", action="store_true")

    ingest = subparsers.add_parser(
        "ingest",
        help="Route one supported source to its installed extractor and emit a Raw bundle.",
    )
    ingest.add_argument("source")
    ingest.add_argument("--output", type=Path)
    ingest.add_argument("--title")
    ingest.add_argument(
        "--mode",
        choices=("quick", "forensic", "fast", "full"),
        default="quick",
        help="quick (legacy: fast) uses captions only; forensic (legacy: full) adds subtitle-anchored visual evidence.",
    )
    ingest.add_argument(
        "--subtitle-langs",
        default="zh.*,ai-zh,en.*",
        help="Caption language patterns passed to Watch/yt-dlp.",
    )
    ingest.add_argument("--mineru-backend", default="pipeline")
    ingest.add_argument("--mineru-method", default="auto")
    ingest.add_argument("--overwrite", action="store_true")
    ingest.add_argument(
        "--timeout-seconds", type=float,
        help="Whole extractor deadline. Defaults to 120 seconds for quick and 900 seconds for forensic.",
    )
    ingest.add_argument("--progress", action="store_true", help="Write JSONL progress events to stderr.")

    route = subparsers.add_parser(
        "route", help="Inspect a local source or URL and print the Raw route plan."
    )
    route.add_argument("source")

    probe = subparsers.add_parser(
        "probe",
        help="Safely inspect one public HTTP(S) URL and emit a Fetch Receipt.",
    )
    probe.add_argument("source")
    probe.add_argument("--timeout", type=float, default=15.0)
    probe.add_argument("--max-bytes", type=int, default=64 * 1024)
    probe.add_argument("--max-redirects", type=int, default=5)

    fetch = subparsers.add_parser(
        "fetch",
        help="Safely download one public HTTP(S) source snapshot and emit a Fetch Receipt.",
    )
    fetch.add_argument("source")
    fetch.add_argument("--output", type=Path, required=True)
    fetch.add_argument("--timeout", type=float, default=30.0)
    fetch.add_argument("--max-bytes", type=int, default=64 * 1024 * 1024)
    fetch.add_argument("--max-redirects", type=int, default=5)
    fetch.add_argument("--overwrite", action="store_true")

    validate = subparsers.add_parser(
        "validate", help="Validate an existing Raw bundle without modifying it."
    )
    validate.add_argument("bundle", type=Path)

    finalize_v2 = subparsers.add_parser(
        "finalize-v2",
        help="Add the Raw Bundle v0.2 manifest, source snapshot, provenance, and run journal to a validated v0.1 bundle.",
    )
    finalize_v2.add_argument("bundle", type=Path)
    finalize_v2.add_argument("--capture-envelope", type=Path, required=True)
    finalize_v2.add_argument("--processing-run", type=Path, required=True)
    finalize_v2.add_argument("--source", type=Path)

    validate_v2 = subparsers.add_parser(
        "validate-v2", help="Validate Raw Bundle v0.2 structure and provenance invariants."
    )
    validate_v2.add_argument("bundle", type=Path)

    check = subparsers.add_parser(
        "check",
        help="验证提取器环境是否可用（Python 版本 + 模块导入）。",
    )
    check.add_argument(
        "extractor",
        nargs="?",
        choices=["watch", "rapidocr", "markitdown", "mineru", "all"],
        default="all",
    )
    check.add_argument("--minimal", action="store_true", help="仅输出版本兼容性检查，不逐个验证提取器。")
    return parser


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")
            count += 1
    return count


def exactly_one(root: Path, pattern: str) -> Path:
    matches = sorted(root.rglob(pattern))
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one {pattern!r} under {root}, found {len(matches)}"
        )
    return matches[0]


def prepare_output(path: Path, overwrite: bool) -> Path:
    path = path.expanduser().resolve()
    if path.exists():
        if not overwrite:
            raise FileExistsError(f"output already exists: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True)
    return path


def source_identity(
    source: str,
    source_file: Path | None = None,
    content_file: Path | None = None,
) -> dict[str, Any]:
    local = source_file
    if local is None:
        candidate = Path(source).expanduser()
        if candidate.is_file():
            local = candidate
    if local is not None:
        local = local.expanduser().resolve()
        if not local.is_file():
            raise FileNotFoundError(local)
        identity = {
            "local_path": str(local),
            "url": None if source == str(local) else source if is_url(source) else None,
            "platform": platform_for(source),
            "content_sha256": sha256_file(local),
            "content_hash_status": "verified",
        }
        if is_url(source):
            identity["source_url_sha256"] = hashlib.sha256(
                source.encode("utf-8")
            ).hexdigest()
        return identity
    if not is_url(source):
        raise FileNotFoundError(source)
    verified_content = None
    if content_file is not None:
        candidate_content = content_file.expanduser().resolve()
        if candidate_content.is_file():
            verified_content = sha256_file(candidate_content)
    return {
        "local_path": None,
        "url": source,
        "platform": platform_for(source),
        "source_url_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "content_sha256": verified_content,
        "content_hash_status": "verified" if verified_content else "unavailable",
    }


from route import is_url, platform_for, route_plan
from digest import write_digest, update_raw_index
from i18n import t


class ProbeError(RuntimeError):
    """One stable, user-facing URL probe failure."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def normalize_public_http_url(value: str) -> str:
    """Normalize a public HTTP(S) URL without treating it as authorization."""
    candidate, _fragment = urldefrag(value.strip())
    parsed = urlparse(candidate)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ProbeError("INVALID_URL", "only http and https URLs are supported")
    if not parsed.hostname:
        raise ProbeError("INVALID_URL", "URL has no hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ProbeError("INVALID_URL", "credentials embedded in URLs are not accepted")
    try:
        _ = parsed.port
    except ValueError as exc:
        raise ProbeError("INVALID_URL", str(exc)) from exc
    return parsed._replace(scheme=parsed.scheme.lower()).geturl()


def assert_public_network_target(url: str) -> list[str]:
    """Resolve a URL and reject loopback, private, link-local and reserved targets."""
    parsed = urlparse(url)
    assert parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(
            parsed.hostname, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as exc:
        raise ProbeError("DNS_FAILED", str(exc), retryable=True) from exc
    resolved: list[str] = []
    for address in addresses:
        raw_ip = address[4][0].split("%", 1)[0]
        ip = ipaddress.ip_address(raw_ip)
        if not ip.is_global:
            raise ProbeError(
                "INVALID_URL",
                f"target resolves to a non-public address: {ip.compressed}",
            )
        if ip.compressed not in resolved:
            resolved.append(ip.compressed)
    if not resolved:
        raise ProbeError("DNS_FAILED", "hostname resolved to no usable address", retryable=True)
    return resolved


class SafeProbeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, max_redirects: int) -> None:
        super().__init__()
        self.max_redirects = max_redirects
        self.redirects: list[dict[str, Any]] = []

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> Request | None:
        if len(self.redirects) >= self.max_redirects:
            raise ProbeError("REDIRECT_LOOP", "redirect limit exceeded")
        target = normalize_public_http_url(urljoin(req.full_url, newurl))
        assert_public_network_target(target)
        self.redirects.append({"status": code, "from": req.full_url, "to": target})
        return super().redirect_request(req, fp, code, msg, headers, target)


def _header_value(headers: Any, name: str) -> str | None:
    value = headers.get(name) if headers is not None else None
    return str(value) if value is not None else None


def _looks_like_challenge(sample: bytes, final_url: str | None = None) -> bool:
    text = sample.decode("utf-8", errors="ignore").lower()
    strong_markers = (
        "cf-chl-",
        "cloudflare challenge",
        "challenges.cloudflare.com",
        "cf-turnstile",
        "g-recaptcha",
        "h-captcha",
        "id=\"captcha\"",
        "id='captcha'",
    )
    if any(marker in text for marker in strong_markers):
        return True
    if final_url:
        parsed = urlparse(final_url)
        location = f"{parsed.path}?{parsed.query}".lower()
        return "captcha" in location or "challenge" in location
    return False


def _looks_script_only(sample: bytes) -> bool:
    text = sample.decode("utf-8", errors="ignore")
    without_scripts = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    visible = re.sub(r"\s+", " ", without_tags).strip()
    return len(visible) < 80 and bool(re.search(r"<script\b", text, flags=re.I))


def _error_receipt(
    source: str,
    normalized: str | None,
    code: str,
    message: str,
    *,
    retryable: bool,
    started_at: str,
    redirects: list[dict[str, Any]] | None = None,
    http_status: int | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": FETCH_RECEIPT_VERSION,
        "status": "failed_retryable" if retryable else "failed_final",
        "source_url": source,
        "normalized_url": normalized,
        "final_url": redirects[-1]["to"] if redirects else normalized,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "fetch_mode": "http_probe",
        "http_status": http_status,
        "redirects": redirects or [],
        "error": {"code": code, "message": message, "retryable": retryable},
        "next_action": "retry" if retryable else "user_review",
    }


def probe_url(
    source: str,
    *,
    timeout: float = 15.0,
    max_bytes: int = 64 * 1024,
    max_redirects: int = 5,
    opener: Any | None = None,
    resolved_addresses: list[str] | None = None,
) -> dict[str, Any]:
    """Inspect one URL without bypassing authentication or anti-bot controls."""
    started_at = datetime.now(timezone.utc).isoformat()
    normalized: str | None = None
    redirect_handler = SafeProbeRedirectHandler(max_redirects)
    try:
        if timeout <= 0 or max_bytes <= 0 or max_redirects < 0:
            raise ProbeError("INVALID_ARGUMENT", "probe limits must be positive")
        normalized = normalize_public_http_url(source)
        route = route_plan(normalized)
        if route["platform"] in {"bilibili", "douyin", "youtube"}:
            finished_at = datetime.now(timezone.utc).isoformat()
            return {
                "schema_version": FETCH_RECEIPT_VERSION,
                "status": "ok",
                "source_url": source,
                "normalized_url": normalized,
                "final_url": normalized,
                "started_at": started_at,
                "finished_at": finished_at,
                "fetch_mode": "platform_route",
                "http_status": None,
                "content_type": None,
                "content_length": None,
                "sample_bytes": 0,
                "sample_truncated": False,
                "sample_sha256": hashlib.sha256(b"").hexdigest(),
                "resolved_addresses": [],
                "redirects": [],
                "route_plan": route,
                "robots": {
                    "checked": False,
                    "reason": "known platform URLs are delegated without a generic HTTP crawl",
                },
                "error": None,
                "next_action": "platform_extractor",
            }
        addresses = resolved_addresses or assert_public_network_target(normalized)
        client = opener or build_opener(redirect_handler)
        request = Request(
            normalized,
            headers={
                "User-Agent": f"oks-connector/{PLUGIN_VERSION} (+single-url-probe)",
                "Accept": "text/html,application/xhtml+xml,application/pdf,image/*,audio/*,video/*,*/*;q=0.1",
            },
            method="GET",
        )
        with client.open(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            final_url = normalize_public_http_url(response.geturl())
            if not redirect_handler.redirects and final_url != normalized:
                assert_public_network_target(final_url)
            content_type = (_header_value(response.headers, "Content-Type") or "").split(";", 1)[0].strip().lower()
            content_length_text = _header_value(response.headers, "Content-Length")
            content_length = int(content_length_text) if content_length_text and content_length_text.isdigit() else None
            sample = response.read(max_bytes + 1)
        sample_truncated = len(sample) > max_bytes
        sample = sample[:max_bytes]
        route = route_plan(final_url)
        next_action = "direct_http_snapshot"
        status_name = "ok"
        error: dict[str, Any] | None = None
        if _looks_like_challenge(sample, final_url):
            status_name = "needs_user_action"
            next_action = "visible_browser_or_manual_snapshot"
            error = {
                "code": "CHALLENGE_REQUIRED",
                "message": "challenge or CAPTCHA detected; automatic bypass is not attempted",
                "retryable": False,
            }
        elif content_length is not None and content_length > max_bytes and route["source_type"] == "unknown":
            next_action = "review_size_before_download"
        elif content_type in {"text/html", "application/xhtml+xml"} and _looks_script_only(sample):
            next_action = "browser_public"
            error = {
                "code": "JS_RENDER_REQUIRED",
                "message": "HTTP response contains little visible text and requires browser rendering",
                "retryable": False,
            }
        elif route["platform"] in {"bilibili", "douyin", "youtube"}:
            next_action = "platform_extractor"
        elif route["source_type"] != "unknown":
            next_action = "download_then_route"
        return {
            "schema_version": FETCH_RECEIPT_VERSION,
            "status": status_name,
            "source_url": source,
            "normalized_url": normalized,
            "final_url": final_url,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "fetch_mode": "http_probe",
            "http_status": status,
            "content_type": content_type or None,
            "content_length": content_length,
            "sample_bytes": len(sample),
            "sample_truncated": sample_truncated,
            "sample_sha256": hashlib.sha256(sample).hexdigest(),
            "resolved_addresses": addresses,
            "redirects": redirect_handler.redirects,
            "route_plan": route,
            "robots": {"checked": False, "reason": "site crawl is not performed by probe v0.1"},
            "error": error,
            "next_action": next_action,
        }
    except ProbeError as exc:
        return _error_receipt(
            source,
            normalized,
            exc.code,
            str(exc),
            retryable=exc.retryable,
            started_at=started_at,
            redirects=redirect_handler.redirects,
        )
    except HTTPError as exc:
        try:
            sample = exc.read(max_bytes)
        except Exception:
            sample = b""
        if _looks_like_challenge(sample, getattr(exc, "url", None)):
            code, retryable = "CHALLENGE_REQUIRED", False
        elif exc.code in {401, 407}:
            code, retryable = "AUTH_REQUIRED", False
        elif exc.code in {403, 451}:
            code, retryable = "FORBIDDEN", False
        elif exc.code == 404:
            code, retryable = "NOT_FOUND", False
        elif exc.code == 429:
            code, retryable = "RATE_LIMITED", True
        elif 500 <= exc.code <= 599:
            code, retryable = "UPSTREAM_UNAVAILABLE", True
        else:
            code, retryable = "HTTP_ERROR", False
        receipt = _error_receipt(
            source,
            normalized,
            code,
            f"HTTP {exc.code}: {exc.reason}",
            retryable=retryable,
            started_at=started_at,
            redirects=redirect_handler.redirects,
            http_status=exc.code,
        )
        if code in {"AUTH_REQUIRED", "CHALLENGE_REQUIRED"}:
            receipt["status"] = "needs_user_action"
            receipt["next_action"] = "visible_browser_or_manual_snapshot"
        if exc.code == 429:
            receipt["retry_after"] = _header_value(exc.headers, "Retry-After")
        return receipt
    except (socket.timeout, TimeoutError) as exc:
        return _error_receipt(source, normalized, "FETCH_TIMEOUT", str(exc), retryable=True, started_at=started_at)
    except ssl.SSLError as exc:
        return _error_receipt(source, normalized, "TLS_FAILED", str(exc), retryable=False, started_at=started_at)
    except URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.gaierror):
            code, retryable = "DNS_FAILED", True
        elif isinstance(reason, (socket.timeout, TimeoutError)):
            code, retryable = "FETCH_TIMEOUT", True
        elif isinstance(reason, ssl.SSLError):
            code, retryable = "TLS_FAILED", False
        else:
            code, retryable = "NETWORK_FAILED", True
        return _error_receipt(source, normalized, code, str(reason), retryable=retryable, started_at=started_at)


def fetch_url(
    source: str,
    output: Path,
    *,
    timeout: float = 30.0,
    max_bytes: int = 64 * 1024 * 1024,
    max_redirects: int = 5,
    overwrite: bool = False,
    opener: Any | None = None,
    resolved_addresses: list[str] | None = None,
) -> dict[str, Any]:
    """Download one immutable public source snapshot with bounded resource use."""
    started_at = datetime.now(timezone.utc).isoformat()
    normalized: str | None = None
    redirect_handler = SafeProbeRedirectHandler(max_redirects)
    target = output.expanduser().resolve()
    temporary: Path | None = None
    try:
        if timeout <= 0 or max_bytes <= 0 or max_redirects < 0:
            raise ProbeError("INVALID_ARGUMENT", "fetch limits must be positive")
        normalized = normalize_public_http_url(source)
        addresses = resolved_addresses or assert_public_network_target(normalized)
        if target.exists() and not overwrite:
            raise ProbeError("OUTPUT_EXISTS", f"output already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        client = opener or build_opener(redirect_handler)
        request = Request(
            normalized,
            headers={
                "User-Agent": f"oks-connector/{PLUGIN_VERSION} (+single-url-snapshot)",
                "Accept": "application/pdf,image/*,audio/*,video/*,application/octet-stream,*/*;q=0.1",
            },
            method="GET",
        )
        with client.open(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            final_url = normalize_public_http_url(response.geturl())
            if not redirect_handler.redirects and final_url != normalized:
                assert_public_network_target(final_url)
            content_type = (_header_value(response.headers, "Content-Type") or "").split(";", 1)[0].strip().lower()
            content_length_text = _header_value(response.headers, "Content-Length")
            content_length = int(content_length_text) if content_length_text and content_length_text.isdigit() else None
            if content_length is not None and content_length > max_bytes:
                raise ProbeError(
                    "RESPONSE_TOO_LARGE",
                    f"declared response size {content_length} exceeds limit {max_bytes}",
                )
            handle, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
            temporary = Path(temporary_name)
            digest = hashlib.sha256()
            sample = bytearray()
            received = 0
            with os.fdopen(handle, "wb") as stream:
                while True:
                    chunk = response.read(min(1024 * 1024, max_bytes - received + 1))
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > max_bytes:
                        raise ProbeError(
                            "RESPONSE_TOO_LARGE",
                            f"response exceeded download limit {max_bytes}",
                        )
                    if len(sample) < 64 * 1024:
                        sample.extend(chunk[: 64 * 1024 - len(sample)])
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
        if content_type in {"text/html", "application/xhtml+xml"}:
            if _looks_like_challenge(bytes(sample), final_url):
                raise ProbeError("CHALLENGE_REQUIRED", "challenge or CAPTCHA detected; automatic bypass is not attempted")
            raise ProbeError("UNSUPPORTED_MIME", "HTML snapshots must use the web or browser acquisition route")
        os.replace(temporary, target)
        temporary = None
        return {
            "schema_version": FETCH_RECEIPT_VERSION,
            "status": "ok",
            "source_url": source,
            "normalized_url": normalized,
            "final_url": final_url,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "fetch_mode": "http_snapshot",
            "http_status": status,
            "content_type": content_type or None,
            "content_length": content_length,
            "downloaded_bytes": received,
            "content_sha256": digest.hexdigest(),
            "output": str(target),
            "resolved_addresses": addresses,
            "redirects": redirect_handler.redirects,
            "route_plan": route_plan(final_url),
            "error": None,
            "next_action": "route_local_snapshot",
        }
    except ProbeError as exc:
        receipt = _error_receipt(
            source,
            normalized,
            exc.code,
            str(exc),
            retryable=exc.retryable,
            started_at=started_at,
            redirects=redirect_handler.redirects,
        )
        receipt["fetch_mode"] = "http_snapshot"
        if exc.code == "CHALLENGE_REQUIRED":
            receipt["status"] = "needs_user_action"
            receipt["next_action"] = "visible_browser_or_manual_snapshot"
        return receipt
    except (HTTPError, URLError, socket.timeout, TimeoutError, ssl.SSLError) as exc:
        retryable = isinstance(exc, (URLError, socket.timeout, TimeoutError))
        receipt = _error_receipt(
            source,
            normalized,
            "NETWORK_FAILED" if retryable else "HTTP_ERROR",
            str(exc),
            retryable=retryable,
            started_at=started_at,
            redirects=redirect_handler.redirects,
            http_status=getattr(exc, "code", None),
        )
        receipt["fetch_mode"] = "http_snapshot"
        return receipt
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def default_ingest_output(source: str) -> Path:
    """Return a unique, human-readable bundle path for one immutable run."""
    if is_url(source):
        parsed = urlparse(source)
        label = f"{parsed.hostname or 'url'}-{Path(parsed.path).stem or 'source'}"
        identity = source
    else:
        local = Path(source).expanduser().resolve()
        label = local.stem or "source"
        identity = str(local)
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", label).strip("-._").lower() or "source"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
    timestamp = f"{datetime.now():%Y%m%d-%H%M%S-%f}-{uuid.uuid4().hex[:8]}"
    return (Path.cwd() / "raw" / f"{timestamp}-{slug[:64]}-{digest}").resolve()


def _extractor_python(extractor: str) -> Path:
    environment = {
        "watch": "OKS_WATCH_PYTHON",
        "rapidocr": "OKS_WATCH_PYTHON",
        "markitdown": "OKS_DOCUMENT_PYTHON",
        "mineru": "OKS_MINERU_PYTHON",
    }[extractor]
    extra = {
        "watch": "watch",
        "rapidocr": "watch",
        "markitdown": "document",
        "mineru": "pdf",
    }[extractor]
    module = {
        "watch": "watch_skill",
        "rapidocr": "rapidocr",
        "markitdown": "markitdown",
        "mineru": "mineru",
    }[extractor]

    # 1. Already installed (via oks capability install) — shared check
    from capability_check import is_capability_available as _cap_ok
    cap_ok, cap_python = _cap_ok(extractor)
    if cap_ok and cap_python is not None:
        return cap_python

    # 2. Explicit env var override
    configured = os.environ.get(environment)
    if configured:
        candidate = Path(configured).expanduser().resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"{environment} does not point to a Python executable: {candidate}")
        return _validate_extractor_python(candidate, extractor, environment=environment)

    # 3. Repo layout (.venv-watch etc.)
    root = Path(__file__).resolve().parent.parent
    environment_dir = {
        "watch": ".venv-watch",
        "rapidocr": ".venv-watch",
        "markitdown": ".venv-document",
        "mineru": ".venv-pdf",
    }[extractor]
    relative = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    candidate = root / environment_dir / relative
    if candidate.is_file():
        return _validate_extractor_python(candidate.resolve(), extractor, environment=environment)

    raise RuntimeError(
        f"{t('capability_missing', name=extractor)}\n"
        f"{t('capability_missing_hint', name=extra, env=environment)}"
    )


def _validate_extractor_python(
    candidate: Path,
    extractor: str,
    *,
    environment: str | None = None,
) -> Path:
    """验证发现到的 Python 解释器版本和模块导入能力。"""
    candidate = candidate.resolve()

    # 1. 验证解释器能否启动
    try:
        version_result = subprocess.run(
            [str(candidate), "-c",
             "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        context = f"（通过 {environment} 或项目布局解析到此路径）" if environment else ""
        raise RuntimeError(
            f"{extractor} Python 在 {candidate} 无法启动: {exc}\n{context}"
        )
    if version_result.returncode != 0:
        context = f"（通过 {environment} 或项目布局解析到此路径）" if environment else ""
        raise RuntimeError(
            f"{extractor} Python 在 {candidate} 不是有效的 Python 解释器。\n"
            f"stderr: {version_result.stderr.strip()[-500:]}\n{context}"
        )

    # 2. 验证 Python 版本 >= 3.12
    try:
        major, minor = map(int, version_result.stdout.strip().split("."))
    except ValueError:
        raise RuntimeError(
            f"{extractor} Python 在 {candidate} 返回了无法解析的版本号: "
            f"{version_result.stdout.strip()}"
        )
    if (major, minor) < (3, 12):
        raise RuntimeError(
            f"{extractor} Python 在 {candidate} 是 {major}.{minor}，"
            f"但此模块要求 Python >= 3.12。\n"
            f"请使用 Python 3.12+ 创建虚拟环境，并设置 {environment} 环境变量指向其解释器路径。"
        )

    # 3. 验证所需模块能否导入
    module_query = {
        "watch": "watch_skill",
        "rapidocr": "rapidocr",
        "markitdown": "markitdown",
        "mineru": "mineru",
    }[extractor]
    try:
        import_result = subprocess.run(
            [str(candidate), "-c", f"import {module_query}"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        extra_name = {
            "watch": "watch", "rapidocr": "watch",
            "markitdown": "document", "mineru": "pdf",
        }[extractor]
        raise RuntimeError(
            f"{extractor} Python 在 {candidate} 导入 {module_query} 时超时。\n"
            f"可选依赖可能已损坏或未安装。\n"
            f"重新安装: oks capability install {extra_name} --yes"
        )
    if import_result.returncode != 0:
        extra_name = {
            "watch": "watch", "rapidocr": "watch",
            "markitdown": "document", "mineru": "pdf",
        }[extractor]
        raise RuntimeError(
            f"{extractor} Python 在 {candidate} 无法导入 {module_query}:\n"
            f"{import_result.stderr.strip()[-800:]}\n"
            f"安装: oks capability install {extra_name} --yes\n"
            f"或设置 {environment} 指向已安装完整 {extractor} 依赖的 Python 解释器。"
        )

    return candidate


def ingest_child_argv(
    args: argparse.Namespace,
    plan: dict[str, Any],
    output: Path,
    extractor_python: Path,
    *,
    mineru_result: Path | None = None,
) -> list[str]:
    """Build the explicit extractor command selected by the deterministic route."""
    adapter = Path(__file__).resolve()
    base = [str(extractor_python), str(adapter)]
    extractor = plan["extractor"]
    tier = canonical_evidence_tier(args.mode)
    if extractor == "watch":
        command = [*base, "watch", args.source, "--output", str(output)]
        if plan["source_type"] == "audio" or tier == "quick":
            command.append("--transcript-only")
        if plan["source_type"] == "video" and tier == "quick":
            command.append("--no-local-whisper")
        command.extend(["--subtitle-langs", args.subtitle_langs, "--evidence-tier", tier])
        timeout = getattr(args, "timeout_seconds", None)
        if timeout is not None:
            command.extend(["--timeout-seconds", str(timeout)])
        if getattr(args, "progress", False):
            command.append("--progress")
    elif extractor == "rapidocr":
        command = [*base, "image", args.source, "--output", str(output)]
    elif extractor == "markitdown":
        command = [*base, "markitdown", args.source, "--output", str(output)]
    elif extractor == "mineru":
        if mineru_result is None:
            raise ValueError("mineru_result is required for the PDF packaging stage")
        command = [
            *base,
            "mineru",
            str(mineru_result),
            "--source",
            args.source,
            "--output",
            str(output),
        ]
    else:
        raise ValueError(f"unsupported extractor: {extractor}")
    if args.title:
        command.extend(["--title", args.title])
    if args.overwrite:
        command.append("--overwrite")
    return command


def canonical_evidence_tier(mode: str) -> str:
    """Keep the earlier fast/full spelling working while exposing stable tier names."""
    return {"fast": "quick", "full": "forensic"}.get(mode, mode)


def ingest_timeout_seconds(args: argparse.Namespace) -> float:
    timeout = getattr(args, "timeout_seconds", None)
    if timeout is not None:
        if timeout <= 0:
            raise ValueError("timeout-seconds must be positive")
        return timeout
    return 120.0 if canonical_evidence_tier(args.mode) == "quick" else 900.0


def run_ingest(args: argparse.Namespace) -> int:
    """Route and execute one source without adding Studio review or Wiki behavior."""
    plan = route_plan(args.source)
    extractor = plan.get("extractor")
    if extractor is None:
        diag = plan.get("diagnostics", {})
        ext = diag.get("detected_extension", "")
        ext_info = f" (扩展名: {ext})" if ext else ""
        suggestion = diag.get("suggestion", "")
        raise RuntimeError(
            f"没有匹配的 Raw 提取路由{ext_info}\n"
            f"来源类型: {plan.get('source_type', 'unknown')} | "
            f"平台: {plan.get('platform', 'unknown')}\n"
            f"\n{suggestion}\n"
            f"\n运行 `oks-connector route \"{args.source}\"` 查看路由决策详情。"
        )
    if is_url(args.source) and plan["platform"] not in {"bilibili", "douyin", "youtube"}:
        raise RuntimeError(
            "direct non-platform URL acquisition is not yet provenance-safe in ingest; "
            "use fetch followed by ingest on the local snapshot"
        )
    if not is_url(args.source) and not Path(args.source).expanduser().is_file():
        raise FileNotFoundError(Path(args.source).expanduser().resolve())

    output = (args.output or default_ingest_output(args.source)).expanduser().resolve()
    extractor_python = _extractor_python(extractor)
    timeout = ingest_timeout_seconds(args)
    tier = canonical_evidence_tier(args.mode)
    started = time.monotonic()
    emit_progress(getattr(args, "progress", False), "routing", 0.02, int(timeout))
    if extractor != "mineru":
        command = ingest_child_argv(args, plan, output, extractor_python)
        try:
            completed = subprocess.run(
                command,
                stdout=None,  # pass through to terminal for real-time progress
                stderr=subprocess.PIPE,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            emit_json({
                "status": "partial",
                "contract": SCHEMA_VERSION,
                "source": args.source,
                "evidence_tier": tier,
                "error": {"code": "EXTRACTION_TIMEOUT", "retryable": True,
                          "message": f"{tier} extraction exceeded {int(timeout)} seconds"},
                "next_action": "retry_with_larger_timeout_or_quick_tier",
            })
            return 2
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip()
            raise RuntimeError(
                f"{extractor} 提取失败 (exit code {completed.returncode})"
                f"\n--- stderr (最后 3000 字符) ---\n{detail[-3000:] or '(无)'}"
                f"\n--- 命令 ---\n{' '.join(command)}"
            )
        return 0

    with tempfile.TemporaryDirectory(prefix="oks-mineru-") as temporary:
        result_dir = Path(temporary)
        # MinerU 3.4+ uses a standalone CLI entry point, not `python -m mineru`.
        mineru_cli = str(Path(extractor_python).parent / ("mineru.exe" if os.name == "nt" else "mineru"))
        if not Path(mineru_cli).is_file():
            mineru_cli = shutil.which("mineru") or "mineru"
        mineru = subprocess.run(
            [
                mineru_cli,
                "-p",
                str(Path(args.source).expanduser().resolve()),
                "-o",
                str(result_dir),
                "-b",
                args.mineru_backend,
                "-m",
                args.mineru_method,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if mineru.returncode != 0:
            detail = (mineru.stderr or mineru.stdout).strip()
            raise RuntimeError(f"MinerU extraction failed: {detail[-2000:]}")
        command = ingest_child_argv(
            args,
            plan,
            output,
            Path(sys.executable).resolve(),
            mineru_result=result_dir,
        )
        remaining = max(0.1, timeout - (time.monotonic() - started))
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                errors="replace",
                timeout=remaining,
            )
        except subprocess.TimeoutExpired:
            emit_json({
                "status": "partial",
                "contract": SCHEMA_VERSION,
                "source": args.source,
                "evidence_tier": tier,
                "error": {"code": "EXTRACTION_TIMEOUT", "retryable": True,
                          "message": f"{tier} extraction exceeded {int(timeout)} seconds"},
                "next_action": "retry_with_larger_timeout_or_quick_tier",
            })
            return 2
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(
                f"MinerU 打包失败 (exit code {completed.returncode})"
                f"\n--- stderr (最后 3000 字符) ---\n{detail[-3000:]}"
                f"\n--- 命令 ---\n{' '.join(command)}"
            )
        return 0


def run_check(args: argparse.Namespace) -> int:
    """验证提取器环境（Python 版本 + 模块导入）。"""
    if getattr(args, "minimal", False):
        emit_json({
            "connector_version": PLUGIN_VERSION,
            "schema_versions": [SCHEMA_VERSION],
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "compatibility": "compatible",
        }, indent=2)
        return 0

    extractors = (
        ["watch", "rapidocr", "markitdown", "mineru"]
        if args.extractor == "all"
        else [args.extractor]
    )
    results: dict[str, dict[str, Any]] = {}
    all_ok = True
    for ext in extractors:
        try:
            python_path = _extractor_python(ext)
            results[ext] = {
                "status": "available",
                "python": str(python_path),
                "environment_variable": {
                    "watch": "OKS_WATCH_PYTHON",
                    "rapidocr": "OKS_WATCH_PYTHON",
                    "markitdown": "OKS_DOCUMENT_PYTHON",
                    "mineru": "OKS_MINERU_PYTHON",
                }[ext],
            }
        except (RuntimeError, FileNotFoundError) as exc:
            results[ext] = {"status": "unavailable", "error": str(exc)}
            all_ok = False
    emit_json({
        "connector_version": PLUGIN_VERSION,
        "schema_versions": [SCHEMA_VERSION],
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "extractors": results,
        "all_available": all_ok,
    }, indent=2)
    return 0 if all_ok else 2


def common_metadata(
    *,
    capture_id: str,
    identity: dict[str, Any],
    title: str,
    source_type: str,
    modalities: list[str],
    route: list[str],
    extractor_name: str,
    extractor_version: str,
    processing_status: str,
    benchmark: bool,
) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": SCHEMA_VERSION,
        "capture_id": capture_id,
        "source": {
            **identity,
            "title": title,
            "author": None,
            "collected_at": generated_at,
        },
        "source_type": source_type,
        "modalities": modalities,
        "route": route,
        "extractors": [{"name": extractor_name, "version": extractor_version}],
        "processing_status": processing_status,
        "review_status": "pending",
        "benchmark": bool(benchmark),
        "human_context": "omitted" if benchmark else "required",
        "purpose": "multimodal_pipeline_evaluation" if benchmark else None,
    }


def coverage_report(
    checks: dict[str, tuple[int | None, int]],
) -> tuple[dict[str, dict[str, Any]], str]:
    report: dict[str, dict[str, Any]] = {}
    statuses: list[str] = []
    for name, (expected, observed) in checks.items():
        if expected is None:
            status = "unknown"
        elif observed == expected:
            status = "passed"
        else:
            status = "partial"
        report[name] = {
            "expected": expected,
            "observed": observed,
            "status": status,
        }
        statuses.append(status)
    if "partial" in statuses:
        overall = "partial"
    elif statuses and all(status == "passed" for status in statuses):
        overall = "passed"
    else:
        overall = "unknown"
    return report, overall


def markdown_asset_references(markdown: str) -> list[str]:
    values = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown)
    values.extend(re.findall(r'<img\s+[^>]*src=["\']([^"\']+)', markdown))
    return [value.strip().split()[0].strip("<>") for value in values]


def neutralize_unresolved_images(markdown: str, unresolved: set[str]) -> str:
    def replace_markdown(match: re.Match[str]) -> str:
        alt, target = match.group(1), match.group(2).strip().split()[0].strip("<>")
        if target not in unresolved:
            return match.group(0)
        return f"> 未映射图片引用：`{target}`（原alt：{alt or '无'}）"

    value = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_markdown, markdown)

    def replace_html(match: re.Match[str]) -> str:
        target = match.group(1)
        if target not in unresolved:
            return match.group(0)
        return f"<!-- 未映射图片引用：{target} -->"

    return re.sub(r'<img\s+[^>]*src=["\']([^"\']+)["\'][^>]*>', replace_html, value)


def mineru_evidence(
    entries: list[dict[str, Any]], image_map: dict[str, str]
) -> Iterable[dict[str, Any]]:
    for index, entry in enumerate(entries):
        kind = str(entry.get("type", "unknown"))
        evidence: dict[str, Any] = {
            "id": f"mineru-{index + 1:06d}",
            "kind": kind,
            "method": "mineru",
            "locator": {
                "page": int(entry.get("page_idx", 0)) + 1,
            },
        }
        if entry.get("bbox") is not None:
            evidence["locator"]["bbox"] = entry["bbox"]
        text = entry.get("text")
        if text:
            evidence["text"] = text
        image_path = entry.get("img_path")
        if image_path:
            normalized = Path(str(image_path)).name
            evidence["locator"]["asset"] = image_map.get(
                normalized, f"assets/images/{normalized}"
            )
        table_body = entry.get("table_body")
        if table_body:
            evidence["text"] = table_body
        yield evidence


def rewrite_mineru_images(markdown: str) -> str:
    return re.sub(
        r'(?P<prefix>(?:!\[[^\]]*\]\(|src=["\']))images/',
        r"\g<prefix>assets/images/",
        markdown,
    )


def package_mineru(args: argparse.Namespace) -> Path:
    result_dir = args.result_dir.expanduser().resolve()
    source = args.source.expanduser().resolve()
    if not result_dir.is_dir():
        raise NotADirectoryError(result_dir)
    if not source.is_file():
        raise FileNotFoundError(source)

    markdown_path = exactly_one(result_dir, "*.md")
    content_list_path = exactly_one(result_dir, "*_content_list.json")
    entries = json.loads(content_list_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("MinerU content list must be a JSON array")

    output = prepare_output(args.output, args.overwrite)
    assets_dir = output / "assets" / "images"
    assets_dir.mkdir(parents=True)

    source_images = markdown_path.parent / "images"
    image_map: dict[str, str] = {}
    if source_images.is_dir():
        for image in sorted(source_images.iterdir()):
            if not image.is_file():
                continue
            destination = assets_dir / image.name
            shutil.copy2(image, destination)
            image_map[image.name] = f"assets/images/{image.name}"

    document = rewrite_mineru_images(markdown_path.read_text(encoding="utf-8"))
    (output / "document.md").write_text(document, encoding="utf-8", newline="\n")
    (output / "content.md").write_text(document, encoding="utf-8", newline="\n")
    evidence_count = write_jsonl(
        output / "evidence.jsonl", mineru_evidence(entries, image_map)
    )
    formula_candidate_count = 0
    formula_candidates_path = getattr(args, "formula_candidates", None)
    if formula_candidates_path is not None:
        formula_candidates_path = formula_candidates_path.expanduser().resolve()
        formula_payload = json.loads(formula_candidates_path.read_text(encoding="utf-8"))
        formula_candidate_count = int(formula_payload.get("region_count", 0))
        write_json(output / "formula-candidates.json", formula_payload)

    warnings = list(args.warning)
    warnings.extend(
        [
            "MinerU文本、OCR和公式结果未经人工逐项校对",
            "公式、上下标、矢量和复杂表格可能误识别；以原PDF页面为准",
        ]
    )
    if formula_candidate_count:
        warnings.append(
            f"{formula_candidate_count}个独立公式块有第二提取候选；未自动选择或覆盖MinerU结果"
        )
    image_references = len(re.findall(r"(?:!\[|<img\s)", document))
    expected_image_assets = {
        Path(str(item["img_path"])).name
        for item in entries
        if item.get("img_path")
    }
    observed_image_assets = sum(
        1 for name in expected_image_assets if name in image_map
    )
    coverage_checks, coverage_status = coverage_report(
        {
            "extractor_entries": (len(entries), evidence_count),
            "extractor_image_assets": (
                len(expected_image_assets),
                observed_image_assets,
            ),
        }
    )
    if coverage_status == "partial":
        warnings.append("MinerU提取结果未被完整打包；详见coverage_checks")
    processing_status = "partial" if warnings else "complete"
    digest = sha256_file(source)
    title = args.title or source.stem
    capture_id = f"{datetime.now():%Y%m%d}-document-{digest[:12]}"
    metadata = common_metadata(
        capture_id=capture_id,
        identity=source_identity(str(source)),
        title=title,
        source_type="document",
        modalities=["text", "layout", "formula", "image"],
        route=["mineru", "markdown", "page_evidence", "asset_copy"],
        extractor_name="MinerU",
        extractor_version=args.extractor_version,
        processing_status=processing_status,
        benchmark=args.benchmark,
    )
    write_json(output / "metadata.json", metadata)

    quality = {
        "schema_version": SCHEMA_VERSION,
        "processing_status": processing_status,
        "review_status": "pending",
        "evidence_count": evidence_count,
        "page_count": max(
            (int(item.get("page_idx", 0)) + 1 for item in entries), default=0
        ),
        "asset_count": len(image_map),
        "markdown_image_references": image_references,
        "unresolved_asset_references": max(0, image_references - len(image_map)),
        "formula_candidate_region_count": formula_candidate_count,
        "coverage_status": coverage_status,
        "coverage_checks": coverage_checks,
        "warnings": warnings,
        "human_fallback": "抽样核对每页正文；逐项核对将进入Draft或Wiki的公式",
    }
    write_json(output / "quality-report.json", quality)

    raw_markdown = f"""---
schema_version: {SCHEMA_VERSION}
capture_id: {capture_id}
source_type: document
processing_status: {processing_status}
review_status: pending
benchmark: {str(bool(args.benchmark)).lower()}
---

# {title}

## 来源

- 本地文件：`{source}`
- SHA-256：`{digest}`
- 提取器：MinerU {args.extractor_version}

## Raw提取物

- [可读Raw正文](content.md)
- [文档正文](document.md)
""" + (
        f"- [公式候选](formula-candidates.json)：{formula_candidate_count}个独立公式块\n"
        if formula_candidate_count else ""
    ) + f"""
- [原子证据](evidence.jsonl)：{evidence_count}条，保留页码和可用坐标
- [元数据](metadata.json)
- [质量报告](quality-report.json)
- `assets/images/`：{len(image_map)}个图片证据

## 已知限制

""" + "".join(f"- {warning}\n" for warning in warnings)
    (output / "raw.md").write_text(raw_markdown, encoding="utf-8", newline="\n")
    return output


def markitdown_text(source: Path, markdown: Path | None) -> str:
    if markdown is not None:
        markdown = markdown.expanduser().resolve()
        if not markdown.is_file():
            raise FileNotFoundError(markdown)
        return markdown.read_text(encoding="utf-8")
    try:
        from markitdown import MarkItDown, StreamInfo
    except ImportError as exc:
        raise RuntimeError(
            "MarkItDown is not installed in this interpreter; install it or pass --markdown"
        ) from exc
    stream_info = None
    if source.suffix.lower() in {".html", ".htm"}:
        header = source.read_bytes()[:8192].decode("ascii", errors="ignore")
        charset_match = re.search(
            r"charset\s*=\s*[\"']?([a-zA-Z0-9._-]+)", header, re.IGNORECASE
        )
        stream_info = StreamInfo(
            mimetype="text/html",
            extension=source.suffix.lower(),
            charset=charset_match.group(1) if charset_match else "utf-8",
            filename=source.name,
            local_path=str(source),
        )
    result = MarkItDown().convert(str(source), stream_info=stream_info)
    return result.text_content


def extract_pptx_media(source: Path, assets_dir: Path) -> list[str]:
    if source.suffix.lower() != ".pptx":
        return []
    copied: list[str] = []
    with zipfile.ZipFile(source) as archive:
        for member in sorted(archive.namelist()):
            if not member.startswith("ppt/media/") or member.endswith("/"):
                continue
            name = Path(member).name
            destination = assets_dir / "ppt-media" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as input_handle, destination.open("wb") as output_handle:
                shutil.copyfileobj(input_handle, output_handle)
            copied.append(f"assets/ppt-media/{name}")
    return copied


def extract_docx_media(source: Path, assets_dir: Path) -> list[str]:
    if source.suffix.lower() != ".docx":
        return []
    copied: list[str] = []
    with zipfile.ZipFile(source) as archive:
        for member in sorted(archive.namelist()):
            if not member.startswith("word/media/") or member.endswith("/"):
                continue
            name = Path(member).name
            destination = assets_dir / "docx-media" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as input_handle, destination.open("wb") as output_handle:
                shutil.copyfileobj(input_handle, output_handle)
            copied.append(f"assets/docx-media/{name}")
    return copied


def docx_document_images(source: Path) -> list[str]:
    """Resolve DOCX image occurrence order through document relationships."""
    if source.suffix.lower() != ".docx":
        return []
    relationship_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    drawing_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    office_rel_ns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(source) as archive:
        members = set(archive.namelist())
        rel_path = "word/_rels/document.xml.rels"
        document_path = "word/document.xml"
        if rel_path not in members or document_path not in members:
            return []
        rel_root = ET.fromstring(archive.read(rel_path))
        relationships: dict[str, str] = {}
        for relationship in rel_root.findall(f"{{{relationship_ns}}}Relationship"):
            if not str(relationship.get("Type", "")).endswith("/image"):
                continue
            target = str(relationship.get("Target", ""))
            if relationship.get("TargetMode") == "External" or not target:
                continue
            relationships[str(relationship.get("Id", ""))] = (
                f"assets/docx-media/{Path(target).name}"
            )
        document_root = ET.fromstring(archive.read(document_path))
        images: list[str] = []
        for blip in document_root.findall(f".//{{{drawing_ns}}}blip"):
            relationship_id = blip.get(f"{{{office_rel_ns}}}embed")
            asset = relationships.get(str(relationship_id))
            if asset:
                images.append(asset)
        return images


def map_markitdown_docx_images(markdown: str, images: list[str]) -> tuple[str, int]:
    if not images:
        return markdown, 0
    available = iter(images)
    mapped_count = 0
    image_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    def replace_image(match: re.Match[str]) -> str:
        nonlocal mapped_count
        target = match.group(2).strip().split()[0].strip("<>")
        if is_url(target):
            return match.group(0)
        asset = next(available, None)
        if asset is None:
            return match.group(0)
        mapped_count += 1
        return f"![{match.group(1)}]({asset})"

    return image_pattern.sub(replace_image, markdown), mapped_count


def pptx_slide_images(source: Path) -> dict[int, list[dict[str, str]]]:
    """Resolve each PPTX picture to its packaged media asset via OOXML rels."""
    if source.suffix.lower() != ".pptx":
        return {}
    relationship_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    presentation_ns = (
        "http://schemas.openxmlformats.org/presentationml/2006/main"
    )
    drawing_ns = "http://schemas.openxmlformats.org/drawingml/2006/main"
    office_rel_ns = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )
    mapping: dict[int, list[dict[str, str]]] = {}
    with zipfile.ZipFile(source) as archive:
        slide_members: list[tuple[int, str]] = []
        for member in archive.namelist():
            match = re.fullmatch(r"ppt/slides/slide(\d+)\.xml", member)
            if match:
                slide_members.append((int(match.group(1)), member))
        for slide_number, slide_member in sorted(slide_members):
            rel_member = (
                f"ppt/slides/_rels/slide{slide_number}.xml.rels"
            )
            if rel_member not in archive.namelist():
                continue
            rel_root = ET.fromstring(archive.read(rel_member))
            relationships: dict[str, str] = {}
            for relationship in rel_root.findall(
                f"{{{relationship_ns}}}Relationship"
            ):
                if not str(relationship.get("Type", "")).endswith("/image"):
                    continue
                target = str(relationship.get("Target", ""))
                if relationship.get("TargetMode") == "External" or not target:
                    continue
                relationships[str(relationship.get("Id", ""))] = (
                    f"assets/ppt-media/{Path(target).name}"
                )
            slide_root = ET.fromstring(archive.read(slide_member))
            images: list[dict[str, str]] = []
            for picture in slide_root.findall(
                f".//{{{presentation_ns}}}pic"
            ):
                metadata = picture.find(
                    f".//{{{presentation_ns}}}cNvPr"
                )
                blip = picture.find(f".//{{{drawing_ns}}}blip")
                relationship_id = (
                    blip.get(f"{{{office_rel_ns}}}embed")
                    if blip is not None
                    else None
                )
                asset = relationships.get(str(relationship_id))
                if not asset:
                    continue
                images.append(
                    {
                        "asset": asset,
                        "alt": (
                            str(metadata.get("descr") or metadata.get("name") or "")
                            if metadata is not None
                            else ""
                        ),
                    }
                )
            if images:
                mapping[slide_number] = images
    return mapping


def map_markitdown_ppt_images(
    markdown: str, slide_images: dict[int, list[dict[str, str]]]
) -> tuple[str, int]:
    """Replace MarkItDown placeholders with OOXML-resolved slide media."""
    marker = re.compile(r"<!--\s*Slide number:\s*(\d+)\s*-->", re.IGNORECASE)
    matches = list(marker.finditer(markdown))
    if not matches or not slide_images:
        return markdown, 0
    pieces: list[str] = [markdown[: matches[0].start()]]
    mapped_count = 0
    image_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        section = markdown[match.start() : end]
        available = iter(slide_images.get(int(match.group(1)), []))

        def replace_image(image_match: re.Match[str]) -> str:
            nonlocal mapped_count
            target = image_match.group(2).strip().split()[0].strip("<>")
            if is_url(target):
                return image_match.group(0)
            image = next(available, None)
            if image is None:
                return image_match.group(0)
            mapped_count += 1
            alt = image_match.group(1) or image.get("alt") or ""
            return f"![{alt}]({image['asset']})"

        pieces.append(image_pattern.sub(replace_image, section))
    return "".join(pieces), mapped_count


def extract_markdown_data_images(
    markdown: str, assets_dir: Path
) -> tuple[str, list[Path], int]:
    """Persist extractor-provided data URI images without interpreting them."""
    pattern = re.compile(
        r"(!\[[^\]]*\]\()data:image/([a-zA-Z0-9.+-]+);base64,([^\s)]+)(\))"
    )
    extension_map = {"jpeg": "jpg", "svg+xml": "svg"}
    extracted: list[Path] = []
    failed = 0
    embedded_dir = assets_dir / "embedded"

    def replace(match: re.Match[str]) -> str:
        nonlocal failed
        subtype = match.group(2).lower()
        extension = extension_map.get(subtype, subtype)
        try:
            payload = base64.b64decode(match.group(3), validate=True)
        except (ValueError, TypeError):
            failed += 1
            return match.group(0)
        embedded_dir.mkdir(parents=True, exist_ok=True)
        destination = embedded_dir / f"image-{len(extracted) + 1:04d}.{extension}"
        destination.write_bytes(payload)
        extracted.append(destination)
        return f"{match.group(1)}assets/embedded/{destination.name}{match.group(4)}"

    return pattern.sub(replace, markdown), extracted, failed


def markitdown_evidence(markdown: str) -> Iterable[dict[str, Any]]:
    if not markdown.strip():
        return
    marker = re.compile(r"<!--\s*Slide number:\s*(\d+)\s*-->", re.IGNORECASE)
    matches = list(marker.finditer(markdown))
    if matches:
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
            text = markdown[match.end() : end].strip()
            yield {
                "id": f"markitdown-slide-{int(match.group(1)):04d}",
                "kind": "slide_text",
                "text": text,
                "method": "markitdown",
                "locator": {"slide": int(match.group(1))},
            }
        return
    yield {
        "id": "markitdown-document-0001",
        "kind": "document_text",
        "text": markdown,
        "method": "markitdown",
        "locator": {"document": 1},
    }


def package_markitdown(args: argparse.Namespace) -> Path:
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    document = markitdown_text(source, args.markdown)
    output = prepare_output(args.output, args.overwrite)
    assets_dir = output / "assets"
    original_dir = assets_dir / "original"
    original_dir.mkdir(parents=True)
    shutil.copy2(source, original_dir / source.name)
    ppt_media_assets = extract_pptx_media(source, assets_dir)
    docx_media_assets = extract_docx_media(source, assets_dir)

    original_references = markdown_asset_references(document)
    slide_images = pptx_slide_images(source)
    mapped_document, mapped_reference_count = map_markitdown_ppt_images(
        document, slide_images
    )
    mapped_document, docx_mapped_reference_count = map_markitdown_docx_images(
        mapped_document, docx_document_images(source)
    )
    mapped_reference_count += docx_mapped_reference_count
    mapped_document, data_image_assets, failed_data_images = extract_markdown_data_images(
        mapped_document, assets_dir
    )
    references = markdown_asset_references(mapped_document)
    unresolved = [
        reference
        for reference in references
        if not is_url(reference) and not (output / reference).is_file()
    ]
    packaged_document = neutralize_unresolved_images(
        mapped_document, set(unresolved)
    )
    (output / "extractor-output.md").write_text(
        document, encoding="utf-8", newline="\n"
    )
    (output / "document.md").write_text(
        packaged_document, encoding="utf-8", newline="\n"
    )
    (output / "content.md").write_text(
        packaged_document, encoding="utf-8", newline="\n"
    )
    evidence_count = write_jsonl(
        output / "evidence.jsonl", markitdown_evidence(packaged_document)
    )
    warnings = list(args.warning)
    warnings.append("MarkItDown正文和结构未经人工校对")
    empty_document = not packaged_document.strip()
    if empty_document:
        warnings.append("MarkItDown未提取到可见正文；仅保留原始文件和失败现场")
    if unresolved:
        warnings.append(
            f"Markdown含{len(unresolved)}个未映射图片引用；原文件和内嵌媒体已保留供回查"
        )
    if failed_data_images:
        warnings.append(
            f"{failed_data_images}个内嵌data URI图片未能解码；原始引用保留在extractor-output.md"
        )
    if source.suffix.lower() != ".pptx":
        warnings.append("当前格式缺少稳定的页码或段落级定位，证据定位仅到文档级")
    slide_count = len(
        re.findall(r"<!--\s*Slide number:", document, re.IGNORECASE)
    )
    expected_evidence = slide_count or 1
    coverage_checks, coverage_status = coverage_report(
        {
            "document_units": (expected_evidence, evidence_count),
            "original_asset": (1, int((original_dir / source.name).is_file())),
            "markdown_asset_references": (
                len(original_references),
                len(references) - len(unresolved),
            ),
            "embedded_media": (
                len(ppt_media_assets) + len(docx_media_assets) + len(data_image_assets),
                len(ppt_media_assets) + len(docx_media_assets) + len(data_image_assets),
            ),
        }
    )
    if coverage_status == "partial":
        warnings.append("MarkItDown提取结果未被完整打包；详见coverage_checks")
    processing_status = "failed" if empty_document else ("partial" if warnings else "complete")
    digest = sha256_file(source)
    title = args.title or source.stem
    capture_id = f"{datetime.now():%Y%m%d}-document-{digest[:12]}"
    metadata = common_metadata(
        capture_id=capture_id,
        identity=source_identity(str(source)),
        title=title,
        source_type="document",
        modalities=["text", "layout", "image"],
        route=["markitdown", "markdown", "embedded_media", "original_asset"],
        extractor_name="MarkItDown",
        extractor_version=args.extractor_version,
        processing_status=processing_status,
        benchmark=args.benchmark,
    )
    write_json(output / "metadata.json", metadata)
    quality = {
        "schema_version": SCHEMA_VERSION,
        "processing_status": processing_status,
        "review_status": "pending",
        "evidence_count": evidence_count,
        "slide_count": slide_count,
        "asset_count": 1 + len(ppt_media_assets) + len(docx_media_assets) + len(data_image_assets),
        "embedded_media_count": len(ppt_media_assets) + len(docx_media_assets) + len(data_image_assets),
        "ppt_media_count": len(ppt_media_assets),
        "docx_media_count": len(docx_media_assets),
        "data_uri_image_count": len(data_image_assets),
        "failed_data_uri_image_count": failed_data_images,
        "markdown_asset_references": len(original_references),
        "mapped_asset_references": mapped_reference_count,
        "unresolved_asset_references": len(unresolved),
        "coverage_status": coverage_status,
        "coverage_checks": coverage_checks,
        "warnings": warnings,
        "human_fallback": (
            "通过原PPT和assets/ppt-media核对正文、图片、图表与排版"
            if source.suffix.lower() == ".pptx"
            else "通过原Word和assets/docx-media核对正文、图片、图表与排版"
            if source.suffix.lower() == ".docx"
            else "通过原始文档核对提取正文、链接与结构"
        ),
    }
    write_json(output / "quality-report.json", quality)
    raw_markdown = f"""---
schema_version: {SCHEMA_VERSION}
capture_id: {capture_id}
source_type: document
processing_status: {processing_status}
review_status: pending
benchmark: {str(bool(args.benchmark)).lower()}
---

# {title}

## 来源

- 本地文件：`{source}`
- SHA-256：`{digest}`
- 提取器：MarkItDown {args.extractor_version}

## Raw提取物

- [可读Raw正文](content.md)
- [文档正文](document.md)
- [提取器原始Markdown](extractor-output.md)
- [原子证据](evidence.jsonl)：{evidence_count}条
- [元数据](metadata.json)
- [质量报告](quality-report.json)
- `assets/original/`：原始文件
- `assets/ppt-media/`：{len(ppt_media_assets)}个PPT内嵌媒体
- `assets/docx-media/`：{len(docx_media_assets)}个Word内嵌媒体
- `assets/embedded/`：{len(data_image_assets)}个提取器内嵌图片

## 已知限制

""" + "".join(f"- {warning}\n" for warning in warnings)
    (output / "raw.md").write_text(raw_markdown, encoding="utf-8", newline="\n")
    return output


def watch_payload(result: Any) -> dict[str, Any]:
    frames: list[dict[str, Any]] = []
    if result.perception is not None:
        for frame in result.perception.frames:
            frames.append(
                {
                    "index": frame.index,
                    "timestamp_seconds": frame.timestamp_seconds,
                    "path": str(frame.path),
                    "scene_id": frame.scene_id,
                    "phash": frame.phash,
                    "reason": frame.reason,
                    "ocr_blocks": [asdict(block) for block in frame.ocr_blocks],
                }
            )
    acquisition = result.acquisition
    return {
        "acquisition": {
            "source": acquisition.source,
            "kind": str(acquisition.kind),
            "video_path": str(acquisition.video_path) if acquisition.video_path else None,
            "subtitle_path": str(acquisition.subtitle_path) if acquisition.subtitle_path else None,
            "info": acquisition.info,
            "from_cache": acquisition.from_cache,
            "acquirer": acquisition.acquirer,
        },
        "metadata": asdict(result.metadata),
        "transcript": {
            "source": result.transcript.source,
            "segments": [segment.to_dict() for segment in result.transcript.segments],
        },
        "perception": None
        if result.perception is None
        else {
            "source": result.perception.source,
            "engine": result.perception.engine,
            "scene_count": result.perception.scene_count,
            "candidate_count": result.perception.candidate_count,
            "deduped_count": result.perception.deduped_count,
            "focused": result.perception.focused,
            "start_seconds": result.perception.start_seconds,
            "end_seconds": result.perception.end_seconds,
            "frames": frames,
        },
        "start_seconds": result.start_seconds,
        "end_seconds": result.end_seconds,
    }


def render_transcript(payload: dict[str, Any]) -> str:
    lines = ["# 未校对逐字稿", ""]
    for segment in payload.get("transcript", {}).get("segments", []):
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start))
        speaker = f"{segment['speaker']}: " if segment.get("speaker") else ""
        lines.append(f"[{start:.3f}–{end:.3f}] {speaker}{segment.get('text', '').strip()}")
    return "\n".join(lines).rstrip() + "\n"


def format_media_time(seconds: float) -> str:
    value = max(0, int(seconds))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def group_transcript_segments(
    segments: list[dict[str, Any]], max_chars: int = 220, max_gap: float = 1.5
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for index, segment in enumerate(segments):
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start))
        evidence_id = f"watch-speech-{index + 1:06d}"
        speaker = segment.get("speaker")
        can_merge = bool(
            current
            and start - float(current["end"]) <= max_gap
            and len(str(current["text"])) + len(text) <= max_chars
            and current.get("speaker") == speaker
        )
        if can_merge and current is not None:
            current["end"] = end
            current["text"] = f"{current['text']} {text}"
            current["evidence_ids"].append(evidence_id)
        else:
            current = {
                "start": start,
                "end": end,
                "text": text,
                "speaker": speaker,
                "evidence_ids": [evidence_id],
            }
            groups.append(current)
    return groups


def normalize_ocr_text(value: str) -> str:
    return re.sub(r"\W+", "", value, flags=re.UNICODE).lower()


def order_ocr_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Restore basic top-to-bottom, left-to-right order from OCR bboxes.

    This changes only presentation order. Text, confidence and coordinates are
    copied unchanged, and ``source_index`` preserves the extractor order.
    """
    positioned: list[dict[str, Any]] = []
    unpositioned: list[dict[str, Any]] = []
    for index, original in enumerate(blocks):
        block = dict(original)
        block.setdefault("source_index", index)
        bbox = block.get("bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            unpositioned.append(block)
            continue
        left, top, right, bottom = (float(value) for value in bbox)
        block["_layout"] = {
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "center": (top + bottom) / 2,
            "height": max(1.0, bottom - top),
        }
        positioned.append(block)

    positioned.sort(
        key=lambda item: (
            item["_layout"]["top"],
            item["_layout"]["left"],
            item["source_index"],
        )
    )
    lines: list[dict[str, Any]] = []
    for block in positioned:
        layout = block["_layout"]
        best_line: dict[str, Any] | None = None
        best_distance = float("inf")
        for line in lines:
            overlap = max(
                0.0,
                min(layout["bottom"], line["bottom"])
                - max(layout["top"], line["top"]),
            )
            overlap_ratio = overlap / min(layout["height"], line["height"])
            distance = abs(layout["center"] - line["center"])
            tolerance = max(layout["height"], line["height"]) * 0.6
            if (overlap_ratio >= 0.4 or distance <= tolerance) and distance < best_distance:
                best_line = line
                best_distance = distance
        if best_line is None:
            lines.append(
                {
                    "top": layout["top"],
                    "bottom": layout["bottom"],
                    "center": layout["center"],
                    "height": layout["height"],
                    "blocks": [block],
                }
            )
            continue
        best_line["blocks"].append(block)
        best_line["top"] = min(best_line["top"], layout["top"])
        best_line["bottom"] = max(best_line["bottom"], layout["bottom"])
        best_line["center"] = (best_line["top"] + best_line["bottom"]) / 2
        best_line["height"] = max(1.0, best_line["bottom"] - best_line["top"])

    ordered: list[dict[str, Any]] = []
    for line in sorted(lines, key=lambda item: (item["top"], item["center"])):
        for block in sorted(
            line["blocks"],
            key=lambda item: (item["_layout"]["left"], item["source_index"]),
        ):
            block.pop("_layout", None)
            ordered.append(block)
    ordered.extend(unpositioned)
    return ordered


def format_evidence_refs(evidence_ids: list[str]) -> str:
    if not evidence_ids:
        return "无"
    if len(evidence_ids) == 1:
        return f"`{evidence_ids[0]}`"
    return f"`{evidence_ids[0]}`–`{evidence_ids[-1]}`（{len(evidence_ids)}条）"


def select_visual_summaries(
    frames: list[dict[str, Any]], similarity_threshold: float = 0.88
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    previous = ""
    for frame in frames:
        blocks = [
            str(block.get("text", "")).strip()
            for block in order_ocr_blocks(frame.get("ocr_blocks", []))
            if str(block.get("text", "")).strip()
        ]
        text = "\n".join(dict.fromkeys(blocks))
        normalized = normalize_ocr_text(text)
        similarity = (
            difflib.SequenceMatcher(None, previous, normalized).ratio()
            if previous and normalized
            else 0.0
        )
        if normalized and similarity >= similarity_threshold:
            continue
        selected.append({**frame, "ocr_text": text})
        if normalized:
            previous = normalized
    return selected


def render_watch_content(
    transcript_segments: list[dict[str, Any]],
    frames: list[dict[str, Any]],
    image_map: dict[str, str],
    max_ocr_lines_per_frame: int = 6,
    max_ocr_chars_per_frame: int = 500,
    include_visual: bool = True,
) -> tuple[str, int, int, int]:
    groups = group_transcript_segments(transcript_segments)
    visual_summaries = select_visual_summaries(frames)
    lines = [
        "# Raw提取正文",
        "",
        "> 以下内容仅做机器提取结果的合段、去重和证据编排，未经总结、改写或概念抽取。",
        "",
        "## 语音内容",
        "",
    ]
    if not groups:
        lines.append("未取得字幕或ASR逐字稿。")
    for group in groups:
        start = format_media_time(float(group["start"]))
        end = format_media_time(float(group["end"]))
        evidence_ids = format_evidence_refs(group["evidence_ids"])
        speaker = f"{group['speaker']}：" if group.get("speaker") else ""
        lines.extend(
            [
                f"### {start}–{end}",
                "",
                f"{speaker}{group['text']}",
                "",
                f"证据：{evidence_ids}",
                "",
            ]
        )
    rendered_visuals = 0
    rendered_ocr_lines = 0
    if not include_visual:
        return (
            "\n".join(lines).rstrip() + "\n",
            len(groups),
            rendered_visuals,
            rendered_ocr_lines,
        )
    lines.extend(["## 视觉内容", ""])
    if not visual_summaries:
        lines.append("未取得可用视觉证据。")
    for frame in visual_summaries:
        source_frame = str(Path(frame["path"]).expanduser().resolve())
        asset = image_map.get(source_frame)
        if not asset:
            continue
        rendered_visuals += 1
        index = int(frame.get("index", 0))
        timestamp = float(frame.get("timestamp_seconds", 0))
        lines.extend(
            [
                f"### {format_media_time(timestamp)}",
                "",
                f"![]({asset})",
                "",
                f"证据：`watch-frame-{index + 1:06d}`",
                "",
            ]
        )
        if frame.get("ocr_text"):
            all_ocr_lines = frame["ocr_text"].splitlines()
            excerpt: list[str] = []
            excerpt_chars = 0
            for ocr_line in all_ocr_lines:
                if len(excerpt) >= max_ocr_lines_per_frame:
                    break
                if excerpt and excerpt_chars + len(ocr_line) > max_ocr_chars_per_frame:
                    break
                excerpt.append(ocr_line)
                excerpt_chars += len(ocr_line)
            rendered_ocr_lines += len(excerpt)
            lines.extend(["```text", "\n".join(excerpt), "```", ""])
            if len(excerpt) < len(all_ocr_lines):
                lines.extend(
                    [
                        f"OCR摘录：显示{len(excerpt)}/{len(all_ocr_lines)}行；完整OCR见 `evidence.jsonl`。",
                        "",
                    ]
                )
    return (
        "\n".join(lines).rstrip() + "\n",
        len(groups),
        rendered_visuals,
        rendered_ocr_lines,
    )


def transcript_route(payload: dict[str, Any]) -> str:
    transcript = payload.get("transcript", {})
    if not transcript.get("segments"):
        return "none"
    source = str(transcript.get("source", "")).lower()
    if "caption" in source or "subtitle" in source:
        return "platform_caption"
    if "whisper" in source or "asr" in source:
        return "asr"
    return "extractor_transcript"


def package_watch_payload(
    payload: dict[str, Any],
    *,
    source: str,
    source_file: Path | None,
    output_path: Path,
    title: str | None,
    extractor_version: str,
    warnings: list[str],
    benchmark: bool,
    overwrite: bool,
    frame_fallback_dir: Path | None = None,
) -> Path:
    output = prepare_output(output_path, overwrite)
    planned_route = route_plan(source)
    source_type = (
        planned_route["source_type"]
        if planned_route.get("source_type") in {"audio", "video"}
        else "video"
    )
    is_audio = source_type == "audio"
    acquired_value = payload.get("acquisition", {}).get("video_path")
    acquired_file = Path(acquired_value) if acquired_value else None
    identity = source_identity(source, source_file, acquired_file)
    digest = identity.get("content_sha256") or identity.get("source_url_sha256")
    if not digest:
        raise ValueError("无法为媒体来源生成稳定指纹")
    info = payload.get("acquisition", {}).get("info", {})
    resolved_title = title or info.get("title") or (
        source_file.stem
        if source_file
        else Path(urlparse(source).path).stem or source_type
    )
    capture_id = f"{datetime.now():%Y%m%d}-{source_type}-{digest[:12]}"
    frames_dir = output / "assets" / "frames"
    if not is_audio:
        frames_dir.mkdir(parents=True)
    transcript_segments = payload.get("transcript", {}).get("segments", [])
    perception = payload.get("perception") or {}
    frames = perception.get("frames", [])
    image_map: dict[str, str] = {}
    for frame in frames:
        payload_frame = Path(frame["path"]).expanduser().resolve()
        source_frame = payload_frame
        if not source_frame.is_file() and frame_fallback_dir is not None:
            candidates = sorted(
                frame_fallback_dir.glob(f"frame-{int(frame.get('index', 0)):04d}.*")
            )
            if candidates:
                source_frame = candidates[0].resolve()
        if not source_frame.is_file():
            warnings.append(f"证据帧不存在：{source_frame}")
            continue
        destination = frames_dir / f"frame-{int(frame.get('index', 0)):04d}{source_frame.suffix.lower()}"
        shutil.copy2(source_frame, destination)
        image_map[str(payload_frame)] = f"assets/frames/{destination.name}"

    evidence: list[dict[str, Any]] = []
    for index, segment in enumerate(transcript_segments):
        item = {
            "id": f"watch-speech-{index + 1:06d}",
            "kind": "speech",
            "text": str(segment.get("text", "")),
            "method": payload.get("transcript", {}).get("source", "watch-skill"),
            "locator": {
                "start": float(segment.get("start", 0)),
                "end": float(segment.get("end", segment.get("start", 0))),
            },
        }
        if segment.get("speaker"):
            item["speaker"] = segment["speaker"]
        evidence.append(item)
    visual_lines = ["# 视觉证据", ""]
    ocr_count = 0
    for frame in frames:
        frame_path = str(Path(frame["path"]).expanduser().resolve())
        asset = image_map.get(frame_path)
        if not asset:
            continue
        timestamp = float(frame.get("timestamp_seconds", 0))
        evidence.append(
            {
                "id": f"watch-frame-{int(frame.get('index', 0)) + 1:06d}",
                "kind": "video_frame",
                "method": "watch-skill",
                "locator": {
                    "start": timestamp,
                    "end": timestamp,
                    "asset": asset,
                    "scene_id": frame.get("scene_id"),
                    "reason": frame.get("reason"),
                    "phash": frame.get("phash"),
                },
            }
        )
        visual_lines.extend([f"## {timestamp:.3f}秒", "", f"![]({asset})", ""])
        for block_index, block in enumerate(
            order_ocr_blocks(frame.get("ocr_blocks", []))
        ):
            ocr_count += 1
            evidence.append(
                {
                    "id": f"watch-ocr-{int(frame.get('index', 0)) + 1:04d}-{block_index + 1:04d}",
                    "kind": "ocr",
                    "text": str(block.get("text", "")),
                    "method": "watch-skill/rapidocr",
                    "confidence": block.get("confidence"),
                    "locator": {
                        "start": timestamp,
                        "end": timestamp,
                        "asset": asset,
                        "bbox": block.get("bbox"),
                    },
                }
            )
            visual_lines.append(
                f"- OCR `{block.get('confidence', 'unknown')}`：{block.get('text', '')}"
            )
        visual_lines.append("")

    (
        content,
        transcript_group_count,
        content_visual_count,
        content_ocr_line_count,
    ) = render_watch_content(
        transcript_segments, frames, image_map, include_visual=not is_audio
    )
    (output / "content.md").write_text(
        content, encoding="utf-8", newline="\n"
    )
    (output / "transcript.md").write_text(
        render_transcript(payload), encoding="utf-8", newline="\n"
    )
    transcript_candidates = payload.get("transcript_candidates", [])
    if transcript_candidates:
        candidate_lines = [
            "# ASR候选逐字稿",
            "",
            "> 候选仅用于与主逐字稿对照；未经人工真值确认，不自动覆盖主结果。",
            "",
        ]
        for candidate in transcript_candidates:
            candidate_lines.extend([f"## {candidate.get('source', 'unknown')}", ""])
            for segment in candidate.get("segments", []):
                start = float(segment.get("start", 0))
                end = float(segment.get("end", start))
                candidate_lines.append(
                    f"[{start:.3f}–{end:.3f}] {str(segment.get('text', '')).strip()}"
                )
            candidate_lines.append("")
        (output / "transcript-candidates.md").write_text(
            "\n".join(candidate_lines).rstrip() + "\n",
            encoding="utf-8",
            newline="\n",
        )
    if not is_audio:
        (output / "visual.md").write_text(
            "\n".join(visual_lines).rstrip() + "\n", encoding="utf-8", newline="\n"
        )
    write_json(output / "extractor-result.json", payload)
    evidence_count = write_jsonl(output / "evidence.jsonl", evidence)
    warning_values = list(warnings)
    resolved_transcript_route = transcript_route(payload)
    if not transcript_segments:
        warning_values.append("没有取得字幕或ASR逐字稿；不得据此生成语音内容")
    elif resolved_transcript_route == "platform_caption":
        warning_values.append("平台字幕未经人工校对")
    elif resolved_transcript_route == "asr":
        warning_values.append("ASR逐字稿未经人工校对")
    else:
        warning_values.append("提取器逐字稿未经人工校对")
    if frames and not ocr_count:
        warning_values.append("已保留证据帧，但没有取得可用OCR文字")
    missing_frames = max(0, len(frames) - len(image_map))
    if missing_frames:
        warning_values.append(f"{missing_frames}个证据帧未能打包")
    if frames and int(perception.get("scene_count", 0) or 0) == 0:
        warning_values.append(
            "场景检测未发现切换；当前证据帧可能来自均匀回退或候选筛选，需人工抽样确认视觉覆盖"
        )
    expected_ocr_blocks = sum(
        len(frame.get("ocr_blocks", [])) for frame in frames
    )
    coverage_checks, coverage_status = coverage_report(
        {
            "transcript_segments": (
                len(transcript_segments),
                sum(1 for item in evidence if item.get("kind") == "speech"),
            ),
            "evidence_frames": (len(frames), len(image_map)),
            "ocr_blocks": (expected_ocr_blocks, ocr_count),
            "evidence_records": (
                len(transcript_segments) + len(image_map) + ocr_count,
                evidence_count,
            ),
        }
    )
    if coverage_status == "partial":
        warning_values.append("Watch提取结果未被完整打包；详见coverage_checks")
    has_any_evidence = bool(transcript_segments or image_map)
    processing_status = "partial" if has_any_evidence else "failed"
    metadata = common_metadata(
        capture_id=capture_id,
        identity=identity,
        title=resolved_title,
        source_type=source_type,
        modalities=["speech"] if is_audio else ["speech", "video", "on_screen_text"],
        route=(
            [
                "watch-skill",
                payload.get("acquisition", {}).get("acquirer", "unknown"),
                payload.get("transcript", {}).get("source", "none"),
            ]
            if is_audio
            else [
                "watch-skill",
                payload.get("acquisition", {}).get("acquirer", "unknown"),
                payload.get("transcript", {}).get("source", "none"),
                perception.get("engine", "none"),
                "ocr",
            ]
        ),
        extractor_name="Watch Skill",
        extractor_version=extractor_version,
        processing_status=processing_status,
        benchmark=benchmark,
    )
    metadata["source"]["author"] = info.get("uploader") or info.get("channel")
    metadata["media"] = payload.get("metadata", {})
    metadata["transcript"] = {
        "route": resolved_transcript_route,
        "source": payload.get("transcript", {}).get("source", "none"),
        "subtitle_file": (
            Path(str(payload.get("acquisition", {}).get("subtitle_path"))).name
            if payload.get("acquisition", {}).get("subtitle_path")
            else None
        ),
        "segment_count": len(transcript_segments),
    }
    write_json(output / "metadata.json", metadata)
    quality = {
        "schema_version": SCHEMA_VERSION,
        "processing_status": processing_status,
        "review_status": "pending",
        "duration_seconds": payload.get("metadata", {}).get("duration_seconds", 0),
        "transcript_source": payload.get("transcript", {}).get("source", "none"),
        "transcript_route": resolved_transcript_route,
        "transcript_segment_count": len(transcript_segments),
        "content_transcript_group_count": transcript_group_count,
        "frame_count": len(image_map),
        "content_visual_count": content_visual_count,
        "content_ocr_line_count": content_ocr_line_count,
        "ocr_block_count": ocr_count,
        "ocr_reading_order": "bbox_line_then_left",
        "scene_count": perception.get("scene_count", 0),
        "candidate_frame_count": perception.get("candidate_count", 0),
        "deduped_frame_count": perception.get("deduped_count", 0),
        "evidence_count": evidence_count,
        "missing_frame_count": missing_frames,
        "coverage_status": coverage_status,
        "coverage_checks": coverage_checks,
        "warnings": warning_values,
        "human_fallback": (
            "抽样校对逐字稿"
            if is_audio
            else "抽样校对逐字稿；逐帧核对将用于Draft或Wiki的屏幕文字"
        ),
    }
    write_json(output / "quality-report.json", quality)
    raw_markdown = f"""---
schema_version: {SCHEMA_VERSION}
capture_id: {capture_id}
source_type: {source_type}
processing_status: {processing_status}
review_status: pending
benchmark: {str(bool(benchmark)).lower()}
---

# {resolved_title}

## 来源

- 来源：`{source}`
- 来源指纹：`{digest}`（内容哈希状态：{identity.get('content_hash_status', 'unknown')}）
- 提取器：Watch Skill {extractor_version}

## Raw提取物

- [可读Raw正文](content.md)：{transcript_group_count}个语音段落""" + (
        "" if is_audio else f"，{content_visual_count}个视觉段落"
    ) + f"""
- [未校对逐字稿](transcript.md)：{len(transcript_segments)}段
""" + (
        f"- [ASR候选逐字稿](transcript-candidates.md)：{len(transcript_candidates)}路候选\n"
        if transcript_candidates else ""
    ) + f"""
""" + (
        "" if is_audio else f"- [视觉证据](visual.md)：{len(image_map)}帧，{ocr_count}个OCR块\n"
    ) + f"""- [原子证据](evidence.jsonl)：{evidence_count}条
- [提取器原始结果](extractor-result.json)
- [元数据](metadata.json)
- [质量报告](quality-report.json)

## 已知限制

""" + "".join(f"- {warning}\n" for warning in warning_values)
    (output / "raw.md").write_text(raw_markdown, encoding="utf-8", newline="\n")
    return output


def parse_ocr_roi(value: str | None) -> tuple[int, int, int, int] | None:
    """Parse an explicit pixel ROI without guessing the user's content area."""
    if not value:
        return None
    try:
        values = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise ValueError("OCR ROI must be x1,y1,x2,y2 integers") from exc
    if len(values) != 4:
        raise ValueError("OCR ROI must contain exactly four integers")
    x1, y1, x2, y2 = values
    if min(values) < 0 or x2 <= x1 or y2 <= y1:
        raise ValueError("OCR ROI must satisfy 0 <= x1 < x2 and 0 <= y1 < y2")
    return values


def _adaptive_scene_detector(video_path: Path, start: float | None, end: float | None):
    from scenedetect import AdaptiveDetector, detect

    kwargs: dict[str, Any] = {}
    if start is not None:
        kwargs["start_time"] = start
    if end is not None:
        kwargs["end_time"] = end
    scenes = detect(str(video_path), AdaptiveDetector(), **kwargs)
    return [(float(item[0].seconds), float(item[1].seconds)) for item in scenes]


def _screen_change_scenes(
    video_path: Path,
    start: float | None,
    end: float | None,
    *,
    threshold: float,
    sample_seconds: float,
    roi: tuple[int, int, int, int] | None,
) -> list[tuple[float, float]]:
    """Find material screen changes with OpenCV; return scene-like spans.

    This is intentionally a transparent sampler, not semantic understanding.
    It compares one frame every ``sample_seconds`` after resizing and optional
    content crop. It cannot observe changes shorter than that sampling window.
    """
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return []
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = total_frames / fps if total_frames else 0.0
    lo = max(0.0, float(start or 0.0))
    hi = min(duration, float(end)) if end is not None and duration else duration
    boundaries = [lo]
    if sample_seconds <= 0:
        raise ValueError("screen sample interval must be positive")
    previous = None
    second = lo
    try:
        while second <= hi:
            capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000.0)
            ok, frame = capture.read()
            if not ok:
                second += sample_seconds
                continue
            if roi is not None:
                x1, y1, x2, y2 = roi
                height, width = frame.shape[:2]
                frame = frame[min(y1, height):min(y2, height), min(x1, width):min(x2, width)]
                if frame.size == 0:
                    raise ValueError(f"OCR ROI {roi} is outside video frame {width}x{height}")
            sample = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
            sample = cv2.GaussianBlur(sample, (3, 3), 0)
            if previous is not None:
                difference = float(cv2.absdiff(sample, previous).mean())
                if difference >= threshold and second - boundaries[-1] >= 1.0:
                    boundaries.append(round(second, 3))
            previous = sample
            second += sample_seconds
    finally:
        capture.release()
    if hi <= lo or len(boundaries) == 1:
        return []
    return list(zip(boundaries, [*boundaries[1:], hi]))


def subtitle_topic_anchors(segments: list[dict[str, Any]], max_frames: int) -> list[float]:
    """Choose bounded visual anchors from subtitle topic shifts, without AI inference.

    A long subtitle pause or sufficiently distant new speech segment is a
    transparent topic boundary.  The cap is shared with the visual evidence
    budget, so this never widens into a whole-video frame sweep.
    """
    if max_frames <= 0:
        return []
    anchors: list[float] = []
    previous_end: float | None = None
    previous_anchor: float | None = None
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        start = float(segment.get("start", 0.0))
        gap = previous_end is not None and start - previous_end >= 2.5
        distant = previous_anchor is None or start - previous_anchor >= 45.0
        if previous_anchor is None or gap or distant:
            anchors.append(round(start, 3))
            previous_anchor = start
        previous_end = float(segment.get("end", start))
    if len(anchors) <= max_frames:
        return anchors
    if max_frames == 1:
        return anchors[:1]
    return [anchors[round(index * (len(anchors) - 1) / (max_frames - 1))] for index in range(max_frames)]


def _watch_progress(
    enabled: bool,
    timeout_seconds: float | None,
    *,
    phase_remap: dict[str, str] | None = None,
):
    started = time.monotonic()
    remap = phase_remap or {}

    def report(phase: str, fraction: float) -> None:
        label = remap.get(phase, phase)
        if timeout_seconds is None:
            eta = None
        elif fraction <= 0:
            eta = int(timeout_seconds)
        else:
            elapsed = time.monotonic() - started
            eta = max(0, int(elapsed * (1 - fraction) / fraction))
        emit_progress(enabled, label, fraction, eta)

    return report


def run_watch(args: argparse.Namespace) -> Path:
    # Watch does not expose detector/OCR strategy injection yet. Serialize the
    # short-lived module override so concurrent calls in one process cannot
    # observe each other's strategy.
    with _WATCH_OVERRIDE_LOCK:
        return _run_watch_unlocked(args)


def _run_watch_unlocked(args: argparse.Namespace) -> Path:
    if args.output.expanduser().exists() and not args.overwrite:
        raise FileExistsError(f"output already exists: {args.output.expanduser().resolve()}")
    try:
        from watch_skill.watch import watch
    except ImportError as exc:
        raise RuntimeError(
            "Watch Skill is not installed in this interpreter; run this command with its Python environment"
        ) from exc
    from watch_skill.config import get_settings
    from watch_skill.perceive import ocr as watch_ocr
    from watch_skill.perceive import scenes as watch_scenes
    from watch_skill.transcribe.types import Segment, Transcript

    # 验证 watch-skill 接口：monkey-patch 目标必须存在
    for target_name, target_obj in [
        ("perceive.scenes.detect_scenes", watch_scenes.detect_scenes),
        ("perceive.ocr.ocr_frame", watch_ocr.ocr_frame),
    ]:
        if not callable(target_obj):
            raise RuntimeError(
                f"watch-skill 缺少预期接口 {target_name}\n"
                "当前 watch-skill 版本与此 connector 不兼容，请更新后重试。"
            )

    work_dir = Path(tempfile.mkdtemp(prefix="oks-watch-"))
    roi = parse_ocr_roi(args.ocr_roi)
    original_scene_detector = watch_scenes.detect_scenes
    original_ocr = watch_ocr.ocr_frame
    enhanced_transcribe = None
    if args.hotwords or args.initial_prompt:
        def enhanced_transcribe(audio_path, model_size="auto", language=None):
            from faster_whisper import WhisperModel
            from watch_skill.transcribe.local import has_cuda_gpu, pick_model_size

            size = pick_model_size() if args.asr_model == "auto" else args.asr_model
            device = "cuda" if has_cuda_gpu() else "cpu"
            compute = "float16" if device == "cuda" else "int8"
            model = WhisperModel(size, device=device, compute_type=compute)
            raw_segments, _ = model.transcribe(
                str(audio_path),
                language=language,
                vad_filter=True,
                hotwords=args.hotwords,
                initial_prompt=args.initial_prompt,
                word_timestamps=True,
            )
            segments = [
                Segment(round(item.start, 2), round(item.end, 2), item.text.strip())
                for item in raw_segments if item.text.strip()
            ]
            return Transcript(segments, source=f"whisper-local ({size};context)")

    if args.video_profile == "shots":
        watch_scenes.detect_scenes = _adaptive_scene_detector
    elif args.video_profile == "screen":
        def screen_detector(video_path, start_seconds=None, end_seconds=None):
            return _screen_change_scenes(
                video_path,
                start_seconds,
                end_seconds,
                threshold=args.screen_change_threshold,
                sample_seconds=args.screen_sample_seconds,
                roi=roi,
            )

        watch_scenes.detect_scenes = screen_detector

    if roi is not None:
        def roi_ocr(image_path, min_confidence=0.5, lang=None):
            from PIL import Image
            from watch_skill.perceive.types import OcrBlock

            with Image.open(image_path) as image:
                width, height = image.size
                x1, y1, x2, y2 = roi
                if x1 >= width or y1 >= height:
                    raise ValueError(f"OCR ROI {roi} is outside frame {width}x{height}")
                clipped = (x1, y1, min(x2, width), min(y2, height))
                crop_path = work_dir / f"roi-{Path(image_path).stem}.png"
                image.crop(clipped).save(crop_path)
            blocks = original_ocr(crop_path, min_confidence=min_confidence, lang=lang)
            return [
                OcrBlock(
                    block.text,
                    (
                        block.bbox[0] + clipped[0], block.bbox[1] + clipped[1],
                        block.bbox[2] + clipped[0], block.bbox[3] + clipped[1],
                    ),
                    block.confidence,
                )
                for block in blocks
            ]

        watch_ocr.ocr_frame = roi_ocr
    setting_name = "WATCHSKILL_SUBTITLE_LANGS"
    previous_subtitle_langs = os.environ.get(setting_name)
    if args.subtitle_langs:
        os.environ[setting_name] = args.subtitle_langs
    get_settings.cache_clear()
    try:
        tier = getattr(args, "evidence_tier", "forensic")
        transcript_only = getattr(args, "transcript_only", False) or tier == "quick"
        if transcript_only:
            phase_remap = {
                "extracting frames (scenes, dedup, OCR)": "acquiring source",
                "transcribing (captions -> local whisper)": "transcribing (platform captions)",
            }
        else:
            phase_remap = None
        progress = _watch_progress(
            getattr(args, "progress", False), args.timeout_seconds, phase_remap=phase_remap
        )
        if tier == "forensic" and not args.transcript_only:
            emit_progress(getattr(args, "progress", False), "captions_preflight", 0.08, None)
            caption_result = watch(
                args.source,
                transcript_only=True,
                run_ocr=False,
                allow_local_whisper=False,
                allow_cloud_stt=False,
                out_dir=work_dir / "captions",
                use_cache=True,
                whisper_model=args.asr_model,
                on_progress=progress,
            )
            caption_payload = watch_payload(caption_result)
            captions = caption_payload.get("transcript", {})
            anchors = subtitle_topic_anchors(captions.get("segments", []), args.max_frames)
            has_captions = transcript_route(caption_payload) == "platform_caption"
            if has_captions and anchors:
                emit_progress(getattr(args, "progress", False), "subtitle_anchored_evidence", 0.35, None)
                # Watch's perception normally detects scenes across the whole video.
                # In this tier, reserve its entire frame budget for subtitle anchors.
                watch_scenes.detect_scenes = lambda *_args, **_kwargs: []
                result = watch(
                    args.source,
                    max_frames=len(anchors),
                    cue_timestamps=anchors,
                    transcript_only=False,
                    run_ocr=True,
                    allow_local_whisper=not args.no_local_whisper,
                    allow_cloud_stt=False,
                    out_dir=work_dir / "evidence",
                    use_cache=True,
                    whisper_model=args.asr_model,
                    on_progress=progress,
                )
            else:
                args.warning.append("未取得可用平台字幕主题点；完整取证回退为全片视觉采样")
                result = watch(
                    args.source,
                    max_frames=args.max_frames,
                    transcript_only=False,
                    run_ocr=True,
                    allow_local_whisper=not args.no_local_whisper,
                    allow_cloud_stt=False,
                    out_dir=work_dir,
                    use_cache=True,
                    whisper_model=args.asr_model,
                    on_progress=progress,
                )
        else:
            result = watch(
                args.source,
                max_frames=args.max_frames,
                transcript_only=args.transcript_only,
                run_ocr=not args.transcript_only,
                allow_local_whisper=not args.no_local_whisper,
                allow_cloud_stt=False,
                out_dir=work_dir,
                use_cache=True,
                whisper_model=args.asr_model,
                on_progress=progress,
            )
        payload = watch_payload(result)
        if (
            enhanced_transcribe is not None
            and result.acquisition.video_path is not None
            and "whisper" in str(payload.get("transcript", {}).get("source", "")).lower()
        ):
            context_transcript = enhanced_transcribe(
                result.acquisition.video_path,
                model_size=args.asr_model,
                language=(args.asr_language or result.acquisition.info.get("language")),
            )
            payload["transcript_candidates"] = [
                {
                    "source": context_transcript.source,
                    "segments": [item.to_dict() for item in context_transcript.segments],
                }
            ]
        payload["extraction_options"] = {
            "evidence_tier": tier,
            "subtitle_topic_anchor_seconds": anchors if tier == "forensic" and not args.transcript_only else [],
            "hotwords": [item.strip() for item in (args.hotwords or "").split(",") if item.strip()],
            "initial_prompt_present": bool(args.initial_prompt),
            "asr_model": args.asr_model,
            "asr_language": args.asr_language,
            "video_profile": args.video_profile,
            "ocr_roi": roi,
            "screen_change_threshold": args.screen_change_threshold,
            "screen_sample_seconds": args.screen_sample_seconds,
        }
        return package_watch_payload(
            payload,
            source=args.source,
            source_file=args.source_file,
            output_path=args.output,
            title=args.title,
            extractor_version=args.extractor_version,
            warnings=args.warning,
            benchmark=args.benchmark,
            overwrite=args.overwrite,
            frame_fallback_dir=None,
        )
    finally:
        watch_scenes.detect_scenes = original_scene_detector
        watch_ocr.ocr_frame = original_ocr
        if previous_subtitle_langs is None:
            os.environ.pop(setting_name, None)
        else:
            os.environ[setting_name] = previous_subtitle_langs
        get_settings.cache_clear()
        shutil.rmtree(work_dir, ignore_errors=True)


def rapidocr_blocks(result: Any, min_confidence: float) -> tuple[list[dict[str, Any]], int]:
    raw_texts = getattr(result, "txts", None)
    raw_boxes = getattr(result, "boxes", None)
    raw_scores = getattr(result, "scores", None)
    texts = list(raw_texts) if raw_texts is not None else []
    boxes = list(raw_boxes) if raw_boxes is not None else []
    scores = list(raw_scores) if raw_scores is not None else []
    returned_count = max(len(texts), len(boxes), len(scores))
    blocks: list[dict[str, Any]] = []
    for text, box, score in zip(texts, boxes, scores):
        confidence = float(score)
        value = str(text).strip()
        if not value or confidence < min_confidence:
            continue
        points = box.tolist() if hasattr(box, "tolist") else list(box)
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
        blocks.append(
            {
                "text": value,
                "confidence": confidence,
                "bbox": [min(xs), min(ys), max(xs), max(ys)],
                "polygon": points,
            }
        )
    return order_ocr_blocks(blocks), returned_count


def package_image_result(
    args: argparse.Namespace, result: Any, *, elapsed_seconds: float | None = None
) -> Path:
    source = args.source.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output = prepare_output(args.output, args.overwrite)
    original_dir = output / "assets" / "original"
    original_dir.mkdir(parents=True)
    original_asset = original_dir / f"source{source.suffix.lower()}"
    shutil.copy2(source, original_asset)
    asset_reference = f"assets/original/{original_asset.name}"

    blocks, extractor_block_count = rapidocr_blocks(result, args.min_confidence)
    roi = parse_ocr_roi(getattr(args, "ocr_roi", None))
    if roi is not None:
        x1, y1, _, _ = roi
        for block in blocks:
            block["bbox"] = [
                block["bbox"][0] + x1,
                block["bbox"][1] + y1,
                block["bbox"][2] + x1,
                block["bbox"][3] + y1,
            ]
            block["polygon"] = [
                [float(point[0]) + x1, float(point[1]) + y1]
                for point in block["polygon"]
            ]
    evidence: list[dict[str, Any]] = [
        {
            "id": "rapidocr-image-000001",
            "kind": "image",
            "method": "source-image",
            "locator": {"asset": asset_reference},
        }
    ]
    for index, block in enumerate(blocks, start=1):
        evidence.append(
            {
                "id": f"rapidocr-text-{index:06d}",
                "kind": "ocr",
                "text": block["text"],
                "method": "rapidocr",
                "confidence": block["confidence"],
                "locator": {
                    "asset": asset_reference,
                    "bbox": block["bbox"],
                    "polygon": block["polygon"],
                },
            }
        )
    evidence_count = write_jsonl(output / "evidence.jsonl", evidence)
    lines = [
        "# Raw提取正文",
        "",
        "> 以下文字由RapidOCR直接提取，未经总结、改写或概念抽取。",
        "",
        f"![]({asset_reference})",
        "",
        "## OCR文字",
        "",
    ]
    if blocks:
        for index, block in enumerate(blocks, start=1):
            lines.append(
                f"- {block['text']}  `rapidocr-text-{index:06d}` "
                f"（置信度 {block['confidence']:.3f}）"
            )
    else:
        lines.append("未识别到达到置信度阈值的文字。")
    content = "\n".join(lines).rstrip() + "\n"
    (output / "content.md").write_text(content, encoding="utf-8", newline="\n")
    (output / "visual.md").write_text(content, encoding="utf-8", newline="\n")
    write_json(
        output / "extractor-result.json",
        {
            "engine": "RapidOCR",
            "returned_block_count": extractor_block_count,
            "retained_block_count": len(blocks),
            "minimum_confidence": args.min_confidence,
            "reading_order": "bbox_line_then_left",
            "ocr_roi": roi,
            "elapsed_seconds": elapsed_seconds,
            "blocks": blocks,
        },
    )

    warnings = list(args.warning)
    warnings.append("OCR文字、顺序和坐标未经人工校对；以原图为准")
    if roi is not None:
        warnings.append(f"OCR只处理用户明确指定的像素区域{roi}；区域外内容仍保留在原图中")
    rejected = extractor_block_count - len(blocks)
    if rejected:
        warnings.append(
            f"{rejected}个OCR块为空或低于置信度阈值{args.min_confidence:.2f}，未写入Raw正文"
        )
    if not blocks:
        warnings.append("未取得可用OCR文字；仅保留原图证据")
    coverage_checks, coverage_status = coverage_report(
        {
            "original_asset": (1, int(original_asset.is_file())),
            "extractor_ocr_blocks": (extractor_block_count, len(blocks)),
            "evidence_records": (1 + len(blocks), evidence_count),
        }
    )
    processing_status = "partial" if blocks else "failed"
    digest = sha256_file(source)
    title = args.title or source.stem
    capture_id = f"{datetime.now():%Y%m%d}-image-{digest[:12]}"
    metadata = common_metadata(
        capture_id=capture_id,
        identity=source_identity(str(source)),
        title=title,
        source_type="image",
        modalities=["image", "on_screen_text"],
        route=["rapidocr", "bbox", "original_asset"],
        extractor_name="RapidOCR",
        extractor_version=args.extractor_version,
        processing_status=processing_status,
        benchmark=args.benchmark,
    )
    write_json(output / "metadata.json", metadata)
    quality = {
        "schema_version": SCHEMA_VERSION,
        "processing_status": processing_status,
        "review_status": "pending",
        "extractor_ocr_block_count": extractor_block_count,
        "ocr_block_count": len(blocks),
        "rejected_ocr_block_count": rejected,
        "ocr_reading_order": "bbox_line_then_left",
        "ocr_roi": roi,
        "evidence_count": evidence_count,
        "asset_count": 1,
        "elapsed_seconds": elapsed_seconds,
        "coverage_status": coverage_status,
        "coverage_checks": coverage_checks,
        "warnings": warnings,
        "human_fallback": "对照原图抽样核对OCR文字；进入Draft或Wiki前逐项核对关键表述",
    }
    write_json(output / "quality-report.json", quality)
    raw_markdown = f"""---
schema_version: {SCHEMA_VERSION}
capture_id: {capture_id}
source_type: image
processing_status: {processing_status}
review_status: pending
benchmark: {str(bool(args.benchmark)).lower()}
---

# {title}

## 来源

- 本地文件：`{source}`
- SHA-256：`{digest}`
- 提取器：RapidOCR {args.extractor_version}

## Raw提取物

- [可读Raw正文](content.md)：{len(blocks)}个OCR块
- [视觉证据](visual.md)
- [原子证据](evidence.jsonl)：{evidence_count}条
- [提取器原始结果](extractor-result.json)
- [元数据](metadata.json)
- [质量报告](quality-report.json)
- `{asset_reference}`：原始图片

## 已知限制

""" + "".join(f"- {warning}\n" for warning in warnings)
    (output / "raw.md").write_text(raw_markdown, encoding="utf-8", newline="\n")
    return output


def run_image(args: argparse.Namespace) -> Path:
    try:
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise RuntimeError(
            "RapidOCR is not installed in this interpreter; run this command with its Python environment"
        ) from exc
    source = args.source.expanduser().resolve()
    roi = parse_ocr_roi(getattr(args, "ocr_roi", None))
    temporary: Path | None = None
    target = source
    if roi is not None:
        from PIL import Image

        with Image.open(source) as image:
            width, height = image.size
            x1, y1, x2, y2 = roi
            if x1 >= width or y1 >= height:
                raise ValueError(f"OCR ROI {roi} is outside image {width}x{height}")
            clipped = (x1, y1, min(x2, width), min(y2, height))
            fd, name = tempfile.mkstemp(prefix="oks-ocr-roi-", suffix=".png")
            os.close(fd)
            temporary = Path(name)
            image.crop(clipped).save(temporary)
    started = datetime.now(timezone.utc)
    try:
        result = RapidOCR()(str(target if temporary is None else temporary))
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return package_image_result(args, result, elapsed_seconds=elapsed)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_bundle(bundle: Path) -> dict[str, Any]:
    bundle = bundle.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []
    if not bundle.is_dir():
        return {"valid": False, "bundle": str(bundle), "errors": ["bundle目录不存在"]}
    required = [
        "raw.md",
        "content.md",
        "metadata.json",
        "evidence.jsonl",
        "quality-report.json",
    ]
    for name in required:
        if not (bundle / name).is_file():
            errors.append(f"缺少必需文件：{name}")
    metadata: dict[str, Any] = {}
    quality: dict[str, Any] = {}
    for name, target in (("metadata.json", metadata), ("quality-report.json", quality)):
        path = bundle / name
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                errors.append(f"{name}必须是JSON对象")
            else:
                target.update(value)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{name}无法解析：{exc}")
    if metadata and metadata.get("schema_version") != SCHEMA_VERSION:
        errors.append("metadata.json schema_version不受支持")
    if metadata and metadata.get("processing_status") not in {"complete", "partial", "failed"}:
        errors.append("metadata.json processing_status无效")
    evidence_count = 0
    evidence_path = bundle / "evidence.jsonl"
    if evidence_path.is_file():
        for line_number, line in enumerate(
            evidence_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                evidence = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"evidence.jsonl第{line_number}行无法解析：{exc}")
                continue
            evidence_count += 1
            if not evidence.get("kind") or not evidence.get("method"):
                errors.append(f"evidence.jsonl第{line_number}行缺少kind或method")
            if not isinstance(evidence.get("locator"), dict):
                errors.append(f"evidence.jsonl第{line_number}行缺少locator")
            asset = evidence.get("locator", {}).get("asset")
            if asset and not (bundle / asset).is_file():
                errors.append(f"evidence.jsonl第{line_number}行引用不存在资产：{asset}")
    if quality:
        expected = quality.get("evidence_count")
        if expected is not None and int(expected) != evidence_count:
            errors.append(f"质量报告证据数{expected}与实际{evidence_count}不一致")
        quality_warnings = [str(item) for item in quality.get("warnings", [])]
        warnings.extend(quality_warnings)
        checks = quality.get("coverage_checks")
        if not isinstance(checks, dict) or not checks:
            errors.append("质量报告缺少coverage_checks")
        else:
            recomputed: list[str] = []
            for name, check in checks.items():
                if not isinstance(check, dict):
                    errors.append(f"coverage_checks.{name}必须是JSON对象")
                    continue
                expected_count = check.get("expected")
                observed_count = check.get("observed")
                declared = check.get("status")
                actual = (
                    "unknown"
                    if expected_count is None
                    else "passed"
                    if observed_count == expected_count
                    else "partial"
                )
                recomputed.append(actual)
                if declared != actual:
                    errors.append(
                        f"coverage_checks.{name}状态{declared}与计数推导结果{actual}不一致"
                    )
            actual_overall = (
                "partial"
                if "partial" in recomputed
                else "passed"
                if recomputed and all(item == "passed" for item in recomputed)
                else "unknown"
            )
            if quality.get("coverage_status") != actual_overall:
                errors.append("coverage_status与coverage_checks不一致")
            if actual_overall == "partial" and not quality_warnings:
                errors.append("覆盖不完整时必须在warnings中显式说明")
    for name in ("raw.md", "content.md", "document.md", "transcript.md", "visual.md"):
        markdown_path = bundle / name
        if not markdown_path.is_file():
            continue
        for reference in markdown_asset_references(markdown_path.read_text(encoding="utf-8")):
            if is_url(reference):
                continue
            if not (markdown_path.parent / reference).is_file():
                errors.append(f"{markdown_path.name}引用不存在资产：{reference}")
    report = {
        "valid": not errors,
        "bundle": str(bundle),
        "schema_version": metadata.get("schema_version"),
        "processing_status": metadata.get("processing_status"),
        "evidence_count": evidence_count,
        "errors": errors,
        "warnings": warnings,
    }
    if (bundle / "bundle.json").is_file():
        v2_report = validate_bundle_v2(bundle)
        report["valid"] = bool(report["valid"] and v2_report["valid"])
        report["schema_version"] = v2_report.get("schema_version")
        report["bundle_id"] = v2_report.get("bundle_id")
        report["processing_status"] = v2_report.get("processing_status")
        report["errors"] = [*report["errors"], *v2_report.get("errors", [])]
        report["warnings"] = list(
            dict.fromkeys([*report["warnings"], *v2_report.get("warnings", [])])
        )
    return report


RAW_V2_VERSION = "raw-multimodal/v0.2"


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def _source_snapshot(bundle: Path, metadata: dict[str, Any], explicit_source: Path | None = None) -> Path:
    candidates = [explicit_source.expanduser() if explicit_source else None, bundle / "assets" / "page.html"]
    source = metadata.get("source")
    if isinstance(source, dict):
        for key in ("local_path", "path"):
            if source.get(key):
                candidates.append(Path(str(source[key])).expanduser())
    candidate = next((path.resolve() for path in candidates if path is not None and path.is_file()), None)
    if candidate is None:
        raise ValueError("v0.2 requires a primary source snapshot; none was found")
    source_dir = bundle / "source"
    source_dir.mkdir(exist_ok=True)
    suffix = candidate.suffix or ".bin"
    destination = source_dir / f"primary{suffix.lower()}"
    if candidate != destination.resolve():
        shutil.copy2(candidate, destination)
    return destination


def finalize_bundle_v2(
    bundle: Path,
    capture_envelope_path: Path,
    processing_run_path: Path,
    source_path: Path | None = None,
) -> dict[str, Any]:
    bundle = bundle.expanduser().resolve()
    legacy = validate_bundle(bundle)
    if not legacy["valid"]:
        raise ValueError(f"legacy bundle is invalid: {legacy['errors']}")
    capture = _read_json_object(capture_envelope_path.expanduser().resolve())
    run = _read_json_object(processing_run_path.expanduser().resolve())
    if capture.get("schema_version") != "oks-capture-envelope/v0.2":
        raise ValueError("capture envelope must use oks-capture-envelope/v0.2")
    if run.get("schema_version") != "oks-processing-run/v0.2":
        raise ValueError("processing run must use oks-processing-run/v0.2")
    if capture.get("capture_id") != run.get("capture_id"):
        raise ValueError("capture_id differs between Capture Envelope and Processing Run")
    if run.get("status") not in {"complete", "partial"}:
        raise ValueError("only a successful or partial run can finalize a Raw Bundle")

    metadata = _read_json_object(bundle / "metadata.json")
    quality = _read_json_object(bundle / "quality-report.json")
    primary = _source_snapshot(bundle, metadata, source_path)
    (bundle / "assets").mkdir(exist_ok=True)
    (bundle / "derived").mkdir(exist_ok=True)
    run_journal = bundle / "processing-runs.jsonl"
    existing_runs: list[dict[str, Any]] = []
    if run_journal.is_file():
        for line in run_journal.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing_runs.append(json.loads(line))
    existing_runs = [item for item in existing_runs if item.get("run_id") != run.get("run_id")]
    existing_runs.append(run)
    _atomic_write_text(
        run_journal,
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in existing_runs),
    )

    source_rel = primary.relative_to(bundle).as_posix()
    source_hash = sha256_file(primary)
    capture_snapshot = capture.get("source_snapshot") if isinstance(capture.get("source_snapshot"), dict) else {}
    snapshot_kind = capture_snapshot.get("kind", "content")
    content_hash_status = capture_snapshot.get("content_hash_status", "verified")
    source_entity = f"entity:source:{source_hash[:16]}"
    content_entity = f"entity:content:{sha256_file(bundle / 'content.md')[:16]}"
    evidence_entity = f"entity:evidence:{sha256_file(bundle / 'evidence.jsonl')[:16]}"
    activity = f"activity:{run['run_id']}"
    agent = f"agent:{run['job']['name']}:{run['job']['version']}"
    manifest = {
        "schema_version": RAW_V2_VERSION,
        "bundle_id": f"bundle:{capture['capture_id']}:{run['run_id']}",
        "capture_id": capture["capture_id"],
        "content_hash": capture["content_hash"],
        "recipe_version": run["recipe_version"],
        "processing_status": run["status"],
        "files": {
            "manifest": "bundle.json",
            "content": "content.md",
            "evidence": "evidence.jsonl",
            "quality_report": "quality-report.json",
            "processing_runs": "processing-runs.jsonl",
            "source_dir": "source/",
            "assets_dir": "assets/",
            "derived_dir": "derived/",
        },
        "sources": [
            {
                "entity_id": source_entity,
                "path": source_rel,
                "sha256": source_hash,
                "media_type": metadata.get("source", {}).get("content_type") if isinstance(metadata.get("source"), dict) else None,
                "snapshot_kind": snapshot_kind,
                "content_hash_status": content_hash_status,
                "primary_source": True,
            }
        ],
        "derived": [],
        "provenance": {
            "entities": [
                {"id": source_entity, "path": source_rel, "primary_source": True, "snapshot_kind": snapshot_kind, "content_hash_status": content_hash_status},
                {"id": content_entity, "path": "content.md"},
                {"id": evidence_entity, "path": "evidence.jsonl"},
            ],
            "activities": [
                {"id": activity, "run_id": run["run_id"], "started_at": run["started_at"], "finished_at": run["finished_at"], "status": run["status"]}
            ],
            "agents": [
                {"id": agent, "type": "SoftwareAgent", "name": run["job"]["name"], "version": run["job"]["version"], "capability": run["job"].get("capability")}
            ],
            "relations": [
                {"type": "used", "subject": activity, "object": source_entity},
                {"type": "wasGeneratedBy", "subject": content_entity, "object": activity},
                {"type": "wasGeneratedBy", "subject": evidence_entity, "object": activity},
                {"type": "wasDerivedFrom", "subject": content_entity, "object": source_entity},
                {"type": "wasDerivedFrom", "subject": evidence_entity, "object": source_entity},
            ],
        },
        "warnings": list(quality.get("warnings") or []),
    }
    _atomic_write_text(bundle / "bundle.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    report = validate_bundle_v2(bundle)
    if not report["valid"]:
        raise ValueError(f"v0.2 bundle validation failed: {report['errors']}")
    return report


def validate_bundle_v2(bundle: Path) -> dict[str, Any]:
    bundle = bundle.expanduser().resolve()
    errors: list[str] = []
    manifest_path = bundle / "bundle.json"
    if not manifest_path.is_file():
        return {"valid": False, "bundle": str(bundle), "schema_version": None, "errors": ["missing bundle.json"]}
    try:
        manifest = _read_json_object(manifest_path)
    except Exception as exc:
        return {"valid": False, "bundle": str(bundle), "schema_version": None, "errors": [str(exc)]}
    if manifest.get("schema_version") != RAW_V2_VERSION:
        errors.append("schema_version must be raw-multimodal/v0.2")
    expected_files = {
        "manifest": "bundle.json",
        "content": "content.md",
        "evidence": "evidence.jsonl",
        "quality_report": "quality-report.json",
        "processing_runs": "processing-runs.jsonl",
        "source_dir": "source/",
        "assets_dir": "assets/",
        "derived_dir": "derived/",
    }
    if manifest.get("files") != expected_files:
        errors.append("files must match the stable v0.2 layout")
    for name in ("bundle.json", "content.md", "evidence.jsonl", "quality-report.json", "processing-runs.jsonl"):
        if not (bundle / name).is_file():
            errors.append(f"missing required file: {name}")
    for name in ("source", "assets", "derived"):
        if not (bundle / name).is_dir():
            errors.append(f"missing required directory: {name}/")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("sources must contain at least one primary source")
    else:
        if not any(item.get("primary_source") is True for item in sources if isinstance(item, dict)):
            errors.append("sources must mark a primary source")
        for item in sources:
            if not isinstance(item, dict):
                errors.append("source entry must be an object")
                continue
            path = bundle / str(item.get("path", ""))
            if not path.is_file():
                errors.append(f"missing source entity: {item.get('path')}")
            elif item.get("sha256") != sha256_file(path):
                errors.append(f"source hash mismatch: {item.get('path')}")
            if item.get("snapshot_kind", "content") not in {"content", "reference"}:
                errors.append(f"invalid source snapshot_kind: {item.get('snapshot_kind')}")
            if item.get("content_hash_status", "verified") not in {"verified", "unavailable"}:
                errors.append(f"invalid source content_hash_status: {item.get('content_hash_status')}")
    relations = manifest.get("provenance", {}).get("relations", [])
    relation_types = {item.get("type") for item in relations if isinstance(item, dict)}
    for required in ("used", "wasGeneratedBy", "wasDerivedFrom"):
        if required not in relation_types:
            errors.append(f"missing provenance relation: {required}")
    try:
        runs = [json.loads(line) for line in (bundle / "processing-runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        if not runs:
            errors.append("processing-runs.jsonl is empty")
        if not any(run.get("capture_id") == manifest.get("capture_id") for run in runs if isinstance(run, dict)):
            errors.append("no processing run matches bundle capture_id")
    except Exception as exc:
        errors.append(f"invalid processing-runs.jsonl: {exc}")
    return {
        "valid": not errors,
        "bundle": str(bundle),
        "schema_version": manifest.get("schema_version"),
        "bundle_id": manifest.get("bundle_id"),
        "processing_status": manifest.get("processing_status"),
        "errors": errors,
        "warnings": manifest.get("warnings", []),
    }


def bundle_protocol_result(bundle: Path) -> dict[str, Any]:
    """Return the Level-1 JSON envelope for one generated Raw bundle."""
    bundle = bundle.expanduser().resolve()
    validation = validate_bundle(bundle)
    metadata_path = bundle / "metadata.json"
    content_path = bundle / "content.md"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    source = metadata.get("source", {})
    if not isinstance(source, dict):
        source = {"value": source}
    return {
        "status": "ok" if validation["valid"] else "invalid",
        "contract": SCHEMA_VERSION,
        "plugin_version": PLUGIN_VERSION,
        "bundle": str(bundle),
        "markdown": content_path.read_text(encoding="utf-8"),
        "markdown_path": str(content_path),
        "title": source.get("title"),
        "source": source.get("url") or source.get("path") or source.get("value"),
        "modality": metadata.get("source_type"),
        "metadata": metadata,
        "validation": validation,
    }


def emit_bundle(bundle: Path) -> int:
    result = bundle_protocol_result(bundle)
    emit_json(result)
    try:
        write_digest(bundle)
        update_raw_index(bundle)
    except Exception:
        pass  # digest/index are best-effort, never fail the ingest
    return 0 if result["status"] == "ok" else 2


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "mineru":
            return emit_bundle(package_mineru(args))
        if args.command == "markitdown":
            return emit_bundle(package_markitdown(args))
        if args.command == "watch":
            return emit_bundle(run_watch(args))
        if args.command == "watch-result":
            payload = json.loads(args.result.expanduser().resolve().read_text(encoding="utf-8"))
            return emit_bundle(
                package_watch_payload(
                    payload,
                    source=args.source,
                    source_file=args.source_file,
                    output_path=args.output,
                    title=args.title,
                    extractor_version=args.extractor_version,
                    warnings=args.warning,
                    benchmark=args.benchmark,
                    overwrite=args.overwrite,
                    frame_fallback_dir=args.result.expanduser().resolve().parent
                    / "assets"
                    / "frames",
                )
            )
        if args.command == "image":
            return emit_bundle(run_image(args))
        if args.command == "ingest":
            return run_ingest(args)
        if args.command == "route":
            emit_json(route_plan(args.source), indent=2)
            return 0
        if args.command == "probe":
            receipt = probe_url(
                args.source,
                timeout=args.timeout,
                max_bytes=args.max_bytes,
                max_redirects=args.max_redirects,
            )
            emit_json(receipt, indent=2)
            return 0 if receipt["status"] in {"ok", "needs_user_action"} else 2
        if args.command == "fetch":
            receipt = fetch_url(
                args.source,
                args.output,
                timeout=args.timeout,
                max_bytes=args.max_bytes,
                max_redirects=args.max_redirects,
                overwrite=args.overwrite,
            )
            emit_json(receipt, indent=2)
            return 0 if receipt["status"] in {"ok", "needs_user_action"} else 2
        if args.command == "validate":
            report = validate_bundle(args.bundle)
            emit_json(report, indent=2)
            return 0 if report["valid"] else 2
        if args.command == "finalize-v2":
            report = finalize_bundle_v2(
                args.bundle,
                args.capture_envelope,
                args.processing_run,
                args.source,
            )
            emit_json(report, indent=2)
            return 0
        if args.command == "validate-v2":
            report = validate_bundle_v2(args.bundle)
            emit_json(report, indent=2)
            return 0 if report["valid"] else 2
        if args.command == "check":
            return run_check(args)
        raise AssertionError(args.command)
    except subprocess.TimeoutExpired as exc:
        emit_json(
            {
                "status": "partial",
                "contract": SCHEMA_VERSION,
                "error": {"code": "EXTRACTION_TIMEOUT", "retryable": True,
                          "message": f"extractor exceeded its deadline: {exc.cmd}"},
                "next_action": "retry_with_larger_timeout_or_quick_tier",
            }
        )
        return 2
    except Exception as exc:  # CLI boundary: failures must remain machine-readable.
        emit_json(
            {
                "status": "error",
                "contract": SCHEMA_VERSION,
                "plugin_version": PLUGIN_VERSION,
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
