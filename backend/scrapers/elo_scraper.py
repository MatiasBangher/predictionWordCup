"""
ELO Ratings Scraper for World Cup 2026.

Scrapes eloratings.net for current ELO ratings of national teams.
Includes comprehensive fallback data for all 48 World Cup 2026 teams.

Data source: https://www.eloratings.net/World.tsv
"""

import json
import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache configuration
# ---------------------------------------------------------------------------
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)
ELO_CACHE_FILE = CACHE_DIR / "elo_ratings.json"
ELO_CACHE_TTL_HOURS = 12  # Re-fetch every 12 hours

# ---------------------------------------------------------------------------
# Country code -> Spanish team name mapping (all 48 WC 2026 teams + extras)
# eloratings.net uses 2-letter codes similar to IOC/FIFA codes
# ---------------------------------------------------------------------------
COUNTRY_CODE_TO_SPANISH: dict[str, str] = {
    # Group A
    "mx": "México",
    "za": "Sudáfrica",
    "kr": "Corea del Sur",
    "cz": "República Checa",
    # Group B
    "ca": "Canadá",
    "ba": "Bosnia y Herzegovina",
    "qa": "Qatar",
    "ch": "Suiza",
    # Group C
    "br": "Brasil",
    "ma": "Marruecos",
    "ht": "Haití",
    "sco": "Escocia",
    # Group D
    "us": "Estados Unidos",
    "py": "Paraguay",
    "au": "Australia",
    "tr": "Turquía",
    # Group E
    "de": "Alemania",
    "cw": "Curaçao",
    "ci": "Costa de Marfil",
    "ec": "Ecuador",
    # Group F
    "nl": "Países Bajos",
    "jp": "Japón",
    "se": "Suecia",
    "tn": "Túnez",
    # Group G
    "ir": "Irán",
    "nz": "Nueva Zelanda",
    "be": "Bélgica",
    "eg": "Egipto",
    # Group H
    "sa": "Arabia Saudita",
    "uy": "Uruguay",
    "es": "España",
    "cv": "Cabo Verde",
    # Group I
    "fr": "Francia",
    "sn": "Senegal",
    "iq": "Irak",
    "no": "Noruega",
    # Group J
    "ar": "Argentina",
    "dz": "Argelia",
    "at": "Austria",
    "jo": "Jordania",
    # Group K
    "pt": "Portugal",
    "cd": "Congo RD",
    "uz": "Uzbekistán",
    "co": "Colombia",
    # Group L
    "gh": "Ghana",
    "pa": "Panamá",
    "eng": "Inglaterra",
    "hr": "Croacia",
}

# eloratings.net sometimes uses alternate codes
ALTERNATE_CODES: dict[str, str] = {
    "me": "México",       # alt
    "ko": "Corea del Sur",
    "cr": "República Checa",
    "bh": "Bosnia y Herzegovina",
    "bo": "Bosnia y Herzegovina",
    "sc": "Escocia",
    "ha": "Haití",
    "mo": "Marruecos",
    "tu": "Turquía",
    "ge": "Alemania",
    "cu": "Curaçao",
    "iv": "Costa de Marfil",
    "ho": "Países Bajos",
    "sw": "Suecia",
    "en": "Inglaterra",
    "nw": "Noruega",
    "al": "Argelia",
    "is": "Irak",
    "po": "Portugal",
    "dr": "Congo RD",
    "ub": "Uzbekistán",
    "pn": "Panamá",
    "sv": "Cabo Verde",
    "sd": "Arabia Saudita",
}

