"""Tests for the 6-factor recall engine."""
import json
import os
import yaml
from pathlib import Path

import pytest

from knowledge_studio.store import _atomic_write


@pytest.fixture
def kb_root(tmp_path, monkeypatch):
    """Create a temporary knowledge base with wiki pages."""
    monkeypatch.setenv("OKS_ROOT", str(tmp_path))

    wiki = tmp_path / "wiki" / "computing" / "concepts"
    wiki.mkdir(parents=True)

    pages = [
        {
            "slug": "git-branching",
            "title": "Git Branching Strategy",
            "type": "concept",
            "area": "computing",
            "status": "active",
            "importance": 0.8,
            "confidence": 0.9,
            "created": "2026-01-15T00:00:00+00:00",
            "tags": "git, version-control",
            "body": "Git branching strategy for managing feature development.",
        },
        {
            "slug": "docker-deployment",
            "title": "Docker Container Deployment",
            "type": "strategy",
            "area": "computing",
            "status": "active",
            "importance": 0.7,
            "confidence": 0.8,
            "created": "2026-02-01T00:00:00+00:00",
            "tags": "docker, deployment",
            "body": "Deploy containers using docker-compose for production.",
        },
        {
            "slug": "no-tests",
            "title": "Deploying Without Tests",
            "type": "anti-pattern",
            "area": "computing",
            "status": "active",
            "importance": 0.9,
            "confidence": 0.95,
            "created": "2026-03-01T00:00:00+00:00",
            "tags": "testing, deployment",
            "body": "Deploying to production without running tests leads to failures.",
            "review": {"decision_correct": False, "outcome": "failure"},
        },
    ]

    for page in pages:
        fm = {k: v for k, v in page.items() if k != "body" and k != "slug"}
        fm["pinned"] = False
        fm["archived"] = False
        fm["access_count"] = 0
        fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
        content = f"---\n{fm_str}---\n\n{page['body']}"
        _atomic_write(wiki / f"{page['slug']}.md", content)

    return tmp_path


def test_tokenize():
    from knowledge_studio.recall import _tokenize
    tokens = _tokenize("git branch strategy")
    assert isinstance(tokens, set)
    assert len(tokens) > 0


def test_recall_knowledge_returns_results(kb_root):
    from knowledge_studio.recall import recall_knowledge
    results = recall_knowledge("git branching", limit=5)
    assert len(results) > 0
    assert any(r["slug"] == "git-branching" for r in results)


def test_recall_knowledge_anti_pattern_boosted(kb_root):
    from knowledge_studio.recall import recall_knowledge
    results = recall_knowledge("deployment", limit=5)
    slugs = [r["slug"] for r in results]
    if "no-tests" in slugs and "docker-deployment" in slugs:
        assert slugs.index("no-tests") <= slugs.index("docker-deployment")


def test_recall_knowledge_no_results(kb_root):
    from knowledge_studio.recall import recall_knowledge
    results = recall_knowledge("nonexistent_topic_xyz123", limit=5)
    assert len(results) == 0


def test_recall_combined(kb_root):
    from knowledge_studio.recall import recall
    result = recall("git", limit=5)
    assert "episodic" in result
    assert "knowledge" in result
    assert isinstance(result["episodic"], list)
    assert isinstance(result["knowledge"], list)


def _write_goal(root: Path, slug: str, *, status="active", domains=None, keywords=None):
    gdir = root / "profiles" / "goals"
    gdir.mkdir(parents=True, exist_ok=True)
    fm = {
        "title": slug,
        "type": "goal",
        "status": status,
        "domains": domains or [],
        "keywords": keywords or [],
    }
    fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    _atomic_write(gdir / f"{slug}.md", f"---\n{fm_str}---\n\n# {slug}\n")


def test_load_active_goals_normalizes(kb_root):
    from knowledge_studio.store import load_active_goals
    _write_goal(kb_root, "active-goal", domains=["Computing", "Engineering"],
                keywords=["Docker", "Kubernetes"])
    _write_goal(kb_root, "done-goal", status="done", domains=["finance"],
                keywords=["budget"])

    goals = load_active_goals()
    assert len(goals) == 1
    g = goals[0]
    assert g["domains"] == {"computing", "engineering"}
    assert g["keywords"] == {"docker", "kubernetes"}


def test_goal_boost_lifts_matching_page(kb_root):
    from knowledge_studio.recall import recall_knowledge
    _write_goal(kb_root, "g", domains=["computing"], keywords=["docker"])

    off = recall_knowledge("deployment", limit=5, goal_boost=False)
    on = recall_knowledge("deployment", limit=5, goal_boost=True)

    def rel(results, slug):
        return next((r["relevance"] for r in results if r["slug"] == slug), None)

    assert rel(on, "docker-deployment") > rel(off, "docker-deployment")


