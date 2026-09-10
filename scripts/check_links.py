#!/usr/bin/env python3
"""Link checker for the OKS repository and docs site.

Scans README*.md and docs/**/*.md for markdown links and verifies:

- site links (any *:github.io/open-knowledge-studio/... URL) resolve to a real
  page under docs/ — this is what keeps "README promises a page that does not
  exist" and clean-URL (trailing-slash) 404s out of the tree;
- relative links resolve to a file in the repository (`.html` links map to a
  `.md` source);
- external http(s) links return a non-404 status (skipped with --offline).

Exit code 1 on any broken link. CI runs this with --offline for determinism;
run it without --offline locally before pushing doc changes that touch URLs.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"

SITE_MARKER = "github.io/open-knowledge-studio"
STATUS_OK = {200, 301, 302, 303, 307, 308, 401, 403, 405, 429}

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def markdown_files() -> list[Path]:
    files = [p for p in REPO.glob("README*.md")]
    for pattern in ("docs/**/*.md",):
        files.extend(DOCS.glob(pattern[5:]))
    return sorted(set(files))


def strip_fences(text: str) -> str:
    """Remove fenced code blocks so links inside them are not checked."""
    return re.sub(r"```.*?```", "", text, flags=re.S)


def docs_page_exists(url_path: str) -> bool:
    """True if a docs/ source page renders at url_path (e.g. 'usage/recall.html')."""
    url_path = url_path.split("#", 1)[0]
    if not url_path or url_path == "index.html":
        return True  # site root renders docs/index.md
    if not url_path.endswith(".html"):
        return False
    stem = url_path[:-5]
    for parent in (DOCS,):
        if (parent / (stem + ".md")).is_file():
            return True
        # index pages: docs/usage/index.md renders at usage.html too
        if (parent / stem / "index.md").is_file():
            return True
    return False


def relative_target_exists(link: str, source: Path) -> bool:
    link_path = link.split("#", 1)[0]
    if not link_path:
        return True  # pure-anchor link
    target = (source.parent / link_path).resolve()
    if target.is_file() or target.is_dir():
        return True
    if link_path.endswith(".html"):
        # a rendered page may come from a sibling .md (e.g. oh-my/study.html -> study.md)
        return target.with_suffix(".md").is_file()
    return False


def check_external(url: str) -> str | None:
    """Return an error message, or None if the URL is acceptable."""
    # A browser-shaped UA avoids false negatives from hosts that reject
    # generic bot identifiers.  A few sites also reject HEAD while serving
    # the same URL over GET, so retry that method for transient/unsupported
    # HEAD responses.  Status checks stay strict: a 404 is still broken.
    headers = {"User-Agent": "Mozilla/5.0"}
    last_error: str | None = None
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in STATUS_OK:
                    return None
                if resp.status == 404:
                    return "HTTP 404"
                last_error = f"HTTP {resp.status}"
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return "HTTP 404"
            if exc.code in STATUS_OK:
                if exc.code == 405 and method == "HEAD":
                    # Some servers reject HEAD but serve the same URL via GET.
                    continue
                return None
            last_error = f"HTTP {exc.code}"
            if method == "HEAD":
                continue
        except Exception as exc:  # noqa: BLE001 - report anything unusual
            last_error = f"unreachable: {exc}"
            if method == "HEAD":
                continue
    return last_error or "unreachable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="skip external http(s) checks")
    args = parser.parse_args()

    failures: list[str] = []
    checked = 0
    for source in markdown_files():
        text = strip_fences(source.read_text(encoding="utf-8"))
        for match in LINK_RE.finditer(text):
            link = match.group(1)
            if link.startswith(("#", "mailto:")):
                continue
            checked += 1
            if SITE_MARKER in link:
                path = link.split("open-knowledge-studio", 1)[1].lstrip("/")
                if not docs_page_exists(path):
                    failures.append(f"{source.relative_to(REPO)}: site link has no docs page: {link}")
            elif link.startswith("http://") or link.startswith("https://"):
                if not args.offline:
                    error = check_external(link)
                    if error:
                        failures.append(f"{source.relative_to(REPO)}: external link {error}: {link}")
            else:
                if not relative_target_exists(link, source):
                    failures.append(f"{source.relative_to(REPO)}: broken relative link: {link}")

    print(f"checked {checked} links in {len(markdown_files())} files")
    for failure in failures:
        print("BROKEN:", failure)
    if failures:
        print(f"{len(failures)} broken link(s)")
        return 1
    print("all links ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
