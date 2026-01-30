import json
import re
import unicodedata
from pathlib import Path

# ================= CONFIG =================
CLUBS_JSON = Path(r"C:\Users\44752\Desktop\Football\clubs.json")
LOGO_ROOT = Path(r"C:\Users\44752\Desktop\Football\club_logos_by_league")

IMAGE_EXTS = {".png", ".svg"}

STOPWORDS = {
    "fc", "f", "c", "afc", "the",
    "city", "town", "united", "utd",
    "football", "club"
}
# =========================================

def normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text.strip("_")

def tokens(text: str):
    return [
        t for t in normalise(text).split("_")
        if t and t not in STOPWORDS
    ]

# ---------- load all logos ----------
logos = []

for league_dir in LOGO_ROOT.iterdir():
    if not league_dir.is_dir():
        continue

    league = league_dir.name

    for file in league_dir.iterdir():
        if file.suffix.lower() in IMAGE_EXTS:
            logos.append({
                "league": league,
                "path": f"club_logos_by_league/{league}/{file.name}",
                "stem": normalise(file.stem),
                "tokens": set(tokens(file.stem))
            })

print(f"Loaded {len(logos)} logos")

# ---------- load clubs ----------
clubs = json.loads(CLUBS_JSON.read_text(encoding="utf-8"))

matched = 0
missing = 0

for club in clubs:
    name = club.get("name")
    league = club.get("league")

    if not name or not league:
        continue

    club_norm = normalise(name)
    club_tokens = set(tokens(name))

    best = None
    best_score = 0

    # 1. exact match
    for logo in logos:
        if logo["league"] == league and logo["stem"] == club_norm:
            best = logo
            break

    # 2. containment
    if not best:
        for logo in logos:
            if logo["league"] == league and club_norm in logo["stem"]:
                best = logo
                break

    # 3. base-name containment
    if not best:
        base = "_".join(tokens(name))
        for logo in logos:
            if logo["league"] == league and base and base in logo["stem"]:
                best = logo
                break

    # 4. token overlap scoring
    if not best:
        for logo in logos:
            if logo["league"] != league:
                continue
            score = len(club_tokens & logo["tokens"])
            if score > best_score:
                best_score = score
                best = logo

        if best_score < 1:
            best = None

    if best:
        club["logo"] = best["path"]
        matched += 1
        print(f"[OK] {name} -> {best['path']}")
    else:
        missing += 1
        print(f"[MISS] {name}")

# ---------- write back ----------
CLUBS_JSON.write_text(
    json.dumps(clubs, indent=2),
    encoding="utf-8"
)

print("\n=== SUMMARY ===")
print(f"Logos added: {matched}")
print(f"Still missing: {missing}")
