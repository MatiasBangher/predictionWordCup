"""
FBref xG Stats Scraper for World Cup 2026.

Scrapes expected goals (xG) and advanced statistics from FBref.
Includes aggressive rate limiting (5s between requests) and comprehensive
fallback data for all 48 teams.

Data source: https://fbref.com/en/comps/1/World-Cup-Stats

WARNING: FBref has very strict rate limiting. This scraper is designed
to fail gracefully and use realistic fallback data when blocked.
"""

import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache configuration
# ---------------------------------------------------------------------------
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
XG_CACHE_FILE = CACHE_DIR / "xg_stats.json"
XG_CACHE_TTL_HOURS = 24  # Re-scrape every 24 hours

# Rate limiting
FBREF_REQUEST_DELAY_SECS = 5  # Minimum 5 seconds between requests
_last_request_time: float = 0.0

FBREF_BASE_URL = "https://fbref.com"
FBREF_WC_URL = f"{FBREF_BASE_URL}/en/comps/1/World-Cup-Stats"
FBREF_NATIONAL_TEAMS_URL = f"{FBREF_BASE_URL}/en/comps/1/stats/World-Cup-Stats"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.google.com/",
}

# ---------------------------------------------------------------------------
# Team name mapping: FBref English names -> Spanish names used in the app
# ---------------------------------------------------------------------------
FBREF_NAME_MAP: dict[str, str] = {
    "Argentina": "Argentina",
    "France": "Francia",
    "Spain": "España",
    "England": "Inglaterra",
    "Brazil": "Brasil",
    "Portugal": "Portugal",
    "Netherlands": "Países Bajos",
    "Germany": "Alemania",
    "Belgium": "Bélgica",
    "Colombia": "Colombia",
    "Uruguay": "Uruguay",
    "Croatia": "Croacia",
    "Japan": "Japón",
    "Morocco": "Marruecos",
    "Switzerland": "Suiza",
    "United States": "Estados Unidos",
    "USA": "Estados Unidos",
    "Mexico": "México",
    "Senegal": "Senegal",
    "Ecuador": "Ecuador",
    "Turkey": "Turquía",
    "Türkiye": "Turquía",
    "Austria": "Austria",
    "Korea Republic": "Corea del Sur",
    "South Korea": "Corea del Sur",
    "kr KOR": "Corea del Sur",
    "Australia": "Australia",
    "Norway": "Noruega",
    "Iran": "Irán",
    "IR Iran": "Irán",
    "Sweden": "Suecia",
    "Canada": "Canadá",
    "Egypt": "Egipto",
    "Algeria": "Argelia",
    "Scotland": "Escocia",
    "Paraguay": "Paraguay",
    "Ivory Coast": "Costa de Marfil",
    "Côte d'Ivoire": "Costa de Marfil",
    "Czech Republic": "República Checa",
    "Czechia": "República Checa",
    "Tunisia": "Túnez",
    "Ghana": "Ghana",
    "Panama": "Panamá",
    "Saudi Arabia": "Arabia Saudita",
    "Iraq": "Irak",
    "Uzbekistan": "Uzbekistán",
    "Bosnia and Herzegovina": "Bosnia y Herzegovina",
    "Bosnia-Herzegovina": "Bosnia y Herzegovina",
    "Jordan": "Jordania",
    "DR Congo": "Congo RD",
    "Congo DR": "Congo RD",
    "South Africa": "Sudáfrica",
    "Qatar": "Qatar",
    "New Zealand": "Nueva Zelanda",
    "Cape Verde": "Cabo Verde",
    "Cape Verde Islands": "Cabo Verde",
    "Haiti": "Haití",
    "Curaçao": "Curaçao",
    "Curacao": "Curaçao",
}

