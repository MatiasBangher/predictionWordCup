"""
Historical Results Scraper for World Cup 2026.

Downloads and parses international football results from the
martj42/international_football_results_from_1872 GitHub dataset.

Features:
- Head-to-head records between any two teams
- Average goals per team (last N matches)
- Name normalization (English -> Spanish)
- File-based JSON caching

Data source:
    https://raw.githubusercontent.com/martj42/international_results/master/results.csv
"""

import json
import os
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
RESULTS_CACHE_FILE = CACHE_DIR / "historical_results.json"
RESULTS_CSV_CACHE = CACHE_DIR / "results_raw.csv"
H2H_CACHE_FILE = CACHE_DIR / "h2h_cache.json"
RESULTS_CACHE_TTL_HOURS = 48  # Re-download every 2 days

CSV_URL = (
    "https://raw.githubusercontent.com/martj42/international_results"
    "/master/results.csv"
)

# ---------------------------------------------------------------------------
# Name normalization: English names in the CSV -> Spanish names in the app
# Covers all 48 WC 2026 teams + common alternates
# ---------------------------------------------------------------------------
NAME_NORMALIZATION: dict[str, str] = {
    # Group A
    "Mexico": "México",
    "South Africa": "Sudáfrica",
    "South Korea": "Corea del Sur",
    "Korea Republic": "Corea del Sur",
    "Czech Republic": "República Checa",
    "Czechia": "República Checa",
    # Group B
    "Canada": "Canadá",
    "Bosnia-Herzegovina": "Bosnia y Herzegovina",
    "Bosnia and Herzegovina": "Bosnia y Herzegovina",
    "Qatar": "Qatar",
    "Switzerland": "Suiza",
    # Group C
    "Brazil": "Brasil",
    "Morocco": "Marruecos",
    "Haiti": "Haití",
    "Scotland": "Escocia",
    # Group D
    "United States": "Estados Unidos",
    "USA": "Estados Unidos",
    "United States of America": "Estados Unidos",
    "Paraguay": "Paraguay",
    "Australia": "Australia",
    "Turkey": "Turquía",
    # Group E
    "Germany": "Alemania",
    "Curaçao": "Curaçao",
    "Curacao": "Curaçao",
    "Ivory Coast": "Costa de Marfil",
    "Côte d'Ivoire": "Costa de Marfil",
    "Ecuador": "Ecuador",
    # Group F
    "Netherlands": "Países Bajos",
    "Holland": "Países Bajos",
    "Japan": "Japón",
    "Sweden": "Suecia",
    "Tunisia": "Túnez",
    # Group G
    "Iran": "Irán",
    "New Zealand": "Nueva Zelanda",
    "Belgium": "Bélgica",
    "Egypt": "Egipto",
    # Group H
    "Saudi Arabia": "Arabia Saudita",
    "Uruguay": "Uruguay",
    "Spain": "España",
    "Cape Verde": "Cabo Verde",
    "Cape Verde Islands": "Cabo Verde",
    # Group I
    "France": "Francia",
    "Senegal": "Senegal",
    "Iraq": "Irak",
    "Norway": "Noruega",
    # Group J
    "Argentina": "Argentina",
    "Algeria": "Argelia",
    "Austria": "Austria",
    "Jordan": "Jordania",
    # Group K
    "Portugal": "Portugal",
    "DR Congo": "Congo RD",
    "Congo DR": "Congo RD",
    "Democratic Republic of Congo": "Congo RD",
    "Uzbekistan": "Uzbekistán",
    "Colombia": "Colombia",
    # Group L
    "Ghana": "Ghana",
    "Panama": "Panamá",
    "England": "Inglaterra",
    "Croatia": "Croacia",
}

# Reverse mapping for lookups: Spanish -> English (first match)
SPANISH_TO_ENGLISH: dict[str, list[str]] = {}
for eng, spa in NAME_NORMALIZATION.items():
    SPANISH_TO_ENGLISH.setdefault(spa, []).append(eng)

# All 48 WC 2026 team names in Spanish
WC2026_TEAMS = sorted(set(NAME_NORMALIZATION.values()))