def test_goal_boost_noop_without_goals(kb_root):
    from knowledge_studio.recall import recall_knowledge
    off = recall_knowledge("deployment", limit=5, goal_boost=False)
    on = recall_knowledge("deployment", limit=5, goal_boost=True)
    assert [r["slug"] for r in on] == [r["slug"] for r in off]


def test_recall_explain_components_rebuild_final_score(kb_root):
    from knowledge_studio.recall import RECALL_HIT_SCHEMA, recall_knowledge

    result = recall_knowledge("deployment", goal="none", explain=True)[0]
    components = result["score_components"]
    rebuilt = sum(
        components[key]
        for key in (
            "typed_base",
            "review_decision",
            "review_failure",
            "memory_score",
            "goal_area",
            "goal_keyword",
        )
    )

    assert result["schema_version"] == RECALL_HIT_SCHEMA
    assert result["channel"] == "knowledge"
    assert result["rank"] == 1
    assert components["final_score"] == pytest.approx(rebuilt)
    assert result["relevance"] == pytest.approx(rebuilt, abs=1e-3)
    assert result["reasons"]


def test_recall_explain_does_not_change_ranking(kb_root):
    from knowledge_studio.recall import recall_knowledge

    plain = recall_knowledge("deployment", goal="none")
    explained = recall_knowledge("deployment", goal="none", explain=True)

    assert [item["slug"] for item in explained] == [item["slug"] for item in plain]
    assert [item["relevance"] for item in explained] == [
        item["relevance"] for item in plain
    ]
    assert all("score_components" not in item for item in plain)
    assert all("score_components" in item for item in explained)


def test_explicit_goal_does_not_merge_other_active_goals(kb_root):
    from knowledge_studio.recall import recall_knowledge

    _write_goal(kb_root, "docker-goal", keywords=["docker"])
    _write_goal(kb_root, "testing-goal", keywords=["tests"])

    baseline = recall_knowledge("deployment", goal="none", explain=True)
    selected = recall_knowledge("deployment", goal="docker-goal", explain=True)

    def hit(results, slug):
        return next(item for item in results if item["slug"] == slug)

    docker_base = hit(baseline, "docker-deployment")
    docker_selected = hit(selected, "docker-deployment")
    tests_base = hit(baseline, "no-tests")
    tests_selected = hit(selected, "no-tests")

    assert docker_selected["relevance"] == pytest.approx(
        docker_base["relevance"] + 0.4
    )
    assert tests_selected["relevance"] == tests_base["relevance"]
    assert docker_selected["goal_matches"] == [
        {"slug": "docker-goal", "area": False, "keywords": ["docker"]}
    ]
    assert tests_selected["goal_matches"] == []


def test_explicit_goal_must_exist(kb_root):
    from knowledge_studio.recall import recall_knowledge

    with pytest.raises(ValueError, match="Goal not found"):
        recall_knowledge("deployment", goal="missing-goal")


def test_recall_response_describes_goal_selection(kb_root):
    from knowledge_studio.recall import RECALL_RESPONSE_SCHEMA, recall

    _write_goal(kb_root, "docker-goal", status="done", keywords=["docker"])
    result = recall("deployment", goal="docker-goal", explain=True)

    assert result["schema_version"] == RECALL_RESPONSE_SCHEMA
    assert result["goal"]["mode"] == "explicit"
    assert result["goal"]["slugs"] == ["docker-goal"]
    assert result["goal"]["keywords"] == ["docker"]
    assert result["knowledge"][0]["score_components"]


