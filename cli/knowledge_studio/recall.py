"""Knowledge Recall — two-path retrieval: episodic search + knowledge stability.

Extracted from autpilot-web/backend/app/services/knowledge_recall.py.
Removed settings and knowledge_sync dependencies. Uses store.repo_root().

6+1-factor relevance scoring:
  1. Token overlap (×0.3) — jieba segmentation + intersection
  2. Substring match (+1.0 title / +0.5 body)
  3. Topic trace match (+2.0)
  4. Type boost (anti-pattern=1.5, strategy=0.8, concept=0.6)
  5. Review penalty boost (+2.0 wrong / +1.0 failure)
  6. Memory-curve score (×0.5)
  7. Goal boost — all active goals by default, one explicit goal for a
     reproducible run, or disabled. Matching area adds 0.8 and matching a
     goal keyword adds 0.4 to pages that already matched the query.

Explain mode exposes every score component and matching reason without
changing the ranking. Structured responses use recall-response/v1 and
recall-hit/v1 so evaluation tooling does not have to parse terminal tables.

Recall is read-only: a search does NOT count as a use and never mutates
access counts or page state. Access is recorded only via the explicit
`store.record_access` signal (exposed as `oks wiki use <slug>`), so the
memory curve reflects real usage, not query frequency.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge_studio.store import (
    get_goal,
    list_wiki_pages,
    load_active_goals,
    raw_dir,
    repo_root,
)

_logger = logging.getLogger(__name__)

DEFAULT_RECALL_LIMIT = 5
MAX_BODY_PREVIEW = 200
RECALL_HIT_SCHEMA = "recall-hit/v1"
RECALL_RESPONSE_SCHEMA = "recall-response/v1"
SEARCH_RESPONSE_SCHEMA = "search-response/v1"


def _resolve_goal_context(
    goal: str | None = None,
    *,
    goal_boost: bool = True,
) -> dict[str, Any]:
    """Resolve a deterministic goal selection for recall.

    ``None`` and ``active`` preserve the historical behavior of merging all
    active goals. ``none`` disables goal influence. Any other value selects a
    single goal by slug, including an inactive goal for historical replay.
    """
    requested = (goal or "active").strip()
    normalized = requested.lower()

    if not goal_boost or normalized == "none":
        selected: list[dict] = []
        mode = "none"
    elif normalized == "active":
        selected = load_active_goals()
        mode = "active"
    else:
        selected_goal = get_goal(requested)
        if selected_goal is None:
            raise ValueError(f"Goal not found: {requested}")
        selected = [selected_goal]
        mode = "explicit"

    domains: set[str] = set()
    keywords: set[str] = set()
    for item in selected:
        domains |= item.get("domains", set())
        keywords |= item.get("keywords", set())

    return {
        "mode": mode,
        "requested": requested,
        "goals": selected,
        "domains": domains,
        "keywords": keywords,
    }


def describe_goal_selection(
    goal: str | None = None,
    *,
    goal_boost: bool = True,
) -> dict[str, Any]:
    """Return the JSON-safe goal context used by a recall request."""
    context = _resolve_goal_context(goal, goal_boost=goal_boost)
    return {
        "mode": context["mode"],
        "requested": context["requested"],
        "slugs": [item["slug"] for item in context["goals"]],
        "domains": sorted(context["domains"]),
        "keywords": sorted(context["keywords"]),
    }


def recall(
    query: str = "",
    topic_id: int | None = None,
    limit: int = DEFAULT_RECALL_LIMIT,
    scope: str | None = None,
    goal_boost: bool = True,
    goal: str | None = None,
    explain: bool = False,
) -> dict[str, Any]:
    """Two-path recall: episodic (search) + knowledge (stability).

    scope narrows only the knowledge path (wiki area); episodic recall stays
    global since raw/ is time-partitioned and has no area.
    """
    goal_context = _resolve_goal_context(goal, goal_boost=goal_boost)
    return {
        "schema_version": RECALL_RESPONSE_SCHEMA,
        "query": query,
        "topic_id": topic_id,
        "scope": scope,
        "limit": limit,
        "goal": {
            "mode": goal_context["mode"],
            "requested": goal_context["requested"],
            "slugs": [item["slug"] for item in goal_context["goals"]],
            "domains": sorted(goal_context["domains"]),
            "keywords": sorted(goal_context["keywords"]),
        },
        "episodic": recall_episodic(query=query, topic_id=topic_id, limit=limit),
        "knowledge": _recall_knowledge_with_context(
            query=query,
            topic_id=topic_id,
            limit=limit,
            scope=scope,
            goal_context=goal_context,
            explain=explain,
        ),
    }


def recall_episodic(
    query: str = "",
    topic_id: int | None = None,
    limit: int = DEFAULT_RECALL_LIMIT,
) -> list[dict[str, Any]]:
    """Search episodic memory (raw/) by keyword with freshness weighting."""
    if not query.strip():
        return []

    root = repo_root()
    query_lower = query.lower().strip()
    query_tokens = _tokenize(query_lower)
    results: list[tuple[float, dict[str, Any]]] = []

    rd = raw_dir()
    if rd.exists():
        # Execution traces are provenance, not memory: they are reached through
        # wiki evidence links, never recalled. Without this an agent's own
        # comments outrank the human-collected material they were derived from.
        executions = rd / "executions"

        for f in rd.rglob("*.md"):
            if executions in f.parents:
                continue
            try:
                content = f.read_text(encoding="utf-8").lower()
                if _matches_query(content, query_lower, query_tokens):
                    freshness = _freshness_score(f)
                    snippet_idx = content.find(query_lower) if len(query_lower) > 3 else 0
                    snippet = content[snippet_idx:snippet_idx + 300] if snippet_idx >= 0 else content[:300]
                    results.append((freshness, {
                        "type": "raw",
                        "source_path": str(f.relative_to(root)),
                        "snippet": snippet,
                        "freshness": round(freshness, 3),
                        "relevance": round(freshness, 3),
                    }))
            except OSError:
                continue

        for f in rd.rglob("*.jsonl"):
            if executions in f.parents:
                continue
            try:
                for line in f.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    content = json.dumps(entry, ensure_ascii=False).lower()
                    if _matches_query(content, query_lower, query_tokens):
                        freshness = _freshness_score(f)
                        results.append((freshness + 0.5, {
                            "type": "trace",
                            "source_path": str(f.relative_to(root)),
                            "snippet": content[:300],
                            "freshness": round(freshness, 3),
                            "relevance": round(freshness + 0.5, 3),
                        }))
            except (json.JSONDecodeError, OSError):
                continue

    profiles_dir = root / "profiles"
    if profiles_dir.exists():
        for f in profiles_dir.rglob("*.md"):
            try:
                content = f.read_text(encoding="utf-8").lower()
                if _matches_query(content, query_lower, query_tokens):
                    freshness = _freshness_score(f)
                    snippet_idx = content.find(query_lower) if len(query_lower) > 3 else 0
                    snippet = content[snippet_idx:snippet_idx + 300] if snippet_idx >= 0 else content[:300]
                    results.append((freshness + 1.0, {
                        "type": "profile",
                        "source_path": str(f.relative_to(root)),
                        "snippet": snippet,
                        "freshness": round(freshness, 3),
                        "relevance": round(freshness + 1.0, 3),
                    }))
            except OSError:
                continue

    results.sort(key=lambda x: -x[0])
    ranked: list[dict[str, Any]] = []
    for rank, (_, item) in enumerate(results[:limit], start=1):
        item["schema_version"] = RECALL_HIT_SCHEMA
        item["channel"] = "episodic"
        item["rank"] = rank
        ranked.append(item)
    return ranked


def recall_knowledge(
    query: str = "",
    topic_id: int | None = None,
    limit: int = DEFAULT_RECALL_LIMIT,
    scope: str | None = None,
    goal_boost: bool = True,
    goal: str | None = None,
    explain: bool = False,
    type_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Find wiki pages relevant to the query via 6+1-factor scoring.

    scope: optional area name for soft, opt-in narrowing (reuses the `area`
    field). None = global recall across all areas. This is a soft scope, not
    a hard partition — it filters candidates before scoring, nothing more.

    goal_boost: compatibility switch that disables all goal influence when
    False. ``goal`` selects ``active`` (default), ``none``, or one goal slug.

    explain: include score components and human-readable match reasons. This
    does not change ranking and is intended for evaluation and debugging.

    type_filter: optional wiki type filter applied before ranking and limit.
    """
    goal_context = _resolve_goal_context(goal, goal_boost=goal_boost)
    return _recall_knowledge_with_context(
        query=query,
        topic_id=topic_id,
        limit=limit,
        scope=scope,
        goal_context=goal_context,
        explain=explain,
        type_filter=type_filter,
    )


