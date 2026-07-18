"""Create a derived Watch payload with an explicit transcript candidate.

The primary Watch result remains unchanged. This helper is only for packaging
an independently produced, timestamped candidate through the same Raw adapter.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("watch_result", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = json.loads(args.watch_result.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    segments = [
        {
            "start": float(item["start"]),
            "end": float(item["end"]),
            "text": str(item["text"]),
        }
        for item in candidate.get("segments", [])
        if str(item.get("text", "")).strip()
    ]
    payload["primary_transcript"] = payload.get("transcript")
    payload["transcript"] = {
        "source": candidate.get("candidate", "external-candidate"),
        "segments": segments,
    }
    payload["transcript_candidate_manifest"] = {
        "schema_version": candidate.get("schema_version"),
        "configuration": candidate.get("configuration"),
        "elapsed_seconds": candidate.get("elapsed_seconds"),
        "observation_count": candidate.get("observation_count"),
        "segment_count": len(segments),
        "selection_policy": "explicit-experiment-candidate",
    }

    frame_root = args.frames.expanduser().resolve()
    for frame in payload.get("perception", {}).get("frames", []):
        index = int(frame.get("index", 0))
        resolved = frame_root / f"frame-{index:04d}.jpg"
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        frame["path"] = str(resolved)

    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
