#!/usr/bin/env python3
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List, Dict
from urllib.parse import urljoin, unquote

import requests
from bs4 import BeautifulSoup

OUT_FILE = Path("clubs.json")

HEADERS = {
    "User-Agent": "FootballStadiumClubScraper/2.0 (local script)"
}
WIKI = "https://en.wikipedia.org"

# -----------------------------
# Leagues to scrape (edit later)
# -----------------------------
LEAGUES = [
    # England
    ("Premier League", "ENG", "PL", 1, "https://en.wikipedia.org/wiki/2024%E2%80%9325_Premier_League"),
    ("EFL Championship", "ENG", "CH", 2, "https://en.wikipedia.org/wiki/2024%E2%80%9325_EFL_Championship"),
    ("EFL League One", "ENG", "L1", 3, "https://en.wikipedia.org/wiki/2024%E2%80%9325_EFL_League_One"),
    ("EFL League Two", "ENG", "L2", 4, "https://en.wikipedia.org/wiki/2024%E2%80%9325_EFL_League_Two"),
    ("National League", "ENG", "NL", 5, "https://en.wikipedia.org/wiki/2024%E2%80%9325_National_League"),

    # Scotland
    ("Scottish Premiership", "SCO", "SP", 1, "https://en.wikipedia.org/wiki/2024%E2%80%9325_Scottish_Premiership"),
    ("Scottish Championship", "SCO", "SC", 2, "https://en.wikipedia.org/wiki/2024%E2%80%9325_Scottish_Championship"),
    ("Scottish League One", "SCO", "SL1", 3, "https://en.wikipedia.org/wiki/2024%E2%80%9325_Scottish_League_One"),
    ("Scottish League Two", "SCO", "SL2", 4, "https://en.wikipedia.org/wiki/2024%E2%80%9325_Scottish_League_Two"),

    # Wales
    ("Cymru Premier", "WAL", "CP", 1, "https://en.wikipedia.org/wiki/2024%E2%80%9325_Cymru_Premier"),

    # Ireland
    ("LOI Premier Division", "IRL", "PD", 1, "https://en.wikipedia.org/wiki/2024_League_of_Ireland_Premier_Division"),
    ("LOI First Division", "IRL", "FD", 2, "https://en.wikipedia.org/wiki/2024_League_of_Ireland_First_Division"),

    # Northern Ireland
    ("NIFL Premiership", "NIR", "NIP", 1, "https://en.wikipedia.org/wiki/2024%E2%80%9325_NIFL_Premiership"),
]

# If you want “Conference North/South” later, we can add them once you confirm which season pages you want.


# -----------------------------
# Helpers
# -----------------------------
def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"\s*\(.*?\)\s*", " ", s)  # remove bracketed bits
    s = s.replace("’", "'")
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s

def build_aliases(name: str) -> List[str]:
    base = name.lower().replace(".", "")
    aliases = {base}

    # common trims
    aliases.add(base.replace(" football club", "").strip())
    aliases.add(base.replace(" f.c.", "").replace(" fc", "").strip())

    # initialism
    words = re.findall(r"[a-z0-9]+", base)
    if len(words) >= 2:
        aliases.add("".join(w[0] for w in words))

    # common variants
    aliases.add(base.replace("&", "and"))

    # remove duplicates / empties
    aliases = {a.strip() for a in aliases if a.strip()}
    return sorted(aliases)

def http_get(url: str, timeout: int = 30) -> str:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.text

