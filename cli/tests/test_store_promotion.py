from pathlib import Path

from knowledge_studio import store


def test_write_wiki_page_rejects_area_path_traversal(monkeypatch, tmp_path):
    """area becomes a directory name — an unchecked value escapes the whole KB.

    Before the whitelist, area="../../outside" wrote to
    <kb>/wiki/../../outside/concept/, i.e. outside the knowledge base entirely.
    """
    import pytest

    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    for area in ("../../outside", "../sibling", "a/b", "Computing", "_hidden", ""):
        with pytest.raises(ValueError, match="Invalid area"):
            store.write_wiki_page(
                title="pwned", content="x" * 60, wiki_type="concepts", area=area
            )

    # Nothing may land anywhere, inside or outside the KB.
    assert list(tmp_path.rglob("*pwned*")) == []
    assert not (tmp_path.parent / "outside").exists()

    # A legal area still works.
    page = store.write_wiki_page(
        title="fine", content="y" * 60, wiki_type="concepts", area="product-design"
    )
    assert page.is_relative_to(tmp_path / "wiki" / "product-design")


def test_promote_draft_refuses_a_rejected_draft(monkeypatch, tmp_path):
    """CONSTITUTION A3: once a human says no, promotion must not walk past it.

    Feishu's reject writes status=rejected and keeps the draft on disk, so
    without this gate `oks drafts promote` would resurrect rejected content.
    """
    import pytest

    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    draft = tmp_path / "drafts" / "was-rejected.md"
    draft.parent.mkdir(parents=True)
    draft.write_text(
        '''---
title: "Rejected by review"
draft_type: strategy
draft_area: computing
status: rejected
---

A human already declined this content.
''',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="rejected"):
        store.promote_draft("was-rejected")

    assert draft.exists(), "the rejected draft must stay for audit"
    wiki = tmp_path / "wiki"
    assert not wiki.exists() or list(wiki.rglob("*.md")) == []


def test_cli_reports_security_errors_without_traceback(monkeypatch, tmp_path):
    """A blocked action must read as an error message, not a Python traceback."""
    from typer.testing import CliRunner

    from knowledge_studio.cli import app

    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["wiki", "create", "--title", "pwned", "--type", "concept",
         "--area", "../../outside", "--content", "x" * 60],
    )
    assert result.exit_code == 1
    assert "Invalid area" in result.output
    assert "Traceback" not in result.output

    draft = tmp_path / "drafts" / "nope.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(
        "---\ntitle: No\ndraft_type: concept\ndraft_area: computing\nstatus: rejected\n---\n\nbody\n",
        encoding="utf-8",
    )
    result = runner.invoke(app, ["drafts", "promote", "nope"])
    assert result.exit_code == 1
    assert "rejected" in result.output
    assert "Traceback" not in result.output


def test_promote_draft_preserves_tags_traces_and_review(monkeypatch, tmp_path):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    draft = tmp_path / "drafts" / "base-loop.md"
    draft.parent.mkdir()
    draft.write_text(
        '''---
title: "Feishu Base learning loop"
draft_type: strategy
draft_area: computing
source_type: external
tags: "feishu, learning-loop"
traces:
  - kind: execution
    id: run_1
    path: raw/bundle
review:
  outcome: success
  decision_correct: true
  lesson: "accepted in Base"
  reviewed_at: "2026-07-22T00:20:00+08:00"
status: draft
---

The reviewed body is preserved as the Wiki page content.
''',
        encoding="utf-8",
    )

    slug = store.promote_draft("base-loop")
    page = store.get_wiki_page(slug)

    assert page is not None
    assert page["source_type"] == "external"
    assert page["tags"] == "feishu, learning-loop"
    assert page["traces"][0]["id"] == "run_1"
    assert page["review"]["lesson"] == "accepted in Base"
    assert Path(page["file_path"]).parent.name == "strategies"
    assert not draft.exists()


def test_promote_draft_marks_the_superseded_page(monkeypatch, tmp_path):
    """CONSTITUTION A4: promotion must not leave the replaced page active."""
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    old_slug = store.write_wiki_page(
        title="Old caching guidance",
        content="Use a single global cache.",
        wiki_type="strategy",
        area="computing",
    ).stem

    draft = tmp_path / "drafts" / "caching-v2.md"
    draft.parent.mkdir(exist_ok=True)
    draft.write_text(
        f'''---
title: "Caching guidance v2"
draft_type: strategy
draft_area: computing
relates_to: {old_slug}
relationship: supersedes
status: draft
---

Per-tenant caches replace the single global cache.
''',
        encoding="utf-8",
    )

    new_slug = store.promote_draft("caching-v2")
    old_page = store.get_wiki_page(old_slug)
    new_page = store.get_wiki_page(new_slug)

    assert old_page["status"] == "superseded"
    assert old_page["superseded_by"] == new_slug
    assert new_page["relates_to"] == old_slug
    assert new_page["relationship"] == "supersedes"


def test_promote_draft_uses_explicit_slug_hint_for_non_ascii_title(monkeypatch, tmp_path):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    draft = tmp_path / "drafts" / "feishu-review-return-provenance.md"
    draft.parent.mkdir()
    draft.write_text(
        '''---
title: "飞书个人审核回程的可追溯门禁"
draft_type: strategy
draft_area: computing
status: draft
---

Reviewed knowledge.
''',
        encoding="utf-8",
    )

    slug = store.promote_draft(
        "feishu-review-return-provenance",
        slug_hint="feishu-review-return-provenance",
    )

    assert slug.endswith("-feishu-review-return-provenance")
    assert store.get_wiki_page(slug)["title"] == "飞书个人审核回程的可追溯门禁"
