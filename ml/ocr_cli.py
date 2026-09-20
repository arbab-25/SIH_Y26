#!/usr/bin/env python3
"""CODE MAZE — Standalone OCR CLI Tool per §3 & §5.
Usage:
    python ml/ocr_cli.py --image "path/to/label.jpg" [--json] [--no-blur-check]
"""

import argparse
import json
import sys
import os

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend to path to use application services
backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.services.ocr_service import run_ocr


def main():
    parser = argparse.ArgumentParser(description="CODE MAZE Legal Metrology OCR CLI")
    parser.add_argument("--image", "-i", required=True, help="Path to input product label image")
    parser.add_argument("--json", "-j", action="store_true", help="Output pure JSON format")
    parser.add_argument("--no-blur-check", action="store_true", help="Disable blur rejection heuristic")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Error: Image not found at '{args.image}'", file=sys.stderr)
        sys.exit(1)

    items, meta = run_ocr(args.image, detect_blur=not args.no_blur_check)

    if meta.get("blurry"):
        output = {
            "status": "BLUR_DETECTED",
            "message": meta.get("error"),
            "blur_score": meta.get("blur_score"),
            "items": []
        }
        print(json.dumps(output, indent=2))
        sys.exit(0)

    results = {
        "image": os.path.abspath(args.image),
        "total_detections": len(items),
        "average_confidence_pct": meta.get("avg_confidence"),
        "confidence_distribution": meta.get("confidence_distribution"),
        "words": [item.to_dict() for item in items]
    }

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"==================================================")
        print(f"CODE MAZE OCR CLI — Inspection Report")
        print(f"==================================================")
        print(f"File: {args.image}")
        print(f"Total Detections: {len(items)}")
        print(f"Average Confidence: {meta.get('avg_confidence')}%")
        print(f"--------------------------------------------------")
        for i, item in enumerate(items):
            conf_pct = item.confidence * 100 if item.confidence <= 1.0 else item.confidence
            print(f"[{i+1:02d}] {conf_pct:5.1f}% | {item.text}")
        print(f"==================================================")


if __name__ == "__main__":
    main()