def _recall_knowledge_with_context(
    *,
    query: str,
    topic_id: int | None,
    limit: int,
    scope: str | None,
    goal_context: dict[str, Any],
    explain: bool,
    type_filter: str | None = None,
) -> list[dict[str, Any]]:
    all_pages = list_wiki_pages()
    if not all_pages:
        return []

    scope_lower = scope.lower().strip() if scope else ""
    type_lower = type_filter.lower().strip() if type_filter else ""
    query_lower = query.lower().strip() if query else ""
    query_tokens = _tokenize(query_lower)

    scored: list[tuple[float, dict, dict[str, Any]]] = []
    for item in all_pages:
        if item.get("status") in ("dropped", "superseded") or item.get("archived"):
            continue

        if scope_lower and str(item.get("area", "")).lower().strip() != scope_lower:
            continue

        item_type = str(item.get("type", item.get("category", "concept")))
        if type_lower and item_type.lower().strip() != type_lower:
            continue

        components = _compute_relevance_components(
            item,
            query_lower,
            query_tokens,
            topic_id,
            goal_context,
        )
        relevance = components["final_score"]
        if relevance > 0:
            scored.append((relevance, item, components))

    scored.sort(key=lambda x: (-x[0], x[1]["slug"]))

    results: list[dict[str, Any]] = []
    for rank, (relevance, item, components) in enumerate(scored[:limit], start=1):
        review = item.get("review") or {}
        entry: dict[str, Any] = {
            "schema_version": RECALL_HIT_SCHEMA,
            "channel": "knowledge",
            "rank": rank,
            "slug": item["slug"],
            "title": item.get("title", item["slug"]),
            "type": item.get("type", item.get("category", "concept")),
            "area": item.get("area", ""),
            "status": item.get("status", "active"),
            "score": round(item.get("score", 0), 3),
            "relevance": round(relevance, 3),
            "confidence": item.get("confidence", 0.8),
            "body_preview": item.get("body", "")[:MAX_BODY_PREVIEW],
            "tags": item.get("tags", ""),
            "has_traces": bool(item.get("traces")),
            "relates_to": item.get("relates_to", ""),
            "relationship": item.get("relationship", ""),
        }
        if review.get("lesson"):
            entry["review_lesson"] = review["lesson"][:200]
        if explain:
            entry["score_components"] = {
                key: round(value, 6) if isinstance(value, float) else value
                for key, value in components.items()
                if key not in {"reasons", "goal_matches"}
            }
            entry["reasons"] = components["reasons"]
            entry["goal_matches"] = components["goal_matches"]
        results.append(entry)

    return results