def test_recall_cli_emits_machine_readable_json(kb_root):
    from typer.testing import CliRunner

    from knowledge_studio.cli import app

    result = CliRunner().invoke(
        app,
        ["recall", "deployment", "--goal", "none", "--format", "json", "--explain"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "recall-response/v1"
    assert payload["goal"]["mode"] == "none"
    assert payload["knowledge"][0]["score_components"]


def test_search_cli_rejects_unknown_goal(kb_root):
    from typer.testing import CliRunner

    from knowledge_studio.cli import app

    result = CliRunner().invoke(app, ["search", "deployment", "--goal", "missing"])

    assert result.exit_code == 2
    assert "Goal not found: missing" in result.output


def test_search_cli_json_filters_type_before_limit(kb_root):
    from typer.testing import CliRunner

    from knowledge_studio.cli import app

    result = CliRunner().invoke(
        app,
        [
            "search",
            "deployment",
            "--type",
            "strategy",
            "--limit",
            "1",
            "--goal",
            "none",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "search-response/v1"
    assert payload["result_count"] == 1
    assert payload["knowledge"][0]["slug"] == "docker-deployment"
    assert payload["knowledge"][0]["rank"] == 1


def test_promote_draft_carries_human_note(kb_root):
    from knowledge_studio.store import promote_draft, parse_wiki_file
    drafts = kb_root / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    fm = {
        "title": "Memory Management Insight",
        "draft_type": "concept",
        "draft_area": "computing",
        "source_pages": [],
        "source_note": "这个内容很不错，对于记忆管理",
        "status": "draft",
    }
    fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    _atomic_write(drafts / "mem-insight.md", f"---\n{fm_str}---\n\nBody text about memory.")

    promote_draft("mem-insight")

    pages = list((kb_root / "wiki").rglob("*.md"))
    metas = [parse_wiki_file(p) for p in pages]
    promoted = next(m for m in metas if m and m.get("title") == "Memory Management Insight")
    assert promoted.get("human_note") == "这个内容很不错，对于记忆管理"


def test_recall_is_read_only(kb_root):
    """A search must not count as a use — recall never mutates access state."""
    from knowledge_studio.recall import recall_knowledge
    from knowledge_studio.store import get_wiki_page

    results = recall_knowledge("git branching", limit=5)
    assert any(r["slug"] == "git-branching" for r in results)

    # No access log should be created, and access_count stays 0.
    assert not (kb_root / ".oks" / "access.json").exists()
    assert get_wiki_page("git-branching")["access_count"] == 0


def test_episodic_recall_excludes_execution_traces(kb_root):
    """Traces are provenance: an agent's own comments must not come back as memory."""
    from knowledge_studio.recall import recall_episodic

    material = kb_root / "raw" / "2026" / "07" / "30" / "articles"
    material.mkdir(parents=True)
    _atomic_write(material / "kafka-notes.md", "kafka rebalance notes from a human")

    run = kb_root / "raw" / "executions" / "run-x"
    run.mkdir(parents=True)
    _atomic_write(run / "notes.md", "kafka rebalance guessed by the agent")
    _atomic_write(
        run / "events.jsonl",
        json.dumps({"event_type": "ai_comment", "payload": {"comment": "kafka rebalance"}}) + "\n",
    )

    paths = [hit["source_path"] for hit in recall_episodic("kafka rebalance", limit=10)]
    assert any("kafka-notes.md" in path for path in paths)
    assert not any("executions" in path for path in paths)


def test_episodic_recall_never_leaks_other_identities(kb_root):
    """CONSTITUTION A2: another user's preferences / another project's facts stay out."""
    from knowledge_studio.recall import recall_episodic

    profiles = kb_root / "profiles"
    (profiles / "users" / "alice").mkdir(parents=True)
    (profiles / "users" / "bob").mkdir(parents=True)
    (profiles / "projects").mkdir(parents=True)
    _atomic_write(profiles / "team.md", "team standard: redis caching everywhere")
    _atomic_write(profiles / "users" / "alice" / "profile.md", "alice tunes redis caching")
    _atomic_write(profiles / "users" / "bob" / "profile.md", "bob tunes redis caching, salary 50k")
    _atomic_write(profiles / "projects" / "mine.md", "mine uses redis caching")
    _atomic_write(profiles / "projects" / "theirs.md", "theirs uses redis caching, confidential")

    # Without an identity, every private profile is excluded rather than leaked.
    anonymous = [hit["source_path"] for hit in recall_episodic("redis caching", limit=10)]
    assert any("team.md" in path for path in anonymous)
    assert not any("users/" in path for path in anonymous)
    assert not any("projects/" in path for path in anonymous)

    scoped = [
        hit["source_path"]
        for hit in recall_episodic("redis caching", limit=10, user_id="alice", project_slug="mine")
    ]
    assert any("alice" in path for path in scoped)
    assert any("mine.md" in path for path in scoped)
    assert not any("bob" in path for path in scoped)
    assert not any("theirs.md" in path for path in scoped)


def test_record_access_promotes_provisional(kb_root, monkeypatch):
    """The explicit-use signal increments access_count and promotes at 3 uses."""
    import yaml
    from knowledge_studio.store import record_access, get_wiki_page, _atomic_write

    prov = kb_root / "wiki" / "computing" / "concepts" / "prov.md"
    fm = {
        "title": "Provisional Page",
        "type": "concept",
        "area": "computing",
        "status": "provisional",
        "importance": 0.6,
        "confidence": 0.8,
        "created": "2026-01-15T00:00:00+00:00",
        "pinned": False,
        "archived": False,
    }
    fm_str = yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)
    _atomic_write(prov, f"---\n{fm_str}---\n\nProvisional body.")

    for _ in range(3):
        record_access("prov")

    updated = get_wiki_page("prov")
    assert updated["access_count"] == 3
    assert updated["status"] == "active"
