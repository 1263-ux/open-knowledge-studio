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
from _shared import (
    emit_json, emit_progress, sha256_file, write_json, write_jsonl,
    exactly_one, prepare_output, normalize_ocr_text, order_ocr_blocks,
    parse_ocr_roi, format_media_time,
)


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




def validate_bundle(bundle: Path) -> dict[str, Any]:
    from extractors.markitdown import markdown_asset_references
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
            from extractors.mineru import package_mineru
            return emit_bundle(package_mineru(args))
        if args.command == "markitdown":
            from extractors.markitdown import package_markitdown
            return emit_bundle(package_markitdown(args))
        if args.command == "watch":
            from extractors.watch import run_watch
            return emit_bundle(run_watch(args))
        if args.command == "watch-result":
            from extractors.watch import package_watch_payload
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
            from extractors.image import run_image
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
