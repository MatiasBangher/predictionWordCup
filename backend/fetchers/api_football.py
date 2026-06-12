import os
import hashlib
import httpx
import logging
from typing import Dict, Any, Optional
from functools import lru_cache

from dotenv import load_dotenv
load_dotenv()

from fetchers.team_mapping import get_api_football_id, TEAM_DATA

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Realistic stats calibrated by team tier (based on ELO ranges)
# ──────────────────────────────────────────────────────────────────────────────
_TIER_STATS = {
    # (min_elo, max_elo): (win_range, lose_range, gf_avg, ga_avg, form_pattern)
    "Elite":       {"wins": (7, 9), "loses": (0, 2), "gf": (2.0, 2.8), "ga": (0.4, 0.8), "form": "WWWWW"},
    "MuyFuerte":   {"wins": (6, 8), "loses": (1, 3), "gf": (1.6, 2.2), "ga": (0.6, 1.0), "form": "WWWDW"},
    "Fuerte":      {"wins": (5, 7), "loses": (2, 4), "gf": (1.3, 1.8), "ga": (0.8, 1.2), "form": "WWDWL"},
    "Competitivo": {"wins": (3, 5), "loses": (3, 5), "gf": (1.0, 1.4), "ga": (1.0, 1.3), "form": "WDLWL"},
    "EnDesarrollo":{"wins": (1, 4), "loses": (4, 7), "gf": (0.6, 1.1), "ga": (1.2, 1.7), "form": "LDLWL"},
}


def _get_tier(elo: float) -> str:
    if elo >= 2000: return "Elite"
    if elo >= 1900: return "MuyFuerte"
    if elo >= 1800: return "Fuerte"
    if elo >= 1700: return "Competitivo"
    return "EnDesarrollo"


def _deterministic_value(seed_str: str, min_val: float, max_val: float) -> float:
    """Generate a deterministic pseudo-random value in [min_val, max_val] from a seed string."""
    h = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16)
    frac = (h % 10000) / 10000.0
    return round(min_val + frac * (max_val - min_val), 1)


def get_team_stats_by_name(team_name: str) -> Dict[str, Any]:
    """
    Fetch stats for a team using its Spanish name.
    Uses API-Football if key is available, otherwise generates
    realistic calibrated mock data based on team ELO tier.
    """
    team_id = get_api_football_id(team_name)
    if team_id is None:
        logger.warning(f"No API-Football ID for '{team_name}'. Using calibrated mock.")
        return _generate_calibrated_stats(team_name)
    return fetch_team_stats(team_id, team_name)


@lru_cache(maxsize=128)
def fetch_team_stats(team_id: int, team_name: str = "") -> Dict[str, Any]:
    """
    Fetches team stats from API-Football.
    Falls back to calibrated mock data if API fails or has no data.
    """
    if not API_FOOTBALL_KEY:
        logger.info(f"No API key. Generating calibrated stats for {team_name or team_id}")
        return _generate_calibrated_stats(team_name or str(team_id))

    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    url = f"{BASE_URL}/teams/statistics"
    params = {"league": "1", "season": "2026", "team": team_id}

    try:
        response = httpx.get(url, headers=headers, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()

        resp = data.get("response")
        if resp and isinstance(resp, dict) and resp.get("fixtures"):
            return resp

        # API returned empty — tournament may not have started yet
        logger.info(f"No stats yet from API for {team_name} (ID {team_id}). Using calibrated mock.")
        return _generate_calibrated_stats(team_name or str(team_id))

    except Exception as e:
        logger.error(f"Error fetching stats for {team_name} (ID {team_id}): {e}")
        return _generate_calibrated_stats(team_name or str(team_id))


def _generate_calibrated_stats(team_name: str) -> Dict[str, Any]:
    """
    Generate realistic mock stats based on team's ELO tier.
    Values are deterministic (same team always gets same stats).
    """
    from ml.montecarlo_simulator import DEFAULT_TEAM_RATINGS

    team_data = DEFAULT_TEAM_RATINGS.get(team_name, {})
    elo = team_data.get("elo", 1600)
    tier = _get_tier(elo)
    tier_cfg = _TIER_STATS[tier]

    seed = team_name
    wins = int(_deterministic_value(f"{seed}_wins", *tier_cfg["wins"]))
    loses = int(_deterministic_value(f"{seed}_loses", *tier_cfg["loses"]))
    draws = max(0, 10 - wins - loses)
    gf = _deterministic_value(f"{seed}_gf", *tier_cfg["gf"])
    ga = _deterministic_value(f"{seed}_ga", *tier_cfg["ga"])

    return {
        "form": tier_cfg["form"],
        "fixtures": {
            "played": {"total": wins + draws + loses},
            "wins": {"total": wins},
            "draws": {"total": draws},
            "loses": {"total": loses},
        },
        "goals": {
            "for": {"average": {"total": str(gf)}},
            "against": {"average": {"total": str(ga)}},
        },
        "_source": "calibrated_mock",
        "_elo": elo,
        "_tier": tier,
    }
