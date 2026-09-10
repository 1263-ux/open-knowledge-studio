import importlib.util
import urllib.error
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).parents[1] / "check_links.py"
SPEC = importlib.util.spec_from_file_location("oks_check_links", MODULE_PATH)
assert SPEC and SPEC.loader
check_links = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_links)


class _Response:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_head_412_falls_back_to_get(monkeypatch):
    methods = []

    def fake_urlopen(request, timeout):
        methods.append(request.get_method())
        if request.get_method() == "HEAD":
            raise urllib.error.HTTPError(request.full_url, 412, "precondition", {}, None)
        return _Response(200)

    monkeypatch.setattr(check_links.urllib.request, "urlopen", fake_urlopen)

    assert check_links.check_external("https://example.test/video") is None
    assert methods == ["HEAD", "GET"]


@pytest.mark.parametrize("status", [403, 429])
def test_allowed_http_errors_are_not_broken(monkeypatch, status):
    methods = []

    def fake_urlopen(request, timeout):
        methods.append(request.get_method())
        raise urllib.error.HTTPError(request.full_url, status, "blocked", {}, None)

    monkeypatch.setattr(check_links.urllib.request, "urlopen", fake_urlopen)

    assert check_links.check_external("https://example.test/protected") is None
    assert methods == ["HEAD"]


def test_head_405_falls_back_to_get(monkeypatch):
    methods = []

    def fake_urlopen(request, timeout):
        methods.append(request.get_method())
        if request.get_method() == "HEAD":
            raise urllib.error.HTTPError(request.full_url, 405, "method not allowed", {}, None)
        return _Response(200)

    monkeypatch.setattr(check_links.urllib.request, "urlopen", fake_urlopen)

    assert check_links.check_external("https://example.test/get-only") is None
    assert methods == ["HEAD", "GET"]


def test_404_stays_broken_without_get_fallback(monkeypatch):
    methods = []

    def fake_urlopen(request, timeout):
        methods.append(request.get_method())
        raise urllib.error.HTTPError(request.full_url, 404, "missing", {}, None)

    monkeypatch.setattr(check_links.urllib.request, "urlopen", fake_urlopen)

    assert check_links.check_external("https://example.test/missing") == "HTTP 404"
    assert methods == ["HEAD"]


def test_transport_failure_is_reported_after_both_methods(monkeypatch):
    methods = []

    def fake_urlopen(request, timeout):
        methods.append(request.get_method())
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(check_links.urllib.request, "urlopen", fake_urlopen)

    result = check_links.check_external("https://example.test/offline")
    assert result == "unreachable: <urlopen error offline>"
    assert methods == ["HEAD", "GET"]
