"""Compare existing scene-change strategies without running the full Raw pipeline.

The probe only records detector boundaries and timings. It neither extracts
frames nor changes production defaults, which keeps the experiment cheap and
repeatable on long local videos.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.raw_bundle_adapter import (
    _adaptive_scene_detector,
    _screen_change_scenes,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=float)
    parser.add_argument("--end", type=float)
    parser.add_argument("--screen-threshold", type=float, default=8.0)
    parser.add_argument("--sample-seconds", type=float, default=1.0)
    return parser.parse_args()


def timed(callable_):
    started = time.perf_counter()
    result = callable_()
    return result, round(time.perf_counter() - started, 3)


def main() -> int:
    args = parse_args()
    source = args.input.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    adaptive, adaptive_seconds = timed(
        lambda: _adaptive_scene_detector(source, args.start, args.end)
    )
    screen, screen_seconds = timed(
        lambda: _screen_change_scenes(
            source,
            args.start,
            args.end,
            threshold=args.screen_threshold,
            sample_seconds=args.sample_seconds,
            roi=None,
        )
    )

    payload = {
        "schema_version": "raw-component-experiment/v0.1",
        "candidate": "keyframe-routing",
        "input": str(source),
        "range": {"start": args.start, "end": args.end},
        "strategies": {
            "adaptive_scene_detector": {
                "timing_seconds": adaptive_seconds,
                "scene_count": len(adaptive),
                "scenes": adaptive,
            },
            "screen_change_detector": {
                "configuration": {
                    "threshold": args.screen_threshold,
                    "sample_seconds": args.sample_seconds,
                },
                "timing_seconds": screen_seconds,
                "scene_count": len(screen),
                "scenes": screen,
            },
        },
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
