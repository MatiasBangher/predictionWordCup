"""
Team Squads Scraper for World Cup 2026
=======================================
Extracts team squads, market values, and injury status for 48 teams.
In a real environment, this might scrape Transfermarkt or a similar site.
For demonstration, this provides robust mock data + an architecture for scraping.
"""

import logging
import json
import time
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_FILE = CACHE_DIR / "team_squads.json"
CACHE_TTL = 86400 * 7  # 1 week

# MOCK DATA FOR SQUADS
MOCK_SQUADS = {
    "Argentina": {
        "market_value_m": 850.5,
        "key_injuries": ["Dybala"],
        "top_stars": ["Messi", "Lautaro Martinez", "Enzo Fernandez"],
        "average_age": 27.5
    },
    "Francia": {
        "market_value_m": 1050.0,
        "key_injuries": ["Lucas Hernandez"],
        "top_stars": ["Mbappe", "Griezmann", "Tchouameni"],
        "average_age": 26.2
    },
    "Brasil": {
        "market_value_m": 1090.0,
        "key_injuries": ["Neymar (Doubtful)"],
        "top_stars": ["Vinicius Jr", "Rodrygo", "Alisson"],
        "average_age": 26.8
    },
    "Inglaterra": {
        "market_value_m": 1250.0,
        "key_injuries": [],
        "top_stars": ["Bellingham", "Kane", "Saka"],
        "average_age": 25.5
    },
    "España": {
        "market_value_m": 900.0,
        "key_injuries": ["Gavi (Recovering)"],
        "top_stars": ["Pedri", "Yamal", "Rodri"],
        "average_age": 26.0
    },
    "México": {
        "market_value_m": 220.0,
        "key_injuries": [],
        "top_stars": ["Alvarez", "Gimenez"],
        "average_age": 28.1
    },
    "Estados Unidos": {
        "market_value_m": 280.0,
        "key_injuries": [],
        "top_stars": ["Pulisic", "Reyna", "McKennie"],
        "average_age": 25.1
    }
}

def fetch_team_squads(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Fetches squad info. Uses cache if valid.
    """
    if not force_refresh and CACHE_FILE.exists():
        if time.time() - CACHE_FILE.stat().st_mtime < CACHE_TTL:
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    logger.info("Loaded team squads from cache.")
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")

    logger.info("Fetching fresh team squads data...")
    # Real scraping logic would go here
    # For now, we simulate a successful scrape using mock data
    
    data = MOCK_SQUADS
    
    # Pad missing teams with generic data
    from ml.montecarlo_simulator import DEFAULT_TEAM_RATINGS
    for team in DEFAULT_TEAM_RATINGS.keys():
        if team not in data:
            data[team] = {
                "market_value_m": 100.0,
                "key_injuries": [],
                "top_stars": [],
                "average_age": 27.0
            }
            
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to write cache: {e}")

    return data

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = fetch_team_squads()
    print(f"Loaded squads for {len(res)} teams.")