# ---------------------------------------------------------------------------
# Comprehensive fallback xG data for all 48 WC 2026 teams
# Based on recent competitive match performance (approximated)
# ---------------------------------------------------------------------------
FALLBACK_XG_STATS: dict[str, dict] = {
    # === TIER 1 — Elite ===
    "Argentina": {
        "xg_for": 2.15, "xg_against": 0.72, "xg_diff": 1.43,
        "npxg_for": 1.90, "goals_per90": 2.10, "shots_per90": 14.5,
        "shot_accuracy": 0.42, "possession": 58.5,
    },
    "Francia": {
        "xg_for": 1.95, "xg_against": 0.80, "xg_diff": 1.15,
        "npxg_for": 1.72, "goals_per90": 1.88, "shots_per90": 14.0,
        "shot_accuracy": 0.40, "possession": 57.0,
    },
    "España": {
        "xg_for": 2.05, "xg_against": 0.68, "xg_diff": 1.37,
        "npxg_for": 1.85, "goals_per90": 1.95, "shots_per90": 16.0,
        "shot_accuracy": 0.38, "possession": 65.5,
    },
    "Inglaterra": {
        "xg_for": 1.85, "xg_against": 0.75, "xg_diff": 1.10,
        "npxg_for": 1.60, "goals_per90": 1.78, "shots_per90": 13.8,
        "shot_accuracy": 0.39, "possession": 56.0,
    },
    "Brasil": {
        "xg_for": 1.90, "xg_against": 0.82, "xg_diff": 1.08,
        "npxg_for": 1.68, "goals_per90": 1.85, "shots_per90": 14.2,
        "shot_accuracy": 0.38, "possession": 58.0,
    },
    "Portugal": {
        "xg_for": 1.80, "xg_against": 0.70, "xg_diff": 1.10,
        "npxg_for": 1.55, "goals_per90": 1.82, "shots_per90": 13.5,
        "shot_accuracy": 0.40, "possession": 57.5,
    },
    "Países Bajos": {
        "xg_for": 1.85, "xg_against": 0.78, "xg_diff": 1.07,
        "npxg_for": 1.62, "goals_per90": 1.90, "shots_per90": 14.0,
        "shot_accuracy": 0.39, "possession": 58.0,
    },
    "Alemania": {
        "xg_for": 1.78, "xg_against": 0.95, "xg_diff": 0.83,
        "npxg_for": 1.55, "goals_per90": 1.80, "shots_per90": 15.0,
        "shot_accuracy": 0.37, "possession": 60.0,
    },
    # === TIER 2 — Very Strong ===
    "Bélgica": {
        "xg_for": 1.65, "xg_against": 0.85, "xg_diff": 0.80,
        "npxg_for": 1.45, "goals_per90": 1.68, "shots_per90": 13.0,
        "shot_accuracy": 0.38, "possession": 55.5,
    },
    "Colombia": {
        "xg_for": 1.55, "xg_against": 0.72, "xg_diff": 0.83,
        "npxg_for": 1.35, "goals_per90": 1.50, "shots_per90": 12.5,
        "shot_accuracy": 0.37, "possession": 54.0,
    },
    "Uruguay": {
        "xg_for": 1.60, "xg_against": 0.80, "xg_diff": 0.80,
        "npxg_for": 1.38, "goals_per90": 1.58, "shots_per90": 12.0,
        "shot_accuracy": 0.39, "possession": 52.0,
    },
    "Croacia": {
        "xg_for": 1.50, "xg_against": 0.82, "xg_diff": 0.68,
        "npxg_for": 1.30, "goals_per90": 1.52, "shots_per90": 12.5,
        "shot_accuracy": 0.37, "possession": 55.0,
    },
    "Japón": {
        "xg_for": 1.55, "xg_against": 0.85, "xg_diff": 0.70,
        "npxg_for": 1.35, "goals_per90": 1.60, "shots_per90": 13.0,
        "shot_accuracy": 0.36, "possession": 53.0,
    },
    "Marruecos": {
        "xg_for": 1.40, "xg_against": 0.62, "xg_diff": 0.78,
        "npxg_for": 1.22, "goals_per90": 1.42, "shots_per90": 11.5,
        "shot_accuracy": 0.37, "possession": 50.0,
    },
    "Suiza": {
        "xg_for": 1.35, "xg_against": 0.80, "xg_diff": 0.55,
        "npxg_for": 1.18, "goals_per90": 1.32, "shots_per90": 12.0,
        "shot_accuracy": 0.35, "possession": 52.5,
    },
    "Estados Unidos": {
        "xg_for": 1.48, "xg_against": 0.90, "xg_diff": 0.58,
        "npxg_for": 1.28, "goals_per90": 1.50, "shots_per90": 13.0,
        "shot_accuracy": 0.35, "possession": 53.0,
    },
    # === TIER 3 — Strong ===
    "México": {
        "xg_for": 1.38, "xg_against": 0.88, "xg_diff": 0.50,
        "npxg_for": 1.20, "goals_per90": 1.40, "shots_per90": 12.5,
        "shot_accuracy": 0.34, "possession": 52.0,
    },
    "Senegal": {
        "xg_for": 1.30, "xg_against": 0.78, "xg_diff": 0.52,
        "npxg_for": 1.12, "goals_per90": 1.30, "shots_per90": 11.0,
        "shot_accuracy": 0.36, "possession": 48.0,
    },
    "Ecuador": {
        "xg_for": 1.32, "xg_against": 0.88, "xg_diff": 0.44,
        "npxg_for": 1.15, "goals_per90": 1.28, "shots_per90": 11.5,
        "shot_accuracy": 0.34, "possession": 49.0,
    },
    "Turquía": {
        "xg_for": 1.38, "xg_against": 0.95, "xg_diff": 0.43,
        "npxg_for": 1.20, "goals_per90": 1.40, "shots_per90": 12.0,
        "shot_accuracy": 0.35, "possession": 52.5,
    },
    "Austria": {
        "xg_for": 1.40, "xg_against": 0.98, "xg_diff": 0.42,
        "npxg_for": 1.22, "goals_per90": 1.38, "shots_per90": 13.0,
        "shot_accuracy": 0.33, "possession": 54.0,
    },
    "Corea del Sur": {
        "xg_for": 1.30, "xg_against": 0.90, "xg_diff": 0.40,
        "npxg_for": 1.12, "goals_per90": 1.28, "shots_per90": 12.0,
        "shot_accuracy": 0.34, "possession": 51.0,
    },
    "Australia": {
        "xg_for": 1.25, "xg_against": 0.95, "xg_diff": 0.30,
        "npxg_for": 1.08, "goals_per90": 1.25, "shots_per90": 11.5,
        "shot_accuracy": 0.33, "possession": 49.0,
    },
    "Noruega": {
        "xg_for": 1.30, "xg_against": 0.95, "xg_diff": 0.35,
        "npxg_for": 1.12, "goals_per90": 1.28, "shots_per90": 12.0,
        "shot_accuracy": 0.33, "possession": 50.0,
    },
    "Irán": {
        "xg_for": 1.15, "xg_against": 0.78, "xg_diff": 0.37,
        "npxg_for": 1.00, "goals_per90": 1.18, "shots_per90": 10.0,
        "shot_accuracy": 0.35, "possession": 46.0,
    },
    "Suecia": {
        "xg_for": 1.28, "xg_against": 0.95, "xg_diff": 0.33,
        "npxg_for": 1.10, "goals_per90": 1.25, "shots_per90": 11.5,
        "shot_accuracy": 0.34, "possession": 50.5,
    },
    "Canadá": {
        "xg_for": 1.20, "xg_against": 0.98, "xg_diff": 0.22,
        "npxg_for": 1.02, "goals_per90": 1.18, "shots_per90": 11.0,
        "shot_accuracy": 0.33, "possession": 48.5,
    },
    "Egipto": {
        "xg_for": 1.10, "xg_against": 0.82, "xg_diff": 0.28,
        "npxg_for": 0.95, "goals_per90": 1.10, "shots_per90": 10.5,
        "shot_accuracy": 0.33, "possession": 47.0,
    },
    # === TIER 4 — Competitive ===
    "Argelia": {
        "xg_for": 1.18, "xg_against": 0.88, "xg_diff": 0.30,
        "npxg_for": 1.02, "goals_per90": 1.15, "shots_per90": 10.5,
        "shot_accuracy": 0.33, "possession": 48.0,
    },
    "Escocia": {
        "xg_for": 1.15, "xg_against": 0.98, "xg_diff": 0.17,
        "npxg_for": 0.98, "goals_per90": 1.12, "shots_per90": 11.0,
        "shot_accuracy": 0.32, "possession": 49.0,
    },
    "Paraguay": {
        "xg_for": 1.08, "xg_against": 0.95, "xg_diff": 0.13,
        "npxg_for": 0.92, "goals_per90": 1.05, "shots_per90": 10.0,
        "shot_accuracy": 0.32, "possession": 46.5,
    },
    "Costa de Marfil": {
        "xg_for": 1.15, "xg_against": 0.90, "xg_diff": 0.25,
        "npxg_for": 1.00, "goals_per90": 1.18, "shots_per90": 10.5,
        "shot_accuracy": 0.34, "possession": 47.0,
    },
    "República Checa": {
        "xg_for": 1.18, "xg_against": 0.98, "xg_diff": 0.20,
        "npxg_for": 1.02, "goals_per90": 1.15, "shots_per90": 11.0,
        "shot_accuracy": 0.33, "possession": 50.0,
    },
    "Túnez": {
        "xg_for": 1.00, "xg_against": 0.82, "xg_diff": 0.18,
        "npxg_for": 0.88, "goals_per90": 1.00, "shots_per90": 9.5,
        "shot_accuracy": 0.32, "possession": 45.0,
    },
    "Ghana": {
        "xg_for": 1.08, "xg_against": 0.98, "xg_diff": 0.10,
        "npxg_for": 0.92, "goals_per90": 1.05, "shots_per90": 10.0,
        "shot_accuracy": 0.32, "possession": 46.0,
    },
    "Panamá": {
        "xg_for": 0.95, "xg_against": 1.05, "xg_diff": -0.10,
        "npxg_for": 0.82, "goals_per90": 0.95, "shots_per90": 9.0,
        "shot_accuracy": 0.30, "possession": 43.0,
    },
    "Arabia Saudita": {
        "xg_for": 1.00, "xg_against": 1.00, "xg_diff": 0.00,
        "npxg_for": 0.85, "goals_per90": 0.98, "shots_per90": 9.5,
        "shot_accuracy": 0.31, "possession": 45.0,
    },
    "Irak": {
        "xg_for": 0.98, "xg_against": 0.95, "xg_diff": 0.03,
        "npxg_for": 0.82, "goals_per90": 0.95, "shots_per90": 9.0,
        "shot_accuracy": 0.32, "possession": 44.0,
    },
    "Uzbekistán": {
        "xg_for": 1.05, "xg_against": 0.98, "xg_diff": 0.07,
        "npxg_for": 0.90, "goals_per90": 1.02, "shots_per90": 10.0,
        "shot_accuracy": 0.32, "possession": 46.0,
    },
    "Bosnia y Herzegovina": {
        "xg_for": 1.08, "xg_against": 1.05, "xg_diff": 0.03,
        "npxg_for": 0.92, "goals_per90": 1.05, "shots_per90": 10.5,
        "shot_accuracy": 0.31, "possession": 47.0,
    },
    "Jordania": {
        "xg_for": 0.88, "xg_against": 0.98, "xg_diff": -0.10,
        "npxg_for": 0.75, "goals_per90": 0.85, "shots_per90": 8.5,
        "shot_accuracy": 0.30, "possession": 42.0,
    },
    # === TIER 5 — Developing ===
    "Congo RD": {
        "xg_for": 0.95, "xg_against": 1.05, "xg_diff": -0.10,
        "npxg_for": 0.82, "goals_per90": 0.92, "shots_per90": 9.0,
        "shot_accuracy": 0.30, "possession": 43.0,
    },
    "Sudáfrica": {
        "xg_for": 0.88, "xg_against": 1.00, "xg_diff": -0.12,
        "npxg_for": 0.75, "goals_per90": 0.88, "shots_per90": 9.0,
        "shot_accuracy": 0.30, "possession": 44.0,
    },
    "Qatar": {
        "xg_for": 0.82, "xg_against": 1.15, "xg_diff": -0.33,
        "npxg_for": 0.70, "goals_per90": 0.80, "shots_per90": 8.5,
        "shot_accuracy": 0.29, "possession": 42.0,
    },
    "Nueva Zelanda": {
        "xg_for": 0.78, "xg_against": 1.18, "xg_diff": -0.40,
        "npxg_for": 0.68, "goals_per90": 0.75, "shots_per90": 8.0,
        "shot_accuracy": 0.28, "possession": 40.0,
    },
    "Cabo Verde": {
        "xg_for": 0.75, "xg_against": 1.08, "xg_diff": -0.33,
        "npxg_for": 0.65, "goals_per90": 0.72, "shots_per90": 8.0,
        "shot_accuracy": 0.28, "possession": 41.0,
    },
    "Haití": {
        "xg_for": 0.62, "xg_against": 1.35, "xg_diff": -0.73,
        "npxg_for": 0.55, "goals_per90": 0.60, "shots_per90": 7.5,
        "shot_accuracy": 0.26, "possession": 38.0,
    },
    "Curaçao": {
        "xg_for": 0.55, "xg_against": 1.42, "xg_diff": -0.87,
        "npxg_for": 0.48, "goals_per90": 0.52, "shots_per90": 7.0,
        "shot_accuracy": 0.25, "possession": 36.0,
    },
}


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