def _tokenize(text: str) -> set[str]:
    """Split text into search tokens using jieba when available."""
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "to", "of", "in", "on", "at", "for", "with", "and", "or", "not",
        "this", "that", "it", "from", "by", "as", "how", "what", "why",
        "的", "了", "是", "在", "和", "与", "或", "也", "都", "就", "这", "那",
    }
    raw_words: list[str]
    try:
        import jieba

        import logging as _logging
        jieba.setLogLevel(_logging.WARNING)  # silence "Building prefix dict" chatter
        raw_words = list(jieba.cut_for_search(text))
    except Exception:
        raw_words = text.split()

    tokens = set()
    _strip_chars = ".,!?;:\"'()[]{}，。！？；：''""（）【】"
    for word in raw_words:
        word = word.strip(_strip_chars)
        if len(word) < 2 or word in stopwords:
            continue
        tokens.add(word)
    return tokens


def _compute_relevance(
    item: dict,
    query_lower: str,
    query_tokens: set[str],
    topic_id: int | None,
    goal_domains: set[str] | None = None,
    goal_keywords: set[str] | None = None,
) -> float:
    """Compatibility wrapper returning only the final relevance score."""
    context = {
        "mode": "legacy",
        "requested": "legacy",
        "goals": [],
        "domains": goal_domains or set(),
        "keywords": goal_keywords or set(),
    }
    return _compute_relevance_components(
        item, query_lower, query_tokens, topic_id, context
    )["final_score"]


