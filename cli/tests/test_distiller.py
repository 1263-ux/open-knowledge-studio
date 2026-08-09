"""Tests for the distiller — evolve, digest, decay."""
import yaml
import pytest

from knowledge_studio.store import _atomic_write


@pytest.fixture
def kb_root(tmp_path, monkeypatch):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    wiki = tmp_path / "wiki" / "computing" / "concepts"
    wiki.mkdir(parents=True)
    drafts = tmp_path / "drafts"
    drafts.mkdir(parents=True)
    for i in range(4):
        fm = {
            "title": f"Pattern {i}", "type": "concept", "area": "computing",
            "status": "active", "importance": 0.8, "confidence": 0.9,
            "created": "2026-01-15T00:00:00+00:00", "tags": "shared-tag, other",
            "pinned": False, "archived": False, "access_count": 0,
        }
        fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
        _atomic_write(wiki / f"pattern-{i}.md", f"---\n{fm_str}---\n\nContent for pattern {i}.")
    return tmp_path


def test_evolve_knowledge_creates_draft(kb_root):
    from knowledge_studio.distiller import evolve_knowledge
    result = evolve_knowledge()
    assert result["drafts"] >= 1
    assert len(list((kb_root / "drafts").glob("*.md"))) >= 1


def test_write_digest_creates_file(kb_root):
    from knowledge_studio.distiller import write_digest
    path = write_digest("Test Digest", "Content.", source_count=3)
    assert path.exists()
    assert "Test Digest" in path.read_text()


def test_run_distill_cycle(kb_root):
    from knowledge_studio.distiller import run_distill_cycle
    result = run_distill_cycle()
    assert "dropped" in result
    assert "drafts" in result


def test_evolve_no_duplicates(kb_root):
    from knowledge_studio.distiller import evolve_knowledge
    evolve_knowledge()
    result2 = evolve_knowledge()
    assert result2["drafts"] == 0


def test_decay_archives_without_deleting_anything(kb_root):
    """A3 lets decay archive without review only because it destroys nothing.

    Archiving flags the page and leaves the file in Git, so the worst case is
    lost recall coverage, not lost knowledge. If decay ever deletes content,
    the asymmetry with A3's human-review gate on promotion stops being
    defensible.
    """
    from knowledge_studio.store import apply_decay, parse_wiki_file

    page = kb_root / "wiki" / "computing" / "concepts" / "pattern-0.md"
    # Force it under any sane archive threshold.
    stale = page.read_text(encoding="utf-8").replace(
        "created: '2026-01-15T00:00:00+00:00'", "created: '2019-01-01T00:00:00+00:00'"
    ).replace("importance: 0.8", "importance: 0.01")
    _atomic_write(page, stale)

    apply_decay()

    assert page.is_file(), "decay deleted a wiki page"
    meta = parse_wiki_file(page)
    assert meta is not None
    assert "Content for pattern 0." in meta["body"], "decay destroyed the content"
