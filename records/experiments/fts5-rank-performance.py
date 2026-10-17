"""Paired SQL-sort/rank-cursor comparison on the same synthetic FTS5 index.

Replays the previous filtered query algorithm; this is not a production backend.
Run: .venv/Scripts/python.exe records/experiments/fts5-rank-performance.py --output <json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import runpy
import sqlite3
import tempfile
import time

EXPERIMENT = runpy.run_path(str(Path(__file__).with_name("fts5-status-filter.py")))
ROOT = EXPERIMENT["ROOT"]
from knowledge_studio.search import SearchHit
from knowledge_studio.store import _atomic_write


def previous_search(backend, query, limit=3):
    """Replay 2026-10-15's filtered SQL with growing node prefixes."""
    backend._maybe_reindex()
    match = backend._build_match_expr(query)
    if match is None:
        return []
    weights = backend._weights
    sql = (
        "SELECT f.slug, f.title, p.abstract, "
        f"bm25(wiki_fts, 0, 0, {weights['title']}, {weights['body']}, "
        f"{weights['tags']}, {weights['code_blocks']}) AS rank "
        "FROM wiki_fts f JOIN pages p ON f.slug = p.slug "
        "WHERE wiki_fts MATCH ? "
        "AND COALESCE(LOWER(TRIM(p.status)), 'active') NOT IN (?, ?) "
        "AND COALESCE(p.archived, 0) = 0 ORDER BY rank LIMIT ?"
    )
    count = max(limit * 8, 64)
    while True:
        rows = backend._conn.execute(sql, (match, "dropped", "superseded", count)).fetchall()
        best, order = {}, []
        for slug, title, abstract, rank in rows:
            if slug not in best:
                best[slug] = (title or slug, abstract or "", float(-rank))
                order.append(slug)
        if len(order) >= limit or len(rows) < count:
            break
        count *= 2
    return [SearchHit(slug=slug, title=best[slug][0], score=best[slug][2],
                      abstract=best[slug][1] or None, backend="fts5") for slug in order][:limit]


def query_plans(backend):
    plans = {}
    for name, search in (("previous", previous_search), ("optimized", lambda b, q: b.search(q, limit=3))):
        statements = []
        backend._conn.set_trace_callback(statements.append)
        try:
            search(backend, "ledger")
        finally:
            backend._conn.set_trace_callback(None)
        query = next(sql for sql in statements if sql.startswith("SELECT f.slug"))
        plans[name] = [row[3] for row in backend._conn.execute("EXPLAIN QUERY PLAN " + query)]
    return plans


def measure(size, repeats):
    pages, cases = EXPERIMENT["corpus"](size)
    with tempfile.TemporaryDirectory(prefix="oks-fts5-rank-") as directory:
        backend = EXPERIMENT["FTS5Backend"](root=directory, db_path=":memory:")
        try:
            backend.index(pages)
            errors = []
            for query in ["ledger"] + [case["query"] for case in cases]:
                previous = previous_search(backend, query)
                optimized = backend.search(query, limit=3)
                assert [h.slug for h in previous] == [h.slug for h in optimized], query
                errors.extend(abs(a.score - b.score) for a, b in zip(previous, optimized))
            assert max(errors) == 0, errors
            result = {"pages": size, "order_matches": True, "bm25_max_absolute_error": max(errors),
                      "plans": query_plans(backend), "samples_per_group": len(cases) * repeats}
            for group, queries in (
                ("broad", ["ledger"] * len(cases) * repeats),
                ("selective", [case["query"] for case in cases] * repeats),
            ):
                samples = {"previous": [], "optimized": []}
                for index, query in enumerate(queries):
                    names = ("previous", "optimized") if index % 2 == 0 else ("optimized", "previous")
                    for name in names:
                        start = time.perf_counter_ns()
                        if name == "previous":
                            previous_search(backend, query)
                        else:
                            backend.search(query, limit=3)
                        samples[name].append((time.perf_counter_ns() - start) / 1e6)
                result[group] = {name: EXPERIMENT["latency"](values) for name, values in samples.items()}
            return result
        finally:
            backend.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    result = {
        "method": "warm, same in-memory index; alternate call order; exclude index construction",
        "previous": "replay of filtered ORDER BY bm25 and growing node prefixes; no scope/type filter",
        "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
        "platform": platform.platform(),
        "candidate_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                             for p in EXPERIMENT["FILES"]},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runs": [measure(size, args.repeats) for size in (2000, 10000)],
    }
    _atomic_write(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