def _compute_relevance_components(
    item: dict,
    query_lower: str,
    query_tokens: set[str],
    topic_id: int | None,
    goal_context: dict[str, Any],
) -> dict[str, Any]:
    """Compute relevance and retain every component used in the score."""
    reasons: list[str] = []

    title = item.get("title", "").lower()
    body = item.get("body", "").lower()
    tags_raw = item.get("tags", "")
    if isinstance(tags_raw, list):
        tags = " ".join(str(t) for t in tags_raw).lower()
    else:
        tags = str(tags_raw).lower()

    searchable = f"{title} {body} {tags}"
    overlap_count = sum(1 for token in query_tokens if token in searchable)
    token_overlap = overlap_count * 0.3
    if overlap_count:
        reasons.append(f"token-overlap:{overlap_count}")

    title_substring = 0.0
    body_substring = 0.0
    if query_lower and len(query_lower) > 3:
        if query_lower in title:
            title_substring = 1.0
            reasons.append("title-substring")
        if query_lower in body:
            body_substring = 0.5
            reasons.append("body-substring")

    topic_trace = 0.0
    if topic_id is not None:
        traces = item.get("traces") or []
        for trace in traces:
            if trace.get("kind") == "discuss" and str(trace.get("id")) == str(topic_id):
                topic_trace = 2.0
                reasons.append(f"topic-trace:{topic_id}")
                break

    base = token_overlap + title_substring + body_substring + topic_trace
    has_query = bool(query_lower.strip() or query_tokens or topic_id is not None)
    wiki_type = item.get("type", item.get("category", "concept"))
    type_boost = {
        "anti-pattern": 1.5,
        "strategy": 0.8,
        "concept": 0.6,
    }
    type_multiplier = type_boost.get(wiki_type, 0.5)
    typed_base = base * type_multiplier

    components: dict[str, Any] = {
        "token_overlap_count": overlap_count,
        "token_overlap": token_overlap,
        "title_substring": title_substring,
        "body_substring": body_substring,
        "topic_trace": topic_trace,
        "base_score": base,
        "type_multiplier": type_multiplier,
        "typed_base": typed_base,
        "review_decision": 0.0,
        "review_failure": 0.0,
        "memory_score": 0.0,
        "goal_area": 0.0,
        "goal_keyword": 0.0,
        "final_score": 0.0,
        "reasons": reasons,
        "goal_matches": [],
    }

    if has_query and base == 0:
        reasons.append("filtered:no-query-match")
        return components

    relevance = typed_base
    if base:
        reasons.append(f"type:{wiki_type}x{type_multiplier:g}")

    review = item.get("review")
    if review and isinstance(review, dict):
        if review.get("decision_correct") is False:
            components["review_decision"] = 2.0
            relevance += components["review_decision"]
            reasons.append("review:incorrect-decision")
        if review.get("outcome") == "failure":
            components["review_failure"] = 1.0
            relevance += components["review_failure"]
            reasons.append("review:failure")

    score = float(item.get("score", 0) or 0)
    components["memory_score"] = score * 0.5
    relevance += components["memory_score"]
    if components["memory_score"]:
        reasons.append("memory-score")

    goal_domains: set[str] = goal_context.get("domains", set())
    goal_keywords: set[str] = goal_context.get("keywords", set())
    page_area = str(item.get("area", "")).lower().strip()
    area_match = bool(goal_domains and page_area in goal_domains)
    keyword_matches = sorted(kw for kw in goal_keywords if kw in searchable)

    if relevance > 0 and area_match:
        components["goal_area"] = 0.8
        relevance += components["goal_area"]
        reasons.append(f"goal-area:{page_area}")
    if relevance > 0 and keyword_matches:
        components["goal_keyword"] = 0.4
        relevance += components["goal_keyword"]
        reasons.append(f"goal-keyword:{','.join(keyword_matches)}")

    goal_matches: list[dict[str, Any]] = []
    for goal in goal_context.get("goals", []):
        matched_keywords = sorted(
            keyword for keyword in goal.get("keywords", set()) if keyword in searchable
        )
        matched_area = bool(page_area and page_area in goal.get("domains", set()))
        if matched_area or matched_keywords:
            goal_matches.append({
                "slug": goal.get("slug", ""),
                "area": matched_area,
                "keywords": matched_keywords,
            })

    components["goal_matches"] = goal_matches
    components["final_score"] = relevance
    return components


def _matches_query(content: str, query_lower: str, query_tokens: set[str]) -> bool:
    if query_lower and len(query_lower) > 3 and query_lower in content:
        return True
    if query_tokens:
        return any(token in content for token in query_tokens)
    return bool(query_lower and query_lower in content)


def _freshness_score(file_path: Path) -> float:
    try:
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)
    except (OSError, ValueError):
        return 0.5
    days_old = max(0, (datetime.now(UTC) - mtime).days)
    return max(0.01, 1.0 * (0.95 ** days_old))
