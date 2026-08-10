import hashlib
import json
from pathlib import Path

import pytest

from knowledge_studio import store


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


def test_reject_draft_preserves_append_only_review_receipt(monkeypatch, tmp_path):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    draft = tmp_path / "drafts" / "not-worth-keeping.md"
    draft.parent.mkdir()
    draft_content = """---
title: Not worth keeping
status: draft
---

This candidate was rejected.
"""
    draft.write_text(draft_content, encoding="utf-8")

    receipt_path = store.reject_draft("not-worth-keeping")

    assert not draft.exists()
    assert receipt_path.parent == tmp_path / "drafts" / "rejected"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["decision"] == "rejected"
    assert receipt["draft_slug"] == "not-worth-keeping"
    assert receipt["draft_title"] == "Not worth keeping"
    assert receipt["draft_sha256"] == hashlib.sha256(draft_content.encode()).hexdigest()
    assert "draft_content" not in receipt


def test_reject_draft_creates_a_new_receipt_for_repeated_slug(monkeypatch, tmp_path):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    drafts = tmp_path / "drafts"
    drafts.mkdir()

    (drafts / "repeat.md").write_text("---\ntitle: First\n---\nfirst", encoding="utf-8")
    first = store.reject_draft("repeat")
    (drafts / "repeat.md").write_text("---\ntitle: Second\n---\nsecond", encoding="utf-8")
    second = store.reject_draft("repeat")

    assert first != second
    assert first.exists()
    assert second.exists()


@pytest.mark.parametrize("slug", ["../wiki/keep", "..\\wiki\\keep", ".", ""])
def test_draft_actions_reject_path_traversal(monkeypatch, tmp_path, slug):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))

    with pytest.raises(ValueError, match="Invalid draft slug"):
        store.reject_draft(slug)
    with pytest.raises(ValueError, match="Invalid draft slug"):
        store.promote_draft(slug)


def test_reject_keeps_draft_when_receipt_write_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    draft = tmp_path / "drafts" / "keep-on-failure.md"
    draft.parent.mkdir()
    draft.write_text("---\ntitle: Keep on failure\n---\nbody", encoding="utf-8")

    def fail_write(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(store, "_atomic_write", fail_write)

    with pytest.raises(OSError, match="disk full"):
        store.reject_draft("keep-on-failure")

    assert draft.exists()


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


def _write_draft(root: Path, name: str, body: str, **fields) -> None:
    import yaml

    meta = {
        "title": fields.pop("title", name),
        "draft_type": "concept",
        "draft_area": "computing",
        "status": "pending",
        **fields,
    }
    drafts = root / "drafts"
    drafts.mkdir(exist_ok=True)
    front = yaml.dump(meta, allow_unicode=True, sort_keys=False)
    (drafts / f"{name}.md").write_text(f"---\n{front}---\n\n{body}\n", encoding="utf-8")


def test_dedup_hit_still_records_the_human_review(monkeypatch, tmp_path):
    """Promoting a body-identical draft used to silently discard the approval.

    write_wiki_page returned the existing page early, so human_reviewed_at was
    never written and status stayed provisional — then promote_draft deleted the
    draft, making the lost review unrecoverable, with no error reported.
    """
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    body = "Cache invalidation must be explicit."
    existing = store.write_wiki_page(
        title="Old Note", content=body, area="computing"
    )
    assert store.get_wiki_page(existing.stem)["status"] == "provisional"

    _write_draft(
        tmp_path, "d1", body,
        title="Reviewed Note",
        supersedes=existing.stem,
        relationship="supersedes",
    )
    slug = store.promote_draft("d1")

    page = store.get_wiki_page(slug)
    assert page["human_reviewed_at"], "the human review was discarded"
    assert page["status"] == "active"
    # The dedup target IS the page it declared it supersedes — a page cannot
    # supersede itself.
    assert page.get("superseded_by") in (None, "")


def test_dedup_hit_still_applies_the_declared_relationship(monkeypatch, tmp_path):
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))
    body = "Cache invalidation must be explicit."
    store.write_wiki_page(title="Old Note", content=body, area="computing")
    other = store.write_wiki_page(
        title="Other", content="a completely different body", area="computing"
    )

    _write_draft(
        tmp_path, "d2", body,
        title="Duplicate Body",
        supersedes=other.stem,
        relationship="supersedes",
    )
    store.promote_draft("d2")

    superseded = store.get_wiki_page(other.stem)
    assert superseded["status"] == "superseded", "A4 relationship was dropped"
    assert superseded["superseded_by"]
