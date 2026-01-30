import json
import re
import unicodedata
from pathlib import Path

# ===== CONFIG =====
SOURCE_DIR = Path(r"C:\Users\44752\Desktop\Football\logos\Europe\England\Clubs\normal")
DEST_DIR = Path(r"C:\Users\44752\Desktop\Football\logos\Europe\England\Clubs\Clubs")
CLUBS_JSON = Path(r"C:\Users\44752\Desktop\Football\clubs.json")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".svg"}
# ==================

def sanitize(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", name).strip("_")

def strip_retro_suffix(stem: str) -> str:
    return re.sub(r"_retro\d*$", "", stem)

def load_club_names():
    data = json.loads(CLUBS_JSON.read_text(encoding="utf-8"))
    return {sanitize(club["name"]) for club in data}

def generate_unique_filename(dest_dir, base_name, ext):
    count = 0
    while True:
        suffix = f"_{count}" if count > 0 else ""
        candidate = dest_dir / f"{base_name}{suffix}{ext}"
        if not candidate.exists():
            return candidate
        count += 1

def main():
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    ingame_club_keys = load_club_names()

    moved, skipped = 0, 0

    for file in SOURCE_DIR.iterdir():
        if file.suffix.lower() not in IMAGE_EXTS or not file.is_file():
            continue

        base_stem = sanitize(strip_retro_suffix(file.stem))

        if base_stem not in ingame_club_keys:
            skipped += 1
            continue

        dest_file = generate_unique_filename(DEST_DIR, base_stem + "_club", file.suffix)
        file.rename(dest_file)
        moved += 1
        print(f"[MOVED] {file.name} → {dest_file.name}")

    print("\n=== SUMMARY ===")
    print(f"Moved: {moved}")
    print(f"Skipped (no club match): {skipped}")

if __name__ == "__main__":
    main()
