import json
import re
import unicodedata
from pathlib import Path

# ================= CONFIG =================
SOURCE_DIR = Path(
    r"C:\Users\44752\Desktop\Football\FMG Logos 2026.00\Clubs\Normal"
)

DEST_DIR = Path(
    r"C:\Users\44752\Desktop\Football\FMG Logos 2026.00\normal"
)

ID_MAP_FILE = Path(
    r"C:\Users\44752\Desktop\Football\club_id_map.txt"
)

CLUBS_JSON = Path(
    r"C:\Users\44752\Desktop\Football\clubs.json"
)

IMAGE_EXTS = {".png", ".svg", ".jpg"}
# =========================================


def safe_name(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def extract_leading_id(filename: str):
    """Extract leading numeric ID if present."""
    m = re.match(r"^(\d+)", filename)
    return m.group(1) if m else None


def strip_retro_suffix(name: str):
    """
    Removes _retro, _retro1, _retro2 etc.
    """
    return re.sub(r"_retro\d*$", "", name)


def load_id_map():
    mapping = {}
    for line in ID_MAP_FILE.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        cid, name = line.split("|", 1)
        mapping[cid.strip()] = safe_name(name.strip())
    return mapping


def load_ingame_clubs():
    data = json.loads(CLUBS_JSON.read_text(encoding="utf-8"))
    return {safe_name(c["name"]) for c in data}


def main():
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    id_map = load_id_map()
    ingame_clubs = load_ingame_clubs()

    moved = 0
    skipped = 0

    for file in SOURCE_DIR.iterdir():
        if file.suffix.lower() not in IMAGE_EXTS:
            continue

        stem = file.stem
        club_key = None

        # CASE 1: numeric ID filenames
        cid = extract_leading_id(stem)
        if cid and cid in id_map:
            club_key = id_map[cid]

        # CASE 2: already renamed filenames
        if not club_key:
            cleaned = strip_retro_suffix(safe_name(stem))
            if cleaned in ingame_clubs:
                club_key = cleaned

        if not club_key:
            print(f"[SKIP] {file.name} (no in-game match)")
            skipped += 1
            continue

        dest_path = DEST_DIR / file.name

        if dest_path.exists():
            print(f"[COLLISION] {dest_path.name} exists — skipping")
            skipped += 1
            continue

        file.rename(dest_path)
        print(f"[MOVED] {file.name}")
        moved += 1

    print("\n=== SUMMARY ===")
    print(f"Moved: {moved}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
