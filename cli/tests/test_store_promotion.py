from pathlib import Path

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
