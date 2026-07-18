"""Run PP-StructureV3 as a side-by-side layout/OCR experiment."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lang", default="ch")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output.mkdir(parents=True, exist_ok=True)

    from paddleocr import PPStructureV3

    started = time.perf_counter()
    pipeline = PPStructureV3(
        lang=args.lang,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        use_seal_recognition=False,
        use_table_recognition=False,
        use_formula_recognition=False,
        use_chart_recognition=False,
        use_region_detection=False,
    )
    loaded_seconds = time.perf_counter() - started
    inference_started = time.perf_counter()
    results = list(pipeline.predict(str(source)))
    inference_seconds = time.perf_counter() - inference_started

    for result in results:
        result.save_to_json(str(output))
        result.save_to_markdown(str(output))

    manifest = {
        "schema_version": "raw-component-experiment/v0.1",
        "candidate": "pp-structure-v3",
        "input": str(source),
        "configuration": {
            "lang": args.lang,
            "document_orientation": False,
            "document_unwarping": False,
            "textline_orientation": False,
            "table": False,
            "formula": False,
            "chart": False,
            "seal": False,
        },
        "timing": {
            "model_load_seconds": round(loaded_seconds, 3),
            "inference_seconds": round(inference_seconds, 3),
        },
        "result_count": len(results),
    }
    (output / "experiment-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
