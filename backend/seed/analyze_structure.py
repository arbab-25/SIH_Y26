"""Analyze structure of raw_pages.json to map chapters, rules, schedules."""

import json
import re

with open("seed/raw_pages.json", encoding="utf-8") as f:
    pages = json.load(f)

for p in pages:
    txt = p["text"]
    lines = [line.strip() for line in txt.split("\n") if line.strip()]
    headers = []
    for line in lines:
        if re.match(r"^(CHAPTER\s+[IVXLCDM]+|THE\s+[A-Z]+\s+SCHEDULE|FIRST SCHEDULE|SECOND SCHEDULE|THIRD SCHEDULE|FOURTH SCHEDULE|FIFTH SCHEDULE|SIXTH SCHEDULE|SEVENTH SCHEDULE|\d+\.\s+[A-Z]|Rule\s+\d+)", line, re.IGNORECASE):
            headers.append(line)
    if headers:
        print(f"Page {p['page']}: {headers[:5]}")
