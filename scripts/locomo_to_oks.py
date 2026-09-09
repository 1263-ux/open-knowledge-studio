#!/usr/bin/env python3
"""Convert LoCoMo dataset to OKS eval format.

1. Each of 10 conversations → one wiki page (conversation full text).
2. Each QA → eval entry (query=question, expected=sample slug, topic=category).
3. Excludes category 5 (adversarial), matching OpenViking's protocol.

Usage:
    python3 scripts/locomo_to_oks.py <locomo10.json> <out-wiki-dir> <out-eval.yaml> [--per-sample 10]
"""
import json, sys, os
from pathlib import Path

CAT_NAMES = {1: "multi-hop", 2: "temporal", 3: "open-domain", 4: "single-hop", 5: "adversarial"}

def conversation_to_text(conv):
    """Flatten a LoCoMo conversation into readable text."""
    a, b = conv["speaker_a"], conv["speaker_b"]
    lines = [f"Conversation between {a} and {b}.\n"]
    # sessions in order
    sess_keys = sorted([k for k in conv if k.startswith("session_") and not k.endswith("_date_time") and not k.endswith("_summary") and not k.endswith("_observation")],
                       key=lambda x: int(x.split("_")[1]))
    for sk in sess_keys:
        n = sk.split("_")[1]
        dt = conv.get(f"session_{n}_date_time", "")
        lines.append(f"\n## Session {n} ({dt})\n")
        turns = conv[sk]
        if isinstance(turns, dict):
            turns = turns.get("session_" + n, turns)
        for t in turns:
            sp = t.get("speaker", "?")
            txt = t.get("text", "")
            lines.append(f"{sp}: {txt}")
            cap = t.get("blip_caption")
            if cap:
                lines.append(f"  [image: {cap}]")
    return "\n".join(lines)

def main():
    src = Path(sys.argv[1])
    wiki_dir = Path(sys.argv[2])
    eval_yaml = Path(sys.argv[3])
    per_sample = int(sys.argv[4]) if len(sys.argv) > 4 else 0  # 0 = all

    data = json.load(open(src))
    wiki_dir.mkdir(parents=True, exist_ok=True)

    eval_entries = []
    for sample in data:
        sid = sample["sample_id"]
        slug = f"locomo-{sid}"
        # write wiki page
        body = conversation_to_text(sample["conversation"])
        wiki_path = wiki_dir / f"{slug}.md"
        if not wiki_path.exists():
            wiki_path.write_text(
                "---\n"
                f"title: LoCoMo conversation {sid}\n"
                "type: concept\n"
                "area: conversations\n"
                "status: active\n"
                "importance: 0.7\n"
                "confidence: 0.9\n"
                f"created: 2026-08-29T00:00:00+00:00\n"
                "tags: [locomo, long-conversation, benchmark]\n"
                "pinned: false\n"
                "archived: false\n"
                "access_count: 0\n"
                "---\n\n"
                f"{body}\n",
                encoding="utf-8",
            )

        # qa → eval entries
        qa_list = sample.get("qa", [])
        if per_sample > 0:
            qa_list = qa_list[:per_sample]
        for q in qa_list:
            cat = q.get("category", 0)
            if cat == 5:
                continue  # exclude adversarial (OpenViking protocol)
            eval_entries.append({
                "query": q["question"],
                "relevant": [slug],
                "topic_id": f"locomo-{CAT_NAMES.get(cat, 'unknown')}",
            })

    # write eval yaml (recall-case/v1 schema)
    eval_yaml.parent.mkdir(parents=True, exist_ok=True)
    with open(eval_yaml, "w", encoding="utf-8") as f:
        f.write("schema_version: recall-case/v1\n")
        f.write(f"dataset_id: locomo10\n")
        f.write("version: 1.0.0\n")
        f.write("description: LoCoMo long-conversation QA recall eval (10 conv, 1540 cases, excl. adversarial)\n")
        f.write("cases:\n")
        for i, e in enumerate(eval_entries, 1):
            q = e["query"].replace(chr(34), chr(39)).replace(chr(10), " ")
            f.write(f"- case_id: case-{i:04d}\n")
            f.write(f'  query: "{q}"\n')
            f.write(f'  relevant: {e["relevant"]}\n')
            f.write(f'  topic_id: {e["topic_id"]}\n')

    print(f"✅ {len(data)} conversations → wiki/{wiki_dir.name}/")
    print(f"✅ {len(eval_entries)} eval entries → {eval_yaml}")
    print(f"   categories: multi-hop/temporal/open-domain/single-hop (excl. adversarial)")

if __name__ == "__main__":
    main()
