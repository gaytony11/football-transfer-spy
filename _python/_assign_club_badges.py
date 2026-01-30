import re
import unicodedata
from pathlib import Path

# ================= CONFIG =================
LOGO_DIR = Path(
    r"C:\Users\44752\Desktop\Football\FMG Logos 2026.00\Clubs\Retro"
)

ID_MAP_FILE = Path(
    r"C:\Users\44752\Desktop\Football\club_id_map.txt"
)

IMAGE_EXTS = {".png", ".svg", ".jpg"}
# =========================================


def safe_name(text: str) -> str:
    """
    Make filesystem-safe lowercase name.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def load_id_map():
    """
    Expects lines like:
    625|Arsenal
    """
    mapping = {}
    for line in ID_MAP_FILE.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        cid, name = line.split("|", 1)
        mapping[cid.strip()] = safe_name(name.strip())
    return mapping


def extract_id(filename: str):
    """
    Extract leading numeric club ID.
    """
    m = re.match(r"^(\d+)", filename)
    return m.group(1) if m else None


def main():
    id_map = load_id_map()

    # Group files by club ID
    files_by_id = {}

    for file in LOGO_DIR.iterdir():
        if file.suffix.lower() not in IMAGE_EXTS:
            continue

        cid = extract_id(file.name)
        if not cid or cid not in id_map:
            print(f"[SKIP] {file.name}")
            continue

        files_by_id.setdefault(cid, []).append(file)

    # Rename
    for cid, files in files_by_id.items():
        club_name = id_map[cid]

        # Sort for stable numbering
        files.sort(key=lambda f: f.name)

        for idx, file in enumerate(files, start=1):
            if len(files) == 1:
                new_name = f"{club_name}_retro{file.suffix}"
            else:
                new_name = f"{club_name}_retro{idx}{file.suffix}"

            new_path = file.with_name(new_name)

            if new_path.exists():
                print(f"[COLLISION] {new_name} already exists — skipping")
                continue

            file.rename(new_path)
            print(f"[RENAMED] {file.name} -> {new_name}")

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