def _rate_limit():
    """Ensure minimum delay between FBref requests."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < FBREF_REQUEST_DELAY_SECS:
        wait = FBREF_REQUEST_DELAY_SECS - elapsed
        logger.debug("Rate limiting: waiting %.1fs before next FBref request", wait)
        time.sleep(wait)
    _last_request_time = time.time()


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _load_cache() -> Optional[dict]:
    """Load cached xG data if fresh."""
    if not XG_CACHE_FILE.exists():
        return None
    try:
        with open(XG_CACHE_FILE, "r", encoding="utf-8") as f:
            cached = json.load(f)
        cached_time = datetime.fromisoformat(cached.get("timestamp", "2000-01-01"))
        if datetime.now() - cached_time < timedelta(hours=XG_CACHE_TTL_HOURS):
            logger.info("xG stats loaded from cache (age: %s)", datetime.now() - cached_time)
            return cached.get("data", {})
    except Exception as e:
        logger.warning("Failed to load xG cache: %s", e)
    return None


def _save_cache(data: dict) -> None:
    """Persist xG data to JSON cache."""
    try:
        payload = {
            "timestamp": datetime.now().isoformat(),
            "source": "fbref",
            "data": data,
        }
        with open(XG_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("xG stats saved to cache (%d teams)", len(data))
    except Exception as e:
        logger.warning("Failed to save xG cache: %s", e)


# ---------------------------------------------------------------------------
# Scraping functions
# ---------------------------------------------------------------------------

def _resolve_fbref_name(name: str) -> Optional[str]:
    """Resolve an FBref team name to the Spanish name used in the app."""
    name = name.strip()
    if name in FBREF_NAME_MAP:
        return FBREF_NAME_MAP[name]
    # Try case-insensitive
    name_lower = name.lower()
    for fbref_name, spanish_name in FBREF_NAME_MAP.items():
        if fbref_name.lower() == name_lower:
            return spanish_name
    return None


def _scrape_fbref_xg() -> dict[str, dict]:
    """
    Attempt to scrape xG stats from FBref.

    Tries multiple FBref URLs and parsing strategies.
    Returns dict mapping Spanish team name -> stats dict.
    """
    urls_to_try = [
        FBREF_WC_URL,
        FBREF_NATIONAL_TEAMS_URL,
        f"{FBREF_BASE_URL}/en/comps/1/shooting/World-Cup-Stats",
    ]

    for url in urls_to_try:
        try:
            _rate_limit()
            logger.info("Scraping FBref: %s", url)

            with httpx.Client(timeout=20, follow_redirects=True) as client:
                response = client.get(url, headers=HEADERS)

            if response.status_code == 429:
                logger.warning("FBref rate limit hit (429). Using fallback data.")
                return {}

            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Try to find team stats tables
            stats = _parse_fbref_tables(soup)
            if stats:
                logger.info("Successfully scraped %d teams from FBref", len(stats))
                return stats

        except httpx.HTTPStatusError as e:
            logger.warning("FBref HTTP error (%s): %s", url, e)
        except httpx.RequestError as e:
            logger.warning("FBref network error (%s): %s", url, e)
        except Exception as e:
            logger.warning("FBref scrape error (%s): %s", url, e)

        # Wait before trying next URL
        time.sleep(FBREF_REQUEST_DELAY_SECS)

    return {}


def _parse_fbref_tables(soup: BeautifulSoup) -> dict[str, dict]:
    """
    Parse FBref HTML tables for team-level xG stats.

    FBref structures vary, so we try multiple parsing strategies.
    """
    stats: dict[str, dict] = {}

    # Strategy 1: Look for table with id containing "stats"
    for table_id_prefix in ["stats_squads_standard", "stats_squads_shooting", "stats_"]:
        tables = soup.find_all("table", id=lambda x: x and table_id_prefix in x)
        for table in tables:
            parsed = _parse_single_table(table)
            if parsed:
                stats.update(parsed)

    # Strategy 2: Try all tables with class "stats_table"
    if not stats:
        for table in soup.find_all("table", class_="stats_table"):
            parsed = _parse_single_table(table)
            if parsed:
                stats.update(parsed)

    return stats


def _parse_single_table(table) -> dict[str, dict]:
    """Parse a single FBref stats table for team-level data."""
    results = {}

    try:
        # Find all rows (skip header)
        tbody = table.find("tbody")
        if not tbody:
            return results

        for row in tbody.find_all("tr"):
            if row.get("class") and any("thead" in c for c in row.get("class", [])):
                continue

            # Try to find team name
            team_cell = row.find("td", {"data-stat": "team"}) or row.find("th", {"data-stat": "team"})
            if not team_cell:
                team_cell = row.find("td", {"data-stat": "squad"}) or row.find("th", {"data-stat": "squad"})
            if not team_cell:
                continue

            team_name_raw = team_cell.get_text(strip=True)
            # Remove flag emoji or code prefixes
            for prefix in ["🇦🇷", "🇫🇷", "🇧🇷", "🇪🇸"]:
                team_name_raw = team_name_raw.replace(prefix, "").strip()

            team_name = _resolve_fbref_name(team_name_raw)
            if not team_name:
                continue

            # Extract available stats
            def _get_stat(stat_name: str) -> Optional[float]:
                cell = row.find("td", {"data-stat": stat_name})
                if cell:
                    try:
                        return float(cell.get_text(strip=True))
                    except (ValueError, TypeError):
                        pass
                return None

            team_stats = {}
            stat_mappings = {
                "xg_for": ["xg_for", "xg", "expected_goals"],
                "xg_against": ["xg_against", "xga", "expected_goals_against"],
                "goals_per90": ["goals_per90", "gls_per90"],
                "shots_per90": ["shots_per90", "sh_per90"],
                "possession": ["possession", "poss"],
            }

            for our_key, fbref_keys in stat_mappings.items():
                for fbref_key in fbref_keys:
                    val = _get_stat(fbref_key)
                    if val is not None:
                        team_stats[our_key] = val
                        break

            if team_stats:
                # Calculate derived stats
                xg_for = team_stats.get("xg_for", 0)
                xg_against = team_stats.get("xg_against", 0)
                team_stats["xg_diff"] = round(xg_for - xg_against, 2)
                results[team_name] = team_stats

    except Exception as e:
        logger.debug("Error parsing FBref table: %s", e)

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_xg_stats(force_refresh: bool = False) -> pd.DataFrame:
    """
    Get xG (expected goals) stats for all 48 World Cup 2026 teams.

    Returns a DataFrame with columns:
    team, xg_for, xg_against, xg_diff, npxg_for, goals_per90,
    shots_per90, shot_accuracy, possession

    Uses cache -> live scrape -> fallback strategy.

    Parameters
    ----------
    force_refresh : bool
        If True, skip cache and re-scrape.

    Returns
    -------
    pd.DataFrame
    """
    data = None

    # Step 1: Try cache
    if not force_refresh:
        cached = _load_cache()
        if cached:
            data = cached

    # Step 2: Try live scrape
    if data is None:
        scraped = _scrape_fbref_xg()
        if scraped:
            # Merge with fallback for missing teams
            merged = {**FALLBACK_XG_STATS, **scraped}
            data = merged
            _save_cache(data)

    # Step 3: Fallback
    if not data:
        logger.info("Using complete fallback xG data for all 48 teams")
        data = FALLBACK_XG_STATS.copy()
        _save_cache(data)

    # Build DataFrame
    records = []
    for team, stats in data.items():
        record = {"team": team}
        record.update(stats)
        records.append(record)

    df = pd.DataFrame(records)

    # Ensure all expected columns exist
    expected_cols = [
        "team", "xg_for", "xg_against", "xg_diff", "npxg_for",
        "goals_per90", "shots_per90", "shot_accuracy", "possession",
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = 0.0

    df = df.sort_values("xg_diff", ascending=False).reset_index(drop=True)
    logger.info("xG stats ready: %d teams", len(df))
    return df


def get_xg_for_team(team_name: str) -> dict:
    """
    Get xG stats for a specific team.

    Parameters
    ----------
    team_name : str
        Team name in Spanish (e.g., "Argentina", "Países Bajos").

    Returns
    -------
    dict
        xG stats dict. Returns default values if team not found.
    """
    df = get_xg_stats()
    match = df[df["team"] == team_name]

    if not match.empty:
        return match.iloc[0].to_dict()

    # Try fallback directly
    if team_name in FALLBACK_XG_STATS:
        result = {"team": team_name}
        result.update(FALLBACK_XG_STATS[team_name])
        return result

    logger.warning("Team '%s' not found in xG data. Returning defaults.", team_name)
    return {
        "team": team_name,
        "xg_for": 1.0,
        "xg_against": 1.0,
        "xg_diff": 0.0,
        "npxg_for": 0.85,
        "goals_per90": 1.0,
        "shots_per90": 10.0,
        "shot_accuracy": 0.30,
        "possession": 45.0,
    }


def get_xg_differential(home_team: str, away_team: str) -> dict:
    """
    Calculate xG-based strength comparison between two teams.

    Returns
    -------
    dict
        Keys: home_xg_advantage, offensive_edge, defensive_edge, combined_score
    """
    home = get_xg_for_team(home_team)
    away = get_xg_for_team(away_team)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "home_xg_advantage": round(home.get("xg_diff", 0) - away.get("xg_diff", 0), 2),
        "offensive_edge": round(home.get("xg_for", 1.0) - away.get("xg_for", 1.0), 2),
        "defensive_edge": round(away.get("xg_against", 1.0) - home.get("xg_against", 1.0), 2),
        "combined_score": round(
            (home.get("xg_for", 1.0) - away.get("xg_against", 1.0))
            - (away.get("xg_for", 1.0) - home.get("xg_against", 1.0)),
            2,
        ),
    }


# ---------------------------------------------------------------------------
# Module-level execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    df = get_xg_stats(force_refresh=True)
    print("\n=== xG Stats (Top 15) ===")
    print(df[["team", "xg_for", "xg_against", "xg_diff", "possession"]].head(15).to_string(index=False))
    print(f"\nTotal teams: {len(df)}")

    print("\n=== Argentina vs Brasil xG Comparison ===")
    comp = get_xg_differential("Argentina", "Brasil")
    for k, v in comp.items():
        print(f"  {k}: {v}")
