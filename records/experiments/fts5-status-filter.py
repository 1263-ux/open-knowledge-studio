"""Offline before/after experiment; synthetic Wiki, no personal knowledge access.

Run from the repo root with .venv/Scripts/python.exe (or an equivalent environment):
  records/experiments/fts5-status-filter.py --output <result.json>
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "cli"))
from knowledge_studio.search.fts5 import FTS5Backend
from knowledge_studio.store import _atomic_write

BASE = "f5d0cc26815bede4eea4de340eff97d59ab3406f"
FILES = ["cli/knowledge_studio/search/fts5.py", "cli/knowledge_studio/recall.py",
         "assets/hooks/user-prompt-recall.py"]


def corpus(size):
    pages, cases = [], []
    for index in range(20):
        term = f"orbital{index:02}"
        scenario = "mixed_state" if index < 10 else "many_nodes" if index < 15 else "control"
        relevant = []
        if scenario != "control":
            slug = f"{term}-leader"
            pages.append({"slug": slug, "title": term, "status": "dropped" if index < 10 else "active",
                          "body": "\n".join(f"## Section {n}\n{term} {term} ledger" for n in range(30))})
            if scenario == "many_nodes":
                relevant.append(slug)
        for n in range(3 - len(relevant)):
            slug = f"{term}-current-{n}"
            pages.append({"slug": slug, "title": f"Current policy {n}",
                          "status": "provisional" if n == 1 else "active",
                          "body": f"{term} ledger policy " + "detail " * n})
            relevant.append(slug)
        cases.append({"query": term, "scenario": scenario, "relevant": relevant})
    while len(pages) < size:
        pages.append({"slug": f"background-{len(pages)}", "title": "Background manual",
                      "status": "active", "body": "ledger unrelated maintenance reference"})
    return pages, cases


def latency(samples):
    return {"p50_ms": round(statistics.median(samples), 4),
            "p95_ms": round(sorted(samples)[int(len(samples) * .95) - 1], 4)}


def measure(backend, cases, repeats):
    results, samples = [], []
    for case in cases:
        backend.search(case["query"], limit=3)
    for case in cases:
        for _ in range(repeats):
            start = time.perf_counter_ns()
            hits = backend.search(case["query"], limit=3)
            samples.append((time.perf_counter_ns() - start) / 1e6)
        slugs = [h.slug for h in hits]
        relevant = set(case["relevant"])
        valid = [slug for slug in slugs if slug in relevant]
        first = next((i for i, slug in enumerate(slugs, 1) if slug in relevant), 0)
        results.append({**case, "slugs": slugs, "valid_count": len(valid),
                        "recall_at_3": len(valid) / len(relevant), "mrr": 1 / first if first else 0,
                        "inactive_count": len(slugs) - len(valid)})
    broad = []
    for _ in range(repeats * 20):
        start = time.perf_counter_ns()
        backend.search("ledger", limit=3)
        broad.append((time.perf_counter_ns() - start) / 1e6)
    return {
        "recall_at_3": statistics.mean(r["recall_at_3"] for r in results),
        "mrr": statistics.mean(r["mrr"] for r in results),
        "mean_valid_count": statistics.mean(r["valid_count"] for r in results),
        "inactive_return_rate": sum(r["inactive_count"] for r in results) / sum(len(r["slugs"]) for r in results),
        "selective_latency": latency(samples), "broad_latency": latency(broad), "cases": results,
    }


def hook_trial(code_root, kb, pages):
    wiki = kb / "wiki" / "computing" / "concepts"
    wiki.mkdir(parents=True)
    import yaml
    # One rare query and enough background to exercise the shipped 0.7 floor.
    chosen = pages[:4] + [p for p in pages if p["slug"].startswith("background-")][:100]
    for page in chosen:
        metadata = {k: v for k, v in page.items() if k not in {"slug", "body"}}
        metadata.update(type="concept", area="computing")
        _atomic_write(wiki / f"{page['slug']}.md", f"---\n{yaml.safe_dump(metadata)}---\n{page['body']}")
    _atomic_write(kb / "settings/recall.yaml", "search_backend: fts5\nrecall:\n  floor: 0.7\n  topn: 3\n")
    env = {k: v for k, v in os.environ.items() if not k.startswith("OKS_")}
    env.update(OKS_ROOT=str(kb), OKS_HOOK_OUTPUT="json", PYTHONPATH=str(code_root / "cli"),
               PYTHONIOENCODING="utf-8")
    process = subprocess.run(
        [sys.executable, str(code_root / "assets/hooks/user-prompt-recall.py")],
        input=json.dumps({"prompt": "orbital00", "session_id": "status-experiment", "cwd": str(kb)}),
        encoding="utf-8", capture_output=True, check=True, env=env, cwd=kb, timeout=30,
    )
    result = json.loads(process.stdout)
    trace_path = kb / "records/inject.jsonl"
    traces = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()] if trace_path.exists() else []
    slugs = result["trace"]["matches"]
    return {"status": result["status"], "matches": slugs,
            "inactive_count": sum(slug.endswith("-leader") for slug in slugs),
            "trace_slugs": [slug for row in traces for slug in row.get("slugs", [])],
            "context_contains_inactive": "(orbital00-leader)" in result["context"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pages", type=int, default=2000)
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    if args.pages < 200 or args.repeats < 1:
        parser.error("--pages must be >= 200 and --repeats must be >= 1")
    pages, cases = corpus(args.pages)
    with tempfile.TemporaryDirectory(prefix="oks-fts5-status-") as directory:
        work = Path(directory)
        archive = subprocess.check_output(["git", "archive", BASE, "cli/knowledge_studio", "assets/hooks"], cwd=ROOT)
        baseline_root = work / "baseline-code"
        baseline_root.mkdir()
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(baseline_root, filter="data")
        candidate_root = work / "candidate-code"
        shutil.copytree(baseline_root, candidate_root)
        for relative_path in FILES:
            shutil.copy2(ROOT / relative_path, candidate_root / relative_path)
        module = types.ModuleType("knowledge_studio.search._status_baseline")
        module.__package__ = "knowledge_studio.search"
        exec((baseline_root / FILES[0]).read_text(encoding="utf-8"), module.__dict__)
        baseline = module.FTS5Backend(root=str(work / "baseline-index"), db_path=":memory:")
        candidate = FTS5Backend(root=str(work / "candidate-index"), db_path=":memory:")
        try:
            baseline.index(pages)
            candidate.index(pages)
            metrics = {"baseline": measure(baseline, cases, args.repeats),
                       "candidate": measure(candidate, cases, args.repeats)}
            errors, order_matches = [], []
            for case in cases:
                oracle = [h for h in baseline.search(case["query"], limit=len(pages)) if h.slug in case["relevant"]][:3]
                hits = candidate.search(case["query"], limit=3)
                order_matches.append([h.slug for h in oracle] == [h.slug for h in hits])
                scores = {h.slug: h.score for h in oracle}
                errors.extend(abs(h.score - scores[h.slug]) for h in hits)
            result = {
                "baseline_commit": BASE, "candidate_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FILES},
                "corpus": "synthetic; 20 queries: 10 mixed-state, 5 many-node, 5 control",
                "pages": len(pages), "nodes": candidate._conn.execute("SELECT COUNT(*) FROM wiki_fts").fetchone()[0],
                "corpus_sha256": hashlib.sha256(json.dumps(pages, sort_keys=True).encode()).hexdigest(),
                "python": platform.python_version(), "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
                "samples_per_latency": len(cases) * args.repeats, "cache": "warm; excludes index construction",
                "bm25_max_absolute_error": max(errors), "all_eligible_order_matches": all(order_matches),
                **metrics,
                "hook_default_floor": {
                    "baseline": hook_trial(baseline_root, work / "baseline-kb", pages),
                    "candidate": hook_trial(candidate_root, work / "candidate-kb", pages),
                },
            }
        finally:
            baseline.close()
            candidate.close()
        _atomic_write(args.output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in {"baseline", "candidate"}}, indent=2))
    for name in ("baseline", "candidate"):
        print(name, json.dumps({k: v for k, v in result[name].items() if k != "cases"}))


if __name__ == "__main__":
    main()
