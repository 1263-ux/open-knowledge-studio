"""Extract a timestamped transcript candidate from burned-in video subtitles.

This is an experiment adapter for cases where an upstream ASR route returns no
segments. It samples a user-specified subtitle region, delegates OCR to
RapidOCR, and preserves every retained observation with its source timestamp.
It does not summarize or silently replace the primary transcript.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--roi", required=True, help="x1,y1,x2,y2 in source pixels")
    parser.add_argument("--sample-seconds", type=float, default=0.5)
    parser.add_argument("--min-confidence", type=float, default=0.75)
    return parser.parse_args()


def parse_roi(value: str) -> tuple[int, int, int, int]:
    values = tuple(int(item.strip()) for item in value.split(","))
    if len(values) != 4:
        raise ValueError("ROI must be x1,y1,x2,y2")
    x1, y1, x2, y2 = values
    if min(values) < 0 or x2 <= x1 or y2 <= y1:
        raise ValueError("ROI must satisfy 0 <= x1 < x2 and 0 <= y1 < y2")
    return values


def normalized(value: str) -> str:
    return re.sub(r"[\s，。！？、,.!?;；:：]+", "", value).lower()


def main() -> int:
    args = parse_args()
    source = args.input.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    if args.sample_seconds <= 0:
        raise ValueError("sample interval must be positive")

    import cv2
    from rapidocr import RapidOCR

    x1, y1, x2, y2 = parse_roi(args.roi)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = frame_count / fps if frame_count else 0.0
    engine = RapidOCR()
    observations: list[dict] = []
    started = time.perf_counter()
    second = 0.0
    try:
        while second <= duration:
            capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000.0)
            ok, frame = capture.read()
            if not ok:
                second += args.sample_seconds
                continue
            height, width = frame.shape[:2]
            crop = frame[min(y1, height):min(y2, height), min(x1, width):min(x2, width)]
            if crop.size == 0:
                raise ValueError(f"ROI {(x1, y1, x2, y2)} outside video {width}x{height}")
            result = engine(crop)
            raw_texts = getattr(result, "txts", None)
            raw_boxes = getattr(result, "boxes", None)
            raw_scores = getattr(result, "scores", None)
            texts = list(raw_texts) if raw_texts is not None else []
            boxes = list(raw_boxes) if raw_boxes is not None else []
            scores = list(raw_scores) if raw_scores is not None else []
            rows = []
            for text, box, score in zip(texts, boxes, scores):
                confidence = float(score)
                value = str(text).strip()
                if not value or confidence < args.min_confidence:
                    continue
                points = box.tolist() if hasattr(box, "tolist") else list(box)
                rows.append((min(float(p[1]) for p in points), min(float(p[0]) for p in points), value, confidence))
            rows.sort(key=lambda item: (item[0], item[1]))
            text = " ".join(item[2] for item in rows).strip()
            if text:
                observations.append(
                    {
                        "timestamp": round(second, 3),
                        "text": text,
                        "confidence": round(min(item[3] for item in rows), 4),
                    }
                )
            second += args.sample_seconds
    finally:
        capture.release()

    segments: list[dict] = []
    for item in observations:
        key = normalized(item["text"])
        if segments and key == segments[-1]["normalized_text"]:
            segments[-1]["end"] = round(item["timestamp"] + args.sample_seconds, 3)
            segments[-1]["observation_count"] += 1
            segments[-1]["confidence"] = min(segments[-1]["confidence"], item["confidence"])
            continue
        segments.append(
            {
                "start": item["timestamp"],
                "end": round(item["timestamp"] + args.sample_seconds, 3),
                "text": item["text"],
                "normalized_text": key,
                "confidence": item["confidence"],
                "observation_count": 1,
            }
        )

    payload = {
        "schema_version": "raw-component-experiment/v0.1",
        "candidate": "burned-subtitle-rapidocr",
        "input": str(source),
        "configuration": {
            "roi": [x1, y1, x2, y2],
            "sample_seconds": args.sample_seconds,
            "minimum_confidence": args.min_confidence,
        },
        "duration_seconds": duration,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "observation_count": len(observations),
        "segment_count": len(segments),
        "segments": segments,
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
