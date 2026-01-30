import pdfplumber
import re
from pathlib import Path

PDF_PATH = Path(r"FM2024 Unique IDs - Clubs.pdf")
OUTPUT_PATH = Path("club_id_map.txt")

# COUNTRY + ID + NAME (name may contain spaces)
LINE_RE = re.compile(r"^[A-Z]{3}\s+(\d+)\s+(.+)$")

rows = []

with pdfplumber.open(PDF_PATH) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if not text:
            continue

        for line in text.splitlines():
            line = line.strip()
            match = LINE_RE.match(line)
            if not match:
                continue

            club_id, club_name = match.groups()

            # Skip headers / junk
            if club_name.lower().endswith("clubs"):
                continue

            rows.append(f"{club_id}|{club_name}")

# Deduplicate, preserve order
rows = list(dict.fromkeys(rows))

OUTPUT_PATH.write_text("\n".join(rows), encoding="utf-8")

print(f"Extracted {len(rows)} club ID → name mappings")
