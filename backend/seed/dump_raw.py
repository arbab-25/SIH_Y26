"""Extract full text and analyze section headers across all pages of RULE BOOK.pdf."""

import pymupdf
import json

doc = pymupdf.open(r"d:\ARBAB\SIH DATA\RULE BOOK.pdf")
pages_text = []

for page_num in range(len(doc)):
    text = doc[page_num].get_text("text")
    pages_text.append({
        "page": page_num + 1,
        "text": text
    })

with open(r"d:\ARBAB\SIH DATA\codemaze\backend\seed\raw_pages.json", "w", encoding="utf-8") as f:
    json.dump(pages_text, f, indent=2, ensure_ascii=False)

print(f"Extracted {len(pages_text)} pages to raw_pages.json")
