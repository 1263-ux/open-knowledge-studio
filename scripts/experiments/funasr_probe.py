"""Run a reproducible FunASR candidate extraction without touching Raw output.

This script is intentionally an experiment adapter.  It writes the upstream
result verbatim enough for side-by-side evaluation and does not select or
rewrite the production transcript.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="paraformer-zh")
    parser.add_argument("--vad-model", default="fsmn-vad")
    parser.add_argument("--punc-model", default="ct-punc")
    parser.add_argument("--hotwords", default="")
    parser.add_argument("--device", default="cpu")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.input.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    from funasr import AutoModel

    started = time.perf_counter()
    model = AutoModel(
        model=args.model,
        vad_model=args.vad_model,
        punc_model=args.punc_model,
        device=args.device,
        disable_update=True,
    )
    loaded_seconds = time.perf_counter() - started
    inference_started = time.perf_counter()
    result = model.generate(
        input=str(source),
        hotword=args.hotwords or None,
        batch_size_s=300,
    )
    inference_seconds = time.perf_counter() - inference_started

    payload = {
        "schema_version": "raw-component-experiment/v0.1",
        "candidate": "funasr",
        "input": str(source),
        "configuration": {
            "model": args.model,
            "vad_model": args.vad_model,
            "punc_model": args.punc_model,
            "hotwords": args.hotwords.split() if args.hotwords else [],
            "device": args.device,
        },
        "timing": {
            "model_load_seconds": round(loaded_seconds, 3),
            "inference_seconds": round(inference_seconds, 3),
        },
        "upstream_result": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
