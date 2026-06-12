"""
Scrapers package for World Cup 2026 Prediction System.

This package provides data collection modules for:
- ELO ratings (eloratings.net)
- Historical international match results (GitHub CSV)
- Advanced stats / xG (FBref)
- Team squad data (market values, key players)

All scrapers implement:
- File-based JSON caching in a `cache/` directory
- Comprehensive fallback data for all 48 World Cup 2026 teams
- Robust error handling with logging
- Rate limiting where needed
"""

from .elo_scraper import get_elo_ratings, get_elo_for_team
from .historical_results import (
    get_historical_results,
    get_head_to_head,
    get_team_avg_goals,
)
from .fbref_scraper import get_xg_stats, get_xg_for_team
from .team_squads import fetch_team_squads as get_squad_data

__all__ = [
    "get_elo_ratings",
    "get_elo_for_team",
    "get_historical_results",
    "get_head_to_head",
    "get_team_avg_goals",
    "get_xg_stats",
    "get_xg_for_team",
    "get_squad_data",
]