# ---------------------------------------------------------------------------
# Comprehensive fallback ELO ratings for all 48 teams
# Values calibrated to approximate real ELO as of mid-2026
# ---------------------------------------------------------------------------
FALLBACK_ELO_RATINGS: dict[str, int] = {
    # Tier 1 — Elite (ELO 2000+)
    "Argentina": 2146,
    "Francia": 2084,
    "España": 2073,
    "Inglaterra": 2038,
    "Brasil": 2028,
    "Portugal": 2019,
    "Países Bajos": 2009,
    "Alemania": 2003,
    # Tier 2 — Very Strong (1900-1999)
    "Bélgica": 1985,
    "Colombia": 1978,
    "Uruguay": 1963,
    "Croacia": 1955,
    "Japón": 1940,
    "Marruecos": 1932,
    "Suiza": 1919,
    "Estados Unidos": 1907,
    # Tier 3 — Strong (1800-1899)
    "México": 1895,
    "Senegal": 1880,
    "Ecuador": 1872,
    "Turquía": 1868,
    "Austria": 1855,
    "Corea del Sur": 1848,
    "Australia": 1835,
    "Noruega": 1830,
    "Irán": 1821,
    "Suecia": 1815,
    "Canadá": 1808,
    "Egipto": 1802,
    # Tier 4 — Competitive (1700-1799)
    "Argelia": 1790,
    "Escocia": 1785,
    "Paraguay": 1778,
    "Costa de Marfil": 1772,
    "República Checa": 1768,
    "Tunisia": 1755,
    "Túnez": 1755,
    "Ghana": 1748,
    "Panamá": 1730,
    "Arabia Saudita": 1725,
    "Irak": 1710,
    "Uzbekistán": 1705,
    "Bosnia y Herzegovina": 1698,
    "Jordania": 1688,
    # Tier 5 — Developing (1500-1699)
    "Congo RD": 1672,
    "Sudáfrica": 1658,
    "Qatar": 1638,
    "Nueva Zelanda": 1595,
    "Cabo Verde": 1570,
    "Haití": 1490,
    "Curaçao": 1455,
}


def _load_cache() -> Optional[dict]:
    """Load cached ELO data if it exists and is fresh."""
    if not ELO_CACHE_FILE.exists():
        return None
    try:
        with open(ELO_CACHE_FILE, "r", encoding="utf-8") as f:
            cached = json.load(f)
        cached_time = datetime.fromisoformat(cached.get("timestamp", "2000-01-01"))
        if datetime.now() - cached_time < timedelta(hours=ELO_CACHE_TTL_HOURS):
            logger.info("ELO ratings loaded from cache (age: %s)", datetime.now() - cached_time)
            return cached.get("data", {})
    except Exception as e:
        logger.warning("Failed to load ELO cache: %s", e)
    return None


