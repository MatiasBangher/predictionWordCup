import os
import httpx
import logging
from typing import Dict, Any
from functools import lru_cache

from dotenv import load_dotenv
load_dotenv()

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"

logger = logging.getLogger(__name__)

@lru_cache(maxsize=128)
def fetch_team_stats(team_id: int) -> Dict[str, Any]:
    """
    Fetches team stats from API-Football.
    If no API key is provided, returns mock data.
    """
    if not API_FOOTBALL_KEY:
        logger.warning("API_FOOTBALL_KEY not found. Using MOCK data for stats.")
        return get_mock_team_stats(team_id)

    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }
    url = f"{BASE_URL}/teams/statistics"
    
    # We would pass season and league parameters here
    # Example mock params
    params = {"league": "1", "season": "2026", "team": team_id}
    
    try:
        response = httpx.get(url, headers=headers, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        # If API doesn't have stats yet (e.g. tournament hasn't started), generate realistic deterministic mocks
        if not data.get("response") or not data["response"].get("fixtures"):
            import hashlib
            seed = int(hashlib.md5(str(team_id).encode()).hexdigest(), 16)
            wins = (seed % 6) + 2       # 2 to 7 wins
            loses = (seed % 4) + 1      # 1 to 4 loses
            gf = (seed % 15) + 10       # 10 to 24 goals for
            ga = (seed % 10) + 5        # 5 to 14 goals against
            
            return {
                "fixtures": {"wins": {"total": wins}, "loses": {"total": loses}},
                "goals": {
                    "for": {"average": {"total": round(gf / 10.0, 1)}},
                    "against": {"average": {"total": round(ga / 10.0, 1)}}
                }
            }
            
        return data["response"]
    except Exception as e:
        logger.error(f"Error fetching stats for team {team_id}: {e}")
        return {}

def get_mock_team_stats(team_id: int) -> Dict[str, Any]:
    """Mock stats indicating good or bad form for confidence modeling"""
    # Simulate Argentina (id=1) being very strong
    if team_id == 1:
        return {
            "form": "WWWWW",
            "fixtures": {"wins": {"total": 9}, "draws": {"total": 1}, "loses": {"total": 0}},
            "goals": {"for": {"average": {"total": "2.5"}}, "against": {"average": {"total": "0.5"}}}
        }
    else:
        return {
            "form": "WDLWL",
            "fixtures": {"wins": {"total": 4}, "draws": {"total": 3}, "loses": {"total": 3}},
            "goals": {"for": {"average": {"total": "1.2"}}, "against": {"average": {"total": "1.1"}}}
        }
