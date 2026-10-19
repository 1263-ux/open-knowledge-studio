"""Classification admission and extraction/knowledge separation."""
import pytest
import yaml
from typer.testing import CliRunner

from knowledge_studio import cli, store, mail_knowledge
from knowledge_studio.knowledge_policy import is_source_material
from knowledge_studio.recall import recall_knowledge
from knowledge_studio.search.fts5 import FTS5Backend


def write(root, path, body="Reusable statement.", **meta):
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("---\n" + yaml.safe_dump(meta) + "---\n\n" + body, encoding="utf-8")
    return file


@pytest.mark.parametrize("fields", [
    {}, {"draft_area": "science"}, {"draft_type": "strategy"},
    {"draft_area": "ai", "draft_type": "concept"},
    {"draft_area": "science", "draft_type": "summary"},
    {"area": "science", "type": "strategy"},
    {"draft_area": [], "draft_type": "concept"},
    {"draft_area": "science", "draft_type": []},
])
def test_invalid_classification_preserves_candidate(tmp_path, monkeypatch, fields):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    candidate = write(tmp_path, "drafts/c.md", title="Candidate", **fields)
    before = candidate.read_bytes()
    with pytest.raises(ValueError):
        store.promote_draft("c")
    assert candidate.read_bytes() == before
    assert not list((tmp_path / "wiki").rglob("*.md"))


def test_explicit_review_corrects_legacy_classification(tmp_path, monkeypatch):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    write(tmp_path, "drafts/c.md", title="Reviewed science", type="strategy", area="ai")
    slug = store.promote_draft("c", area="science", wiki_type="strategy")
    page = store.get_wiki_page(slug)
    assert page["area"] == "science" and page["type"] == "strategy"
    assert page["human_reviewed_at"]
    assert not (tmp_path / "drafts/c.md").exists()


@pytest.mark.parametrize("marker", [{"source_type": "local-ocr-import"}, {"content_role": "source_material"}])
def test_source_cannot_promote_even_with_review_marker(tmp_path, monkeypatch, marker):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    candidate = write(tmp_path, "drafts/c.md", title="Source", draft_area="computing",
                      draft_type="concept", human_reviewed_at="2026-10-19", **marker)
    before = candidate.read_bytes()
    with pytest.raises(ValueError, match="Source material"):
        store.promote_draft("c")
    assert candidate.read_bytes() == before


@pytest.mark.parametrize("area,kind", [("science", "concept"), ("computing", "strategy")])
def test_dedup_classification_conflict_preserves_both_files(tmp_path, monkeypatch, area, kind):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    existing = store.write_wiki_page("Existing", "Same body", area="computing")
    candidate = write(tmp_path, "drafts/c.md", body="Same body", title="Candidate",
                      draft_area=area, draft_type=kind)
    before = {p: p.read_bytes() for p in [existing, candidate]}
    with pytest.raises(ValueError, match="classification"):
        store.promote_draft("c")
    assert {p: p.read_bytes() for p in before} == before


@pytest.mark.parametrize("backend", ["native", "fts5"])
def test_legacy_ocr_is_readable_but_not_knowledge(tmp_path, monkeypatch, backend):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    source = write(tmp_path, "wiki/source.md", body="ocrunicorn transcript", title="OCR",
                   type="concept", area="computing", source_type="local-ocr-import")
    before = source.read_bytes()
    assert store.get_wiki_page("source")["body"]
    assert not recall_knowledge("ocrunicorn", search_backend=backend)
    assert mail_knowledge.knowledge_map(tmp_path)["counts"]["points"] == 0
    assert source.read_bytes() == before


def test_fts_removes_previously_indexed_source(tmp_path):
    backend = FTS5Backend(root=str(tmp_path))
    page = dict(slug="source", title="ocrunicorn", body="ocrunicorn")
    try:
        backend.index([page])
        assert backend.search("ocrunicorn")
        backend.index([{**page, "content_role": "source_material"}])
        assert not backend.search("ocrunicorn")
        assert backend._conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 0
    finally:
        backend._conn.close()


def test_creation_has_no_silent_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    runner = CliRunner()
    assert "science" in runner.invoke(cli.app, ["wiki", "domains"]).stdout
    for options in [[], ["--area", "ai"], ["--area", "science", "--type", "summary"]]:
        result = runner.invoke(cli.app, ["wiki", "create", "--title", "Example", "--content", "Body", *options])
        assert result.exit_code != 0
    assert not list((tmp_path / "wiki").rglob("*.md"))


def test_title_and_provisional_do_not_define_source_identity():
    assert not is_source_material({"title": "OCR 汇编", "status": "provisional"})


@pytest.mark.parametrize("area,kind,source", [
    ("science", "concept", "auto"), ("computing", "strategy", "auto"),
    ("computing", "concept", "local-ocr-import"),
])
def test_create_conflicting_duplicate_never_mutates_existing(tmp_path, monkeypatch, area, kind, source):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    existing = store.write_wiki_page("Existing", "Same body", source_type=source)
    before = existing.read_bytes()
    result = CliRunner().invoke(cli.app, ["wiki", "create", "--title", "New",
        "--area", area, "--type", kind, "--content", "Same body"])
    assert result.exit_code != 0
    assert existing.read_bytes() == before
    assert len(list((tmp_path / "wiki").rglob("*.md"))) == 1
