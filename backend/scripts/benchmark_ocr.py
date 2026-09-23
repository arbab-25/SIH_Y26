#!/usr/bin/env python3
"""OCR field-extraction benchmark — prints precision / recall you can quote.

Measures the FULL extraction pipeline (OCR + deterministic field extractors)
against the labeled sample set in tests/benchdata/, per the protocol committed
in docs/EVALUATION.md:

- true positive  — extractor found the field and the value fuzzy-matches
                   ground truth (RapidFuzz ratio >= 80, exact for numbers)
- false positive — extractor returned a value where ground truth is null, or
                   the value mismatches
- false negative — ground truth has the declaration but the extractor found
                   nothing

Run from backend/:

    python tests/benchdata/make_samples.py        # once, to render images
    python scripts/benchmark_ocr.py               # prints per-field P/R + macro

The seed set is synthetic (rendered text, one skewed sample); it measures the
extraction pipeline, NOT legal accuracy, and is labelled as such. Replace it
with real label photographs as they are collected (labels.json schema).
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)  # scripts/ sits directly under backend/
BENCHDATA = os.path.join(BACKEND_ROOT, "tests", "benchdata")

sys.path.insert(0, BACKEND_ROOT)

from rapidfuzz import fuzz  # noqa: E402


def _normalize_number(value):
    try:
        return round(float(str(value).strip().rstrip(".,").replace("₹", "").replace("Rs.", "")), 2)
    except (TypeError, ValueError):
        return None


def _value_matches(predicted, expected, field_key):
    """Field-aware comparison: exact for numerics, fuzzy for prose."""
    if predicted is None:
        return False
    p = str(predicted).strip()
    e = str(expected).strip()
    if not p or not e:
        return False
    if field_key in ("mrp", "net_quantity_value"):
        return _normalize_number(p) == _normalize_number(e)
    if field_key == "net_quantity":
        # "100 g" — compare number and unit separately
        p_parts = p.split()
        e_parts = e.split()
        if not p_parts or not e_parts:
            return False
        if _normalize_number(p_parts[0]) != _normalize_number(e_parts[0]):
            return False
        if len(e_parts) > 1 and len(p_parts) > 1:
            return p_parts[1].lower().lstrip(".") == e_parts[1].lower().lstrip(".")
        return True
    return fuzz.ratio(p.lower(), e.lower()) >= 80


# Extractor key -> benchmark field key. net_quantity maps from the value+unit
# pair the extractor returns.
_EXTRACTOR_KEYS = {
    "net_quantity": ("net_quantity_value", "net_quantity_unit"),
    "mrp": ("mrp",),
    "mfg_date": ("mfg_date_str",),
    "manufacturer_name": ("manufacturer_name",),
    "country_of_origin": ("country_of_origin",),
    "fssai_number": ("fssai_number",),
}


def evaluate_sample(extracted_dict, ground_truth_fields):
    """Count TP/FP/FN for one sample. Returns {field: {tp, fp, fn}}."""
    counts = {}
    for field, expected in ground_truth_fields.items():
        keys = _EXTRACTOR_KEYS.get(field)
        if not keys:
            continue
        c = counts.setdefault(field, {"tp": 0, "fp": 0, "fn": 0})
        if expected is None:
            # Ground truth says the declaration is absent: any confident value
            # the extractor returns is a false positive.
            value_present = any(extracted_dict.get(k, {}).get("value") for k in keys)
            if value_present:
                c["fp"] += 1
            continue
        predicted_value = extracted_dict.get(keys[0], {}).get("value")
        if field == "net_quantity":
            unit = extracted_dict.get("net_quantity_unit", {}).get("value") or ""
            predicted_value = f"{predicted_value} {unit}".strip() if predicted_value is not None else None
        if _value_matches(predicted_value, expected, field):
            c["tp"] += 1
        elif predicted_value:
            c["fp"] += 1
        else:
            c["fn"] += 1
    return counts


def precision_recall_for_field(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return round(precision, 3), round(recall, 3)


def aggregate_report(per_field_counts):
    """Build the printable report with per-field and macro P/R."""
    report = {"fields": {}, "macro": {}}
    precisions, recalls = [], []
    for field, c in per_field_counts.items():
        p, r = precision_recall_for_field(c["tp"], c["fp"], c["fn"])
        report["fields"][field] = {
            "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
            "precision": p, "recall": r,
        }
        precisions.append(p)
        recalls.append(r)
    report["macro"] = {
        "precision": round(sum(precisions) / len(precisions), 3) if precisions else 0.0,
        "recall": round(sum(recalls) / len(recalls), 3) if recalls else 0.0,
    }
    return report


def main():
    dataset_path = os.path.join(BENCHDATA, "labels.json")
    if not os.path.exists(dataset_path):
        print(f"Dataset not found: {dataset_path}", file=sys.stderr)
        sys.exit(1)
    with open(dataset_path, encoding="utf-8") as f:
        dataset = json.load(f)

    # Render synthetic samples if missing (keeps the repo free of binaries).
    missing = [
        s["image"] for s in dataset["samples"]
        if not os.path.exists(os.path.join(BENCHDATA, s["image"]))
    ]
    if missing:
        print(f"[INFO] Rendering {len(missing)} missing sample image(s)...")
        from tests.benchdata.make_samples import main as render_main
        render_main()

    from app.services.ocr_service import run_ocr
    from app.services.field_extractors import extract_fields_from_ocr

    total_counts = {}
    total_words = 0
    total_conf = 0.0

    for sample in dataset["samples"]:
        image_path = os.path.join(BENCHDATA, sample["image"])
        items, meta = run_ocr(image_path, detect_blur=False)
        extracted = extract_fields_from_ocr(items)
        counts = evaluate_sample(extracted.to_dict(), sample["fields"])
        for field, c in counts.items():
            agg = total_counts.setdefault(field, {"tp": 0, "fp": 0, "fn": 0})
            for k in ("tp", "fp", "fn"):
                agg[k] += c[k]
        total_words += len(items)
        total_conf += meta.get("avg_confidence", 0.0) * len(items)
        print(f"--- {sample['image']}: {len(items)} words, avg conf {meta.get('avg_confidence')}%")

    report = aggregate_report(total_counts)
    report["words_read"] = total_words
    report["avg_word_confidence_pct"] = (
        round(total_conf / total_words, 2) if total_words else 0.0
    )
    report["dataset"] = dataset.get("name")
    report["n_samples"] = len(dataset["samples"])

    print("\n================ OCR FIELD-EXTRACTION BENCHMARK ================")
    print(f"Dataset: {report['dataset']} ({report['n_samples']} samples, "
          f"{total_words} words, avg word conf {report['avg_word_confidence_pct']}%)")
    print(f"{'field':<22}{'P':>8}{'R':>8}{'TP':>5}{'FP':>5}{'FN':>5}")
    for field, c in report["fields"].items():
        print(f"{field:<22}{c['precision']:>8.3f}{c['recall']:>8.3f}"
              f"{c['tp']:>5}{c['fp']:>5}{c['fn']:>5}")
    m = report["macro"]
    print("-" * 53)
    print(f"{'MACRO AVG':<22}{m['precision']:>8.3f}{m['recall']:>8.3f}")
    print("Synthetic seed set: measures the extraction pipeline only — "
          "not legal accuracy. See docs/EVALUATION.md for the real-photo protocol.")

    out_path = os.path.join(BENCHDATA, "latest_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to {out_path}")


if __name__ == "__main__":
    main()