# ---------------------------------------------------------------------------
# Fallback data: aggregate stats for all 48 teams (if CSV download fails)
# avg_goals_scored, avg_goals_conceded based on last ~20 matches (approximate)
# ---------------------------------------------------------------------------
FALLBACK_TEAM_STATS: dict[str, dict] = {
    "Argentina": {"avg_scored": 2.1, "avg_conceded": 0.6, "win_pct": 0.78, "matches": 20},
    "Francia": {"avg_scored": 1.9, "avg_conceded": 0.8, "win_pct": 0.72, "matches": 20},
    "España": {"avg_scored": 2.0, "avg_conceded": 0.7, "win_pct": 0.74, "matches": 20},
    "Inglaterra": {"avg_scored": 1.8, "avg_conceded": 0.7, "win_pct": 0.70, "matches": 20},
    "Brasil": {"avg_scored": 1.9, "avg_conceded": 0.8, "win_pct": 0.68, "matches": 20},
    "Portugal": {"avg_scored": 1.8, "avg_conceded": 0.6, "win_pct": 0.72, "matches": 20},
    "Países Bajos": {"avg_scored": 1.9, "avg_conceded": 0.8, "win_pct": 0.70, "matches": 20},
    "Alemania": {"avg_scored": 1.8, "avg_conceded": 1.0, "win_pct": 0.62, "matches": 20},
    "Bélgica": {"avg_scored": 1.7, "avg_conceded": 0.8, "win_pct": 0.65, "matches": 20},
    "Colombia": {"avg_scored": 1.5, "avg_conceded": 0.7, "win_pct": 0.60, "matches": 20},
    "Uruguay": {"avg_scored": 1.6, "avg_conceded": 0.8, "win_pct": 0.62, "matches": 20},
    "Croacia": {"avg_scored": 1.5, "avg_conceded": 0.8, "win_pct": 0.58, "matches": 20},
    "Japón": {"avg_scored": 1.6, "avg_conceded": 0.9, "win_pct": 0.60, "matches": 20},
    "Marruecos": {"avg_scored": 1.4, "avg_conceded": 0.6, "win_pct": 0.58, "matches": 20},
    "Suiza": {"avg_scored": 1.3, "avg_conceded": 0.8, "win_pct": 0.55, "matches": 20},
    "Estados Unidos": {"avg_scored": 1.5, "avg_conceded": 0.9, "win_pct": 0.55, "matches": 20},
    "México": {"avg_scored": 1.4, "avg_conceded": 0.9, "win_pct": 0.52, "matches": 20},
    "Senegal": {"avg_scored": 1.3, "avg_conceded": 0.8, "win_pct": 0.55, "matches": 20},
    "Ecuador": {"avg_scored": 1.3, "avg_conceded": 0.9, "win_pct": 0.50, "matches": 20},
    "Turquía": {"avg_scored": 1.4, "avg_conceded": 1.0, "win_pct": 0.50, "matches": 20},
    "Austria": {"avg_scored": 1.4, "avg_conceded": 1.0, "win_pct": 0.50, "matches": 20},
    "Corea del Sur": {"avg_scored": 1.3, "avg_conceded": 0.9, "win_pct": 0.50, "matches": 20},
    "Australia": {"avg_scored": 1.3, "avg_conceded": 1.0, "win_pct": 0.48, "matches": 20},
    "Noruega": {"avg_scored": 1.3, "avg_conceded": 1.0, "win_pct": 0.48, "matches": 20},
    "Irán": {"avg_scored": 1.2, "avg_conceded": 0.8, "win_pct": 0.50, "matches": 20},
    "Suecia": {"avg_scored": 1.3, "avg_conceded": 1.0, "win_pct": 0.48, "matches": 20},
    "Canadá": {"avg_scored": 1.2, "avg_conceded": 1.0, "win_pct": 0.45, "matches": 20},
    "Egipto": {"avg_scored": 1.1, "avg_conceded": 0.8, "win_pct": 0.48, "matches": 20},
    "Argelia": {"avg_scored": 1.2, "avg_conceded": 0.9, "win_pct": 0.48, "matches": 20},
    "Escocia": {"avg_scored": 1.2, "avg_conceded": 1.0, "win_pct": 0.45, "matches": 20},
    "Paraguay": {"avg_scored": 1.1, "avg_conceded": 1.0, "win_pct": 0.42, "matches": 20},
    "Costa de Marfil": {"avg_scored": 1.2, "avg_conceded": 0.9, "win_pct": 0.45, "matches": 20},
    "República Checa": {"avg_scored": 1.2, "avg_conceded": 1.0, "win_pct": 0.44, "matches": 20},
    "Túnez": {"avg_scored": 1.0, "avg_conceded": 0.8, "win_pct": 0.42, "matches": 20},
    "Ghana": {"avg_scored": 1.1, "avg_conceded": 1.0, "win_pct": 0.42, "matches": 20},
    "Panamá": {"avg_scored": 1.0, "avg_conceded": 1.1, "win_pct": 0.38, "matches": 20},
    "Arabia Saudita": {"avg_scored": 1.0, "avg_conceded": 1.0, "win_pct": 0.40, "matches": 20},
    "Irak": {"avg_scored": 1.0, "avg_conceded": 1.0, "win_pct": 0.38, "matches": 20},
    "Uzbekistán": {"avg_scored": 1.1, "avg_conceded": 1.0, "win_pct": 0.40, "matches": 20},
    "Bosnia y Herzegovina": {"avg_scored": 1.1, "avg_conceded": 1.1, "win_pct": 0.38, "matches": 20},
    "Jordania": {"avg_scored": 0.9, "avg_conceded": 1.0, "win_pct": 0.35, "matches": 20},
    "Congo RD": {"avg_scored": 1.0, "avg_conceded": 1.1, "win_pct": 0.35, "matches": 20},
    "Sudáfrica": {"avg_scored": 0.9, "avg_conceded": 1.0, "win_pct": 0.35, "matches": 20},
    "Qatar": {"avg_scored": 0.9, "avg_conceded": 1.2, "win_pct": 0.32, "matches": 20},
    "Nueva Zelanda": {"avg_scored": 0.8, "avg_conceded": 1.2, "win_pct": 0.30, "matches": 20},
    "Cabo Verde": {"avg_scored": 0.8, "avg_conceded": 1.1, "win_pct": 0.30, "matches": 20},
    "Haití": {"avg_scored": 0.7, "avg_conceded": 1.4, "win_pct": 0.22, "matches": 20},
    "Curaçao": {"avg_scored": 0.6, "avg_conceded": 1.5, "win_pct": 0.18, "matches": 20},
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_team_name(name: str) -> str:
    """Convert English team name (from CSV) to Spanish name used in the app."""
    return NAME_NORMALIZATION.get(name, name)


def _load_results_cache() -> Optional[pd.DataFrame]:
    """Load cached CSV if fresh."""
    if not RESULTS_CSV_CACHE.exists():
        return None
    try:
        mtime = datetime.fromtimestamp(RESULTS_CSV_CACHE.stat().st_mtime)
        if datetime.now() - mtime < timedelta(hours=RESULTS_CACHE_TTL_HOURS):
            df = pd.read_csv(RESULTS_CSV_CACHE, parse_dates=["date"])
            logger.info("Historical results loaded from CSV cache (%d rows)", len(df))
            return df
    except Exception as e:
        logger.warning("Failed to load results cache: %s", e)
    return None


def _save_results_cache(df: pd.DataFrame) -> None:
    """Save results DataFrame to CSV cache."""
    try:
        df.to_csv(RESULTS_CSV_CACHE, index=False)
        logger.info("Historical results cached (%d rows)", len(df))
    except Exception as e:
        logger.warning("Failed to save results cache: %s", e)


def _download_results() -> Optional[pd.DataFrame]:
    """Download the full results CSV from GitHub."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
    }

    logger.info("Downloading historical results from GitHub ...")

    try:
        with httpx.Client(timeout=30, follow_redirects=True) as client:
            response = client.get(CSV_URL, headers=headers)
            response.raise_for_status()

        # Save raw to disk first, then read
        RESULTS_CSV_CACHE.write_text(response.text, encoding="utf-8")
        df = pd.read_csv(RESULTS_CSV_CACHE, parse_dates=["date"])
        logger.info("Downloaded %d total historical matches", len(df))
        return df

    except httpx.HTTPStatusError as e:
        logger.error("HTTP error downloading results: %s", e)
    except httpx.RequestError as e:
        logger.error("Network error downloading results: %s", e)
    except Exception as e:
        logger.error("Unexpected error downloading results: %s", e)

    return None


def _process_results(df: pd.DataFrame, min_year: int = 2015) -> pd.DataFrame:
    """
    Filter and normalize the raw results DataFrame.

    - Filters to matches from `min_year` onward
    - Normalizes team names to Spanish
    - Adds result column (home_win / draw / away_win)
    """
    # Filter by year
    df = df[df["date"].dt.year >= min_year].copy()

    # Normalize names
    df["home_team"] = df["home_team"].apply(_normalize_team_name)
    df["away_team"] = df["away_team"].apply(_normalize_team_name)

    # Add result column
    conditions = [
        df["home_score"] > df["away_score"],
        df["home_score"] == df["away_score"],
        df["home_score"] < df["away_score"],
    ]
    df["result"] = pd.np.select(conditions, ["home_win", "draw", "away_win"]) if hasattr(pd, 'np') else \
        pd.Series(
            ["home_win" if hs > as_ else "draw" if hs == as_ else "away_win"
             for hs, as_ in zip(df["home_score"], df["away_score"])],
            index=df.index,
        )

    # Filter to only include WC2026 teams
    wc_teams = set(WC2026_TEAMS)
    df = df[df["home_team"].isin(wc_teams) | df["away_team"].isin(wc_teams)]

    logger.info("Processed results: %d matches involving WC2026 teams (since %d)", len(df), min_year)
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_historical_results(force_refresh: bool = False, min_year: int = 2015) -> pd.DataFrame:
    """
    Get processed historical match results.

    Returns a DataFrame with columns:
    date, home_team, away_team, home_score, away_score, tournament, city, country, neutral, result

    Parameters
    ----------
    force_refresh : bool
        If True, re-download from GitHub.
    min_year : int
        Minimum year to include (default 2015).

    Returns
    -------
    pd.DataFrame
    """
    df_raw = None

    if not force_refresh:
        df_raw = _load_results_cache()

    if df_raw is None:
        df_raw = _download_results()

    if df_raw is None:
        logger.warning("Could not download historical results. Returning empty DataFrame.")
        return pd.DataFrame(columns=[
            "date", "home_team", "away_team", "home_score", "away_score",
            "tournament", "city", "country", "neutral", "result",
        ])

    return _process_results(df_raw, min_year=min_year)


def get_head_to_head(team_a: str, team_b: str, min_year: int = 2015) -> dict:
    """
    Get head-to-head record between two teams.

    Parameters
    ----------
    team_a : str
        First team (Spanish name).
    team_b : str
        Second team (Spanish name).
    min_year : int
        Minimum year to consider.

    Returns
    -------
    dict
        Keys: team_a_wins, team_b_wins, draws, total_matches,
              team_a_goals, team_b_goals, last_match, matches (list of dicts)
    """
    # Check H2H cache
    cache_key = f"{sorted([team_a, team_b])[0]}_vs_{sorted([team_a, team_b])[1]}"
    if H2H_CACHE_FILE.exists():
        try:
            with open(H2H_CACHE_FILE, "r", encoding="utf-8") as f:
                h2h_cache = json.load(f)
            if cache_key in h2h_cache:
                cached_entry = h2h_cache[cache_key]
                cache_time = datetime.fromisoformat(cached_entry.get("timestamp", "2000-01-01"))
                if datetime.now() - cache_time < timedelta(hours=RESULTS_CACHE_TTL_HOURS):
                    logger.info("H2H %s loaded from cache", cache_key)
                    return cached_entry.get("data", {})
        except Exception:
            pass

    df = get_historical_results(min_year=min_year)

    # Filter to matches between these two teams (in either order)
    mask = (
        ((df["home_team"] == team_a) & (df["away_team"] == team_b))
        | ((df["home_team"] == team_b) & (df["away_team"] == team_a))
    )
    h2h_df = df[mask].sort_values("date", ascending=False)

    a_wins = 0
    b_wins = 0
    draws = 0
    a_goals = 0
    b_goals = 0
    match_list = []

    for _, row in h2h_df.iterrows():
        is_a_home = row["home_team"] == team_a
        ga = row["home_score"] if is_a_home else row["away_score"]
        gb = row["away_score"] if is_a_home else row["home_score"]

        a_goals += int(ga)
        b_goals += int(gb)

        if ga > gb:
            a_wins += 1
        elif gb > ga:
            b_wins += 1
        else:
            draws += 1

        match_list.append({
            "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
            "home_team": row["home_team"],
            "away_team": row["away_team"],
            "score": f"{int(row['home_score'])}-{int(row['away_score'])}",
            "tournament": row.get("tournament", ""),
        })

    result = {
        "team_a": team_a,
        "team_b": team_b,
        "team_a_wins": a_wins,
        "team_b_wins": b_wins,
        "draws": draws,
        "total_matches": len(h2h_df),
        "team_a_goals": a_goals,
        "team_b_goals": b_goals,
        "last_match": match_list[0] if match_list else None,
        "matches": match_list[:10],  # Last 10 encounters
    }

    # Save to H2H cache
    try:
        h2h_cache = {}
        if H2H_CACHE_FILE.exists():
            with open(H2H_CACHE_FILE, "r", encoding="utf-8") as f:
                h2h_cache = json.load(f)
        h2h_cache[cache_key] = {
            "timestamp": datetime.now().isoformat(),
            "data": result,
        }
        with open(H2H_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(h2h_cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("Failed to save H2H cache: %s", e)

    return result


def get_team_avg_goals(team_name: str, last_n: int = 20) -> dict:
    """
    Calculate average goals scored/conceded for a team over last N matches.

    Parameters
    ----------
    team_name : str
        Team name in Spanish.
    last_n : int
        Number of recent matches to consider.

    Returns
    -------
    dict
        Keys: team, avg_scored, avg_conceded, goal_diff, win_pct, matches_found
    """
    df = get_historical_results()

    # Get all matches for this team
    mask = (df["home_team"] == team_name) | (df["away_team"] == team_name)
    team_df = df[mask].sort_values("date", ascending=False).head(last_n)

    if team_df.empty:
        # Return fallback
        if team_name in FALLBACK_TEAM_STATS:
            fb = FALLBACK_TEAM_STATS[team_name]
            return {
                "team": team_name,
                "avg_scored": fb["avg_scored"],
                "avg_conceded": fb["avg_conceded"],
                "goal_diff": round(fb["avg_scored"] - fb["avg_conceded"], 2),
                "win_pct": fb["win_pct"],
                "matches_found": 0,
                "source": "fallback",
            }
        return {
            "team": team_name,
            "avg_scored": 1.0,
            "avg_conceded": 1.0,
            "goal_diff": 0.0,
            "win_pct": 0.33,
            "matches_found": 0,
            "source": "default",
        }

    total_scored = 0
    total_conceded = 0
    wins = 0

    for _, row in team_df.iterrows():
        if row["home_team"] == team_name:
            total_scored += row["home_score"]
            total_conceded += row["away_score"]
            if row["home_score"] > row["away_score"]:
                wins += 1
        else:
            total_scored += row["away_score"]
            total_conceded += row["home_score"]
            if row["away_score"] > row["home_score"]:
                wins += 1

    n = len(team_df)
    return {
        "team": team_name,
        "avg_scored": round(total_scored / n, 2),
        "avg_conceded": round(total_conceded / n, 2),
        "goal_diff": round((total_scored - total_conceded) / n, 2),
        "win_pct": round(wins / n, 2),
        "matches_found": n,
        "source": "historical",
    }


def get_all_teams_stats(last_n: int = 20) -> pd.DataFrame:
    """
    Get aggregate stats for all 48 WC2026 teams.

    Returns DataFrame with: team, avg_scored, avg_conceded, goal_diff, win_pct, matches_found
    """
    records = []
    for team in WC2026_TEAMS:
        stats = get_team_avg_goals(team, last_n=last_n)
        records.append(stats)

    df = pd.DataFrame(records)
    df = df.sort_values("goal_diff", ascending=False).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Module-level execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

    # Download and process
    df = get_historical_results(force_refresh=True)
    print(f"\nTotal matches: {len(df)}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"\nSample matches:")
    print(df.tail(10).to_string(index=False))

    # H2H example
    h2h = get_head_to_head("Argentina", "Brasil")
    print(f"\n=== Argentina vs Brasil ===")
    print(f"Argentina wins: {h2h['team_a_wins']}, Brasil wins: {h2h['team_b_wins']}, Draws: {h2h['draws']}")

    # Team stats
    stats = get_team_avg_goals("Argentina")
    print(f"\nArgentina stats: {stats}")