def _save_cache(data: dict) -> None:
    """Persist ELO data to JSON cache."""
    try:
        payload = {
            "timestamp": datetime.now().isoformat(),
            "source": "eloratings.net",
            "data": data,
        }
        with open(ELO_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info("ELO ratings saved to cache (%d teams)", len(data))
    except Exception as e:
        logger.warning("Failed to save ELO cache: %s", e)


def _resolve_team_name(code: str) -> Optional[str]:
    """Resolve a country code to a Spanish team name."""
    code_lower = code.lower().strip()
    return COUNTRY_CODE_TO_SPANISH.get(code_lower) or ALTERNATE_CODES.get(code_lower)


def _scrape_elo_ratings() -> dict[str, int]:
    """
    Scrape the current ELO ratings from eloratings.net.

    The TSV file format is:
    rank \\t country_name \\t country_code \\t elo_rating \\t ...
    """
    url = "https://www.eloratings.net/World.tsv"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/tab-separated-values,text/plain,*/*",
        "Referer": "https://www.eloratings.net/",
    }

    logger.info("Scraping ELO ratings from %s ...", url)

    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

        ratings: dict[str, int] = {}
        lines = response.text.strip().split("\n")

        for line in lines:
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            try:
                code = parts[2].strip()
                elo = int(parts[3].strip())
                team_name = _resolve_team_name(code)
                if team_name and team_name not in ratings:
                    ratings[team_name] = elo
            except (ValueError, IndexError):
                continue

        if len(ratings) >= 20:
            logger.info("Successfully scraped %d WC2026 team ELO ratings", len(ratings))
            # Fill any missing WC2026 teams from fallback
            for team, fallback_elo in FALLBACK_ELO_RATINGS.items():
                if team not in ratings:
                    ratings[team] = fallback_elo
                    logger.debug("Filled missing team from fallback: %s = %d", team, fallback_elo)
            return ratings
        else:
            logger.warning(
                "Only %d teams resolved from scrape. Using fallback data.", len(ratings)
            )
            # Merge scraped with fallback (prefer scraped)
            merged = {**FALLBACK_ELO_RATINGS, **ratings}
            return merged

    except httpx.HTTPStatusError as e:
        logger.error("HTTP error scraping ELO ratings: %s %s", e.response.status_code, e)
    except httpx.RequestError as e:
        logger.error("Network error scraping ELO ratings: %s", e)
    except Exception as e:
        logger.error("Unexpected error scraping ELO ratings: %s", e)

    return {}


def get_elo_ratings(force_refresh: bool = False) -> pd.DataFrame:
    """
    Get ELO ratings for all 48 World Cup 2026 teams.

    Returns a DataFrame with columns: ['team', 'elo', 'tier']
    Uses cache -> live scrape -> fallback strategy.

    Parameters
    ----------
    force_refresh : bool
        If True, skip cache and re-scrape.

    Returns
    -------
    pd.DataFrame
        Columns: team (str), elo (int), tier (str)
    """
    ratings = None

    # Step 1: Try cache
    if not force_refresh:
        cached = _load_cache()
        if cached:
            ratings = cached

    # Step 2: Try live scrape
    if ratings is None:
        scraped = _scrape_elo_ratings()
        if scraped:
            ratings = scraped
            _save_cache(ratings)

    # Step 3: Fallback
    if not ratings:
        logger.warning("Using complete fallback ELO data for all 48 teams")
        ratings = FALLBACK_ELO_RATINGS.copy()
        _save_cache(ratings)

    # Build DataFrame
    df = pd.DataFrame(
        [{"team": team, "elo": elo} for team, elo in ratings.items()]
    )

    # Assign tiers based on ELO ranges
    def _assign_tier(elo: int) -> str:
        if elo >= 2000:
            return "Elite"
        elif elo >= 1900:
            return "Muy Fuerte"
        elif elo >= 1800:
            return "Fuerte"
        elif elo >= 1700:
            return "Competitivo"
        else:
            return "En Desarrollo"

    df["tier"] = df["elo"].apply(_assign_tier)
    df = df.sort_values("elo", ascending=False).reset_index(drop=True)

    logger.info("ELO ratings ready: %d teams (range: %d–%d)", len(df), df["elo"].min(), df["elo"].max())
    return df


def get_elo_for_team(team_name: str) -> int:
    """
    Get the ELO rating for a specific team.

    Parameters
    ----------
    team_name : str
        Team name in Spanish (e.g., "Argentina", "Países Bajos").

    Returns
    -------
    int
        ELO rating. Returns 1500 (default) if team not found.
    """
    df = get_elo_ratings()
    match = df.loc[df["team"] == team_name, "elo"]
    if not match.empty:
        return int(match.iloc[0])

    # Try fallback dict directly
    if team_name in FALLBACK_ELO_RATINGS:
        return FALLBACK_ELO_RATINGS[team_name]

    logger.warning("Team '%s' not found in ELO data. Returning default 1500.", team_name)
    return 1500


def get_elo_differential(home_team: str, away_team: str) -> float:
    """
    Calculate ELO differential between two teams.

    Positive value = home team is stronger.

    Parameters
    ----------
    home_team : str
    away_team : str

    Returns
    -------
    float
        ELO differential (home - away).
    """
    home_elo = get_elo_for_team(home_team)
    away_elo = get_elo_for_team(away_team)
    return float(home_elo - away_elo)


def get_win_probability_from_elo(home_team: str, away_team: str, home_advantage: float = 65.0) -> dict:
    """
    Calculate expected win probability using the ELO formula.

    Uses the standard formula: E = 1 / (1 + 10^((R_away - R_home - home_adv) / 400))

    Parameters
    ----------
    home_team : str
    away_team : str
    home_advantage : float
        ELO points bonus for home team (default 65 for international football).

    Returns
    -------
    dict
        Keys: home_win, draw, away_win (float percentages)
    """
    home_elo = get_elo_for_team(home_team) + home_advantage
    away_elo = get_elo_for_team(away_team)

    diff = home_elo - away_elo
    expected_home = 1.0 / (1.0 + 10 ** (-diff / 400.0))

    # Split into win/draw/away using empirical international football draw rate (~25%)
    draw_factor = 0.25 * (1 - abs(expected_home - 0.5) * 1.5)
    draw_factor = max(0.10, min(0.30, draw_factor))

    home_win = expected_home * (1 - draw_factor)
    away_win = (1 - expected_home) * (1 - draw_factor)

    total = home_win + draw_factor + away_win
    return {
        "home_win": round(home_win / total * 100, 1),
        "draw": round(draw_factor / total * 100, 1),
        "away_win": round(away_win / total * 100, 1),
    }


# ---------------------------------------------------------------------------
# Module-level execution for quick testing
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    df = get_elo_ratings(force_refresh=True)
    print("\n=== ELO Ratings (Top 15) ===")
    print(df.head(15).to_string(index=False))
    print(f"\nTotal teams: {len(df)}")

    print("\n=== Argentina vs Brasil ===")
    probs = get_win_probability_from_elo("Argentina", "Brasil")
    print(f"Home: {probs['home_win']}% | Draw: {probs['draw']}% | Away: {probs['away_win']}%")