def normalize_wiki_href(href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(WIKI, href)

def is_wiki_article_link(href: str) -> bool:
    # Only accept /wiki/... links (not redlinks, not files)
    if not href:
        return False
    if not href.startswith("/wiki/"):
        return False
    if "redlink=1" in href:
        return False
    if href.startswith("/wiki/File:") or href.startswith("/wiki/Help:") or href.startswith("/wiki/Special:"):
        return False
    return True


# -----------------------------
# Stage 1: Extract club links from league page
# -----------------------------
def scrape_club_links_from_league(league_url: str) -> List[Tuple[str, str]]:
    """
    Robust approach:
    - Find all tables that look like standings (contain 'Pos' and 'Team' or 'Club')
    - Extract the "Team/Club" column links
    - De-duplicate
    """
    html = http_get(league_url)
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table", class_=lambda c: c and "wikitable" in c)
    candidates: List[Tuple[str, str]] = []

    for table in tables:
        headers = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
        header_text = " ".join(headers)

        # Heuristics: standings tables usually contain Pos and either Team/Club
        if ("pos" not in header_text) or (("team" not in header_text) and ("club" not in header_text)):
            continue

        # Find index of team/club column
        header_row = table.find("tr")
        if not header_row:
            continue

        ths = header_row.find_all(["th", "td"])
        col_names = [th.get_text(" ", strip=True).lower() for th in ths]

        team_idx = None
        for i, name in enumerate(col_names):
            if name in ("team", "club") or "team" in name or "club" in name:
                team_idx = i
                break
        if team_idx is None:
            continue

        # Extract rows
        for tr in table.find_all("tr")[1:]:
            tds = tr.find_all(["th", "td"])
            if len(tds) <= team_idx:
                continue

            cell = tds[team_idx]
            a = cell.find("a", href=True)
            if not a:
                continue

            href = a["href"]
            if not is_wiki_article_link(href):
                continue

            name = a.get_text(" ", strip=True)
            if not name:
                continue

            candidates.append((name, normalize_wiki_href(href)))

    # De-dupe by URL
    seen = set()
    out = []
    for name, url in candidates:
        if url in seen:
            continue
        seen.add(url)
        out.append((name, url))

    return out


# -----------------------------
# Stage 2: For each club page, find home ground page link
# -----------------------------
def find_home_ground_link(club_url: str) -> Optional[Tuple[str, str]]:
    """
    In the club's infobox, find row labeled 'Ground' or 'Home ground'.
    Return (ground_name, ground_url).
    """
    html = http_get(club_url)
    soup = BeautifulSoup(html, "html.parser")

    infobox = soup.find("table", class_=lambda c: c and "infobox" in c)
    if not infobox:
        return None

    # look for "Ground" / "Home ground"
    for tr in infobox.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if not th or not td:
            continue
        label = th.get_text(" ", strip=True).lower()
        if label in ("ground", "home ground", "stadium"):
            a = td.find("a", href=True)
            if a and is_wiki_article_link(a["href"]):
                ground_name = a.get_text(" ", strip=True)
                ground_url = normalize_wiki_href(a["href"])
                return (ground_name, ground_url)

            # If no link, we still might parse plain text, but coords would be hard.
            text = td.get_text(" ", strip=True)
            if text:
                return (text, None)

    return None


# -----------------------------
# Stage 3: Extract coords from stadium page
# -----------------------------
def extract_coords_from_wiki_page(url: str) -> Optional[Tuple[float, float]]:
    """
    Prefer coordinates in the page header (#coordinates or span.geo).
    """
    if not url:
        return None

    html = http_get(url)
    soup = BeautifulSoup(html, "html.parser")

    # The most reliable is span.geo (lat; lon)
    geo = soup.find("span", class_="geo")
    if geo:
        try:
            lat_str, lon_str = [x.strip() for x in geo.get_text(strip=True).split(";")]
            return float(lat_str), float(lon_str)
        except Exception:
            pass

    # Fallback: look for geo-dec spans used sometimes
    geo_dec = soup.find("span", class_="geo-dec")
    if geo_dec:
        # geo-dec is like "51.507°N 0.127°W"
        txt = geo_dec.get_text(" ", strip=True)
        # crude parse is not worth it; skip for simplicity
        return None

    return None


# -----------------------------
# Main
# -----------------------------
def main():
    all_clubs: Dict[str, dict] = {}

    for league_name, country, code, tier, league_url in LEAGUES:
        print(f"\nScraping {league_name}")
        club_links = scrape_club_links_from_league(league_url)

        if not club_links:
            print("  !! No clubs found on this league page (table structure changed).")
            continue

        print(f"  Found {len(club_links)} club links")

        for club_name, club_url in club_links:
            club_id = slugify(club_name)

            try:
                ground = find_home_ground_link(club_url)
                if not ground:
                    print(f"  ✗ {club_name} (no ground found)")
                    continue

                ground_name, ground_url = ground

                coords = extract_coords_from_wiki_page(ground_url) if ground_url else None
                if not coords:
                    print(f"  ✗ {club_name} (no coords for ground: {ground_name})")
                    continue

                lat, lon = coords

                all_clubs[club_id] = {
                    "id": club_id,
                    "name": club_name,
                    "country": country,
                    "league": code,
                    "tier": tier,
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "ground": ground_name,
                    "aliases": build_aliases(club_name),
                    "wikipedia": club_url,
                    "ground_wikipedia": ground_url,
                }

                print(f"  ✓ {club_name}  ->  {ground_name}")
                time.sleep(0.35)  # be polite to Wikipedia

            except requests.HTTPError as e:
                print(f"  ✗ {club_name} (HTTP error: {e})")
            except Exception as e:
                print(f"  ✗ {club_name} (error: {e})")

    final = sorted(all_clubs.values(), key=lambda c: (c["country"], c["tier"], c["name"]))

    OUT_FILE.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWritten {len(final)} clubs to {OUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
