# CODE MAZE — Evaluation & Published OCR Baselines

This document separates three kinds of numbers, and never mixes them:

1. **Published (external)** — figures taken from official, public documentation of the OCR
   engines this project uses. Each carries a source URL. We do not re-measure them and we do
   not present them as our own results.
2. **Measured (this project)** — numbers produced by running CODE MAZE in a stated
   environment. Only measurements actually taken in this workspace appear here.
3. **Not yet measured** — metrics the specification asks for that require data or hardware
   we do not currently have. They are listed with the protocol that will produce them.

All accuracy claims about CODE MAZE come from the OCR engine's own word-level confidence
plus deterministic rule checks. No LLM participates in any verdict.

---

## 1. Published baselines (external, cited)

### 1.1 PaddleOCR / PP-OCR series

Source: PaddleOCR official repository documentation, `v2.7.0` tag
([README_en.md](https://github.com/PaddlePaddle/PaddleOCR/blob/v2.7.0/README_en.md),
[ppocr_introduction_en.md](https://github.com/PaddlePaddle/PaddleOCR/blob/v2.7.0/doc/doc_en/ppocr_introduction_en.md),
[models_list_en.md](https://github.com/PaddlePaddle/PaddleOCR/blob/v2.7.0/doc/doc_en/models_list_en.md)).
License: Apache-2.0 (license badge in the official README).

**Release notes for PP-OCRv4 (2023-08-07, quoted from the official README):**

> - PP-OCRv4-mobile：When the speed is comparable, the effect of the Chinese scene is improved
>   by 4.5% compared with PP-OCRv3, the English scene is improved by 10%, and the average
>   recognition accuracy of the 80-language multilingual model is increased by more than 8%.
> - PP-OCRv4-server：Release the OCR model with the highest accuracy at present, the detection
>   model accuracy increased by 4.9% in the Chinese and English scenes, and the recognition
>   model accuracy increased by 2%

**Model sizes (quoted from the official PP-OCR introduction):**

| PP-OCR series model | Total size | Detection | Direction classifier | Recognition |
| --- | --- | --- | --- | --- |
| PP-OCRv3 ultra-lightweight | 17.0M | 3.6M | 1.4M | 12M |
| PP-OCRv2 ultra-lightweight | 13.0M | 3.1M | 1.4M | 8.5M |
| PP-OCR mobile | 9.4M | 3.0M | 1.4M | 5.0M |
| PP-OCR server | 143.4M | 47.1M | 1.4M | 94.9M |

**Devanagari support (relevant to the Hindi requirement):** PaddleOCR publishes a dedicated
`devanagari_PP-OCRv3_rec` recognition model, 9.9M, listed in the official multilingual
recognition model table.

**Technical reports** (cited by the official docs):
PP-OCR — [arXiv:2009.09941](https://arxiv.org/abs/2009.09941);
PP-OCRv2 — [arXiv:2109.03144](https://arxiv.org/abs/2109.03144);
PP-OCRv3 — [arXiv:2206.03001](https://arxiv.org/abs/2206.03001).

**What this baseline means for CODE MAZE:** the project runs RapidOCR, which executes
PaddleOCR PP-OCR series models via ONNX Runtime. The published relative-improvement figures
above (v3 → v4 gains, English +10% for the mobile pipeline) are the manufacturers' own
comparisons and set the expected accuracy envelope for our engine choice. They are **not**
CODE MAZE measurements.

### 1.2 Tesseract 5

Source: official Tesseract documentation repository
([ReleaseNotes.md](https://github.com/tesseract-ocr/tessdoc/blob/main/ReleaseNotes.md),
[Benchmarks.md](https://github.com/tesseract-ocr/tessdoc/blob/main/Benchmarks.md),
[ChangeLog](https://github.com/tesseract-ocr/tesseract/blob/5.0.0/ChangeLog)).

**Version facts (quoted from the official ReleaseNotes/ChangeLog):**

- V4.0.0 (2018-10-29): "Added new neural network system based on LSTMs, with major accuracy
  gains."
- V5.0.0 (November 2021): "Faster training and recognition by default (float instead of
  double calculations)" and "More options for binarization".
- Current line: V5.5.3 (July 24, 2026) per the official ReleaseNotes index.

**Official benchmark table** (single image, average over 15 runs, Windows 10, VS 2019,
Intel Core i7-10750H @ 2.60 GHz, 6 cores; seconds per inference, from `tessdoc/Benchmarks.md`):

| Build | tessdata_best | tessdata_fast | tessdata (default) |
| --- | ---: | ---: | ---: |
| 3.05 (legacy engine) | — | — | 2.4713 |
| 4.1.3, no AVX | 37.6052 | 5.1589 | 10.1519 |
| 4.1.3, AVX2/AVX/SSE4 | 12.7300 | 2.9538 | 4.0860 |
| 5.0.1, AVX2 | 6.1981 | 2.1241 | 2.9107 |
| 5.0.1, AVX2 + OpenMP | 3.4590 | 1.9612 | 2.3554 |

Derived reading (arithmetic on the published table, not a new measurement): Tesseract
5.0.1 is ≈2× faster than 4.1.3-AVX and ≈6× faster than a 4.1.3 build without AVX on the
`tessdata_best` LSTM models, which is why CODE MAZE's fallback uses Tesseract 5, never 4.x.

**What this baseline means for CODE MAZE:** Tesseract 5 is the fallback engine when
RapidOCR/ONNX is unavailable. The published table justifies two operational choices: pinning
SIMD-capable builds, and preferring `tessdata_fast` when latency matters more than the last
few accuracy points.

---

## 2. Measured in this project (real runs, stated environment)

Measured with `assets/test 1.jpeg` (1200×1600 JPEG photograph of a real package); the figure
is the API's own `processing_time_ms` for upload-to-verdict. OCR engine: RapidOCR
(PP-OCR series models via ONNX Runtime), threads pinned to 4.

| Environment | Engine config | Processing time |
| --- | --- | --- |
| AMD EPYC 9254 sandbox, 48 vCPU | RapidOCR, ONNX Runtime threads = 4 | 6.7 s / 7.2 s / 8.6 s (three runs) |
| Same sandbox | ONNX Runtime default thread count | ≈75 s |

The 1 vCPU / 2 GB deployment target has **not** been benchmarked from this workspace, so no
figure is claimed for it. `docs/walkthrough.md` records the full run context (NEEDS_REVIEW
verdict at 57.14% compliance, 90.73% average word-level OCR confidence, 29.6 KB PDF
generated).

---

## 3. Not yet measured — protocol committed in advance

Per the project specification (§14), the following evaluation is defined now and will be
filled in only with real measurements:

**Held-out set.** A minimum of 50 real package-label photographs spanning the categories in
the scan UI (food, cosmetics, cement, paint, garment, other), each photographed once, with a
human-entered ground truth for every Rule 6(1) declaration (present/absent + correct value).

**Field-level precision / recall.** For each extracted field:

- `true positive` — extractor found the field and its value matches ground truth
  (fuzzy match ≥ 0.9 with RapidFuzz for text; exact for numeric/MRP/date after normalization).
- `false positive` — extractor returned a value where ground truth says the declaration is
  absent, or the value mismatches.
- `false negative` — ground truth has the declaration but the extractor returned nothing
  (or NEEDS_REVIEW with no value).

Precision = TP / (TP + FP); Recall = TP / (TP + FN). Reported per field and macro-averaged.

**Confusion matrix.** Over the three verdict states (COMPLIANT / NON_COMPLIANT / NEEDS_REVIEW),
using labels derived deterministically from ground truth + the rule engine applied to the
ground-truth values. The matrix answers the fail-closed question directly: how often a
truly non-compliant label was reported as NEEDS_REVIEW instead (acceptable), and how often a
compliant label was reported NON_COMPLIANT (unacceptable; investigate immediately).

**OCR confidence calibration.** Bin word-level confidences into the four pie-chart slices
(High ≥90, Medium 75–89, Low <75, Not detected) and compare against actual correctness per
bin. A bin is calibrated when the share of correctly-read words matches the bin's nominal
range; miscalibration >10 points would require re-tuning `OCR_CONFIDENCE_THRESHOLD`.

**Reporting rule.** No result enters this file or the README until the run has actually been
executed; no placeholder numbers are invented anywhere in this document.
