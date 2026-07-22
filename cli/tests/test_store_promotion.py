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
