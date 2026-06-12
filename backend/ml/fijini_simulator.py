"""
Fijini Simulator — Monte Carlo Bet Evaluator for World Cup 2026
================================================================
Evaluates individual "fijini" bets (safe bets, odds 1.10–1.30) by running
N Monte Carlo Poisson-based match simulations and comparing the estimated
real probability against the implied probability from the bookmaker odds.

Supports 12 market types:
    h2h, totals, btts, corners, cards, double_chance,
    draw_no_bet, handicap, asian_handicap, first_goal,
    half_time, shots_on_target

Usage:
    from ml.fijini_simulator import simulate_fijini, simulate_match_fijinis

    result = simulate_fijini(
        home_team="Argentina",
        away_team="Francia",
        market_key="totals",
        selection="Más de 1.5",
        price=1.18,
    )
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports from sibling modules (fail gracefully)
# ---------------------------------------------------------------------------
_team_ratings_cache: Optional[Dict] = None
_avg_attack_cache: Optional[float] = None
_avg_defense_cache: Optional[float] = None


def _get_team_ratings() -> Dict:
    """Load team ratings once and cache."""
    global _team_ratings_cache, _avg_attack_cache, _avg_defense_cache
    if _team_ratings_cache is not None:
        return _team_ratings_cache

    try:
        from ml.montecarlo_simulator import load_team_data
        _team_ratings_cache = load_team_data()
    except ImportError:
        try:
            from backend.ml.montecarlo_simulator import load_team_data
            _team_ratings_cache = load_team_data()
        except ImportError:
            logger.warning("Could not import load_team_data. Using inline defaults.")
            _team_ratings_cache = _build_fallback_ratings()

    attacks = [r.attack for r in _team_ratings_cache.values()]
    defenses = [r.defense for r in _team_ratings_cache.values()]
    _avg_attack_cache = float(np.mean(attacks)) if attacks else 1.0
    _avg_defense_cache = float(np.mean(defenses)) if defenses else 1.0
    return _team_ratings_cache


def _build_fallback_ratings():
    """Inline fallback if montecarlo_simulator can't be imported."""
    from dataclasses import dataclass as _dc

    @_dc
    class _TR:
        name: str
        elo: float
        attack: float
        defense: float

    try:
        from ml.montecarlo_simulator import TeamRating, DEFAULT_TEAM_RATINGS
    except ImportError:
        try:
            from backend.ml.montecarlo_simulator import TeamRating, DEFAULT_TEAM_RATINGS
        except ImportError:
            # Absolute minimal fallback
            return {}

    ratings = {}
    for name, vals in DEFAULT_TEAM_RATINGS.items():
        ratings[name] = TeamRating(
            name=name, elo=vals["elo"],
            attack=vals["attack"], defense=vals["defense"],
        )
    return ratings


def _get_team_rating(team_name: str):
    """Get a single team's rating, with fallback for unknown teams."""
    ratings = _get_team_ratings()

    if team_name in ratings:
        return ratings[team_name]

    # Try case-insensitive / accent-insensitive lookup
    normalized = _normalize_str(team_name)
    for name, rating in ratings.items():
        if _normalize_str(name) == normalized:
            return rating

    # Build a default rating for unknown teams
    logger.warning("Team '%s' not found in ratings. Using fallback ELO=1500.", team_name)
    try:
        from ml.montecarlo_simulator import TeamRating
    except ImportError:
        try:
            from backend.ml.montecarlo_simulator import TeamRating
        except ImportError:
            @dataclass
            class TeamRating:
                name: str
                elo: float
                attack: float
                defense: float

    return TeamRating(name=team_name, elo=1500.0, attack=1.0, defense=1.2)


def _get_historical_goals(team_name: str) -> Dict[str, float]:
    """Get average goals scored/conceded from historical scraper."""
    try:
        from scrapers.historical_results import get_team_avg_goals, FALLBACK_TEAM_STATS
    except ImportError:
        try:
            from backend.scrapers.historical_results import get_team_avg_goals, FALLBACK_TEAM_STATS
        except ImportError:
            return {"avg_scored": 1.2, "avg_conceded": 1.0}

    try:
        stats = get_team_avg_goals(team_name)
        return {
            "avg_scored": stats.get("avg_scored", 1.2),
            "avg_conceded": stats.get("avg_conceded", 1.0),
        }
    except Exception as e:
        logger.warning("Failed to get historical goals for '%s': %s", team_name, e)
        fb = FALLBACK_TEAM_STATS.get(team_name, {})
        return {
            "avg_scored": fb.get("avg_scored", 1.2),
            "avg_conceded": fb.get("avg_conceded", 1.0),
        }


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_RATE: float = 1.3          # avg goals per team per WC match
HOME_FACTOR: float = 1.05      # slight geographic proximity advantage
HOST_NATIONS = {"México", "Estados Unidos", "Canadá"}

# Corner calibration
CORNER_BASE_HIGH_ATK = 6.0      # attack > 1.3
CORNER_BASE_MED_ATK = 5.0       # attack 1.0–1.3
CORNER_BASE_LOW_ATK = 3.5       # attack < 1.0
CORNER_VS_LOW_DEF_BONUS = 0.5   # opponent defense < 0.95
CORNER_VS_HIGH_DEF_PENALTY = -0.5  # opponent defense > 1.2

# Card calibration
CARD_BASE = 2.0                 # base cards per team per match
CARD_ELO_DIFF_THRESHOLD = 200   # weaker team +0.5 cards
CARD_COMPETITIVE_THRESHOLD = 100  # both teams +0.3 cards

# Shots on target calibration
SOT_BASE = 4.0                  # base shots on target per team

# Half-time scaling
HALF_TIME_FACTOR = 0.5          # λ for first half is half of full match


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------
def _normalize_str(s: str) -> str:
    """Strip accents and lowercase for fuzzy matching."""
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _parse_line_from_selection(selection: str) -> Optional[float]:
    """
    Extract the numeric line from a selection string.

    Examples:
        "Más de 2.5"   -> 2.5
        "Menos de 3.5" -> 3.5
        "Over 10.5"    -> 10.5
        "+1.5"         -> 1.5
        "-0.5"         -> -0.5
    """
    # Try to find a decimal or integer number (with optional sign)
    match = re.search(r"[+-]?\d+\.?\d*", selection)
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return None


def _is_over_selection(selection: str) -> bool:
    """Check if a selection is 'over' / 'más de'."""
    sel = selection.lower()
    return "más de" in sel or "mas de" in sel or "over" in sel or sel.startswith("+") or "al menos" in sel


def _is_under_selection(selection: str) -> bool:
    """Check if a selection is 'under' / 'menos de'."""
    sel_lower = selection.lower()
    return "menos de" in sel_lower or "under" in sel_lower


def _implied_probability(price: float) -> float:
    """Convert decimal odds to implied probability (0–100)."""
    if price <= 1.0:
        return 100.0
    return (1.0 / price) * 100.0


def _wilson_score_interval(
    successes: int,
    total: int,
    confidence: float = 0.95,
) -> Tuple[float, float]:
    """
    Wilson score confidence interval for a binomial proportion.

    Returns (lower, upper) as percentages (0–100).
    """
    if total == 0:
        return (0.0, 100.0)

    z = 1.96 if confidence == 0.95 else 1.645  # z for 95% or 90%
    p_hat = successes / total
    denominator = 1 + z**2 / total

    center = (p_hat + z**2 / (2 * total)) / denominator
    margin = (z / denominator) * math.sqrt(
        (p_hat * (1 - p_hat) / total) + (z**2 / (4 * total**2))
    )

    lower = max(0.0, (center - margin)) * 100
    upper = min(1.0, (center + margin)) * 100
    return (round(lower, 2), round(upper, 2))


def _value_rating(edge: float) -> str:
    """Assign a colour-coded value rating based on edge."""
    if edge > 8.0:
        return "GREEN"
    elif edge > 4.0:
        return "YELLOW"
    elif edge > 0.0:
        return "ORANGE"
    else:
        return "RED"


def _recommendation(edge: float, ci_lower: float, implied_prob: float) -> str:
    """
    Generate a recommendation based on edge and confidence interval.

    BET:     edge > 3% AND lower CI bound > implied prob
    CAUTION: edge > 0% but lower CI <= implied prob
    SKIP:    edge <= 0%
    """
    if edge > 3.0 and ci_lower > implied_prob:
        return "BET"
    elif edge > 0.0:
        return "CAUTION"
    else:
        return "SKIP"


# ---------------------------------------------------------------------------
# Lambda (expected goals) calculation — mirrors montecarlo_simulator
# ---------------------------------------------------------------------------
def _compute_lambda(
    attack_a: float,
    defense_b: float,
    avg_attack: float,
    avg_defense: float,
    is_host: bool = False,
) -> float:
    """Expected goals λ for team A attacking against team B's defense."""
    lam = BASE_RATE * (attack_a / avg_attack) * (avg_defense / defense_b)
    if is_host:
        lam *= HOME_FACTOR
    return max(lam, 0.15)


def _compute_corner_lambda(attack: float, opp_defense: float) -> float:
    """
    Compute expected corners per team per match.

    Calibration:
        High attack (>1.3): ~6 corners
        Medium attack (1.0-1.3): ~5 corners
        Low attack (<1.0): ~3.5 corners
        Against low defense (<0.95): +0.5
        Against high defense (>1.2): -0.5
    """
    if attack > 1.3:
        base = CORNER_BASE_HIGH_ATK
    elif attack >= 1.0:
        base = CORNER_BASE_MED_ATK
    else:
        base = CORNER_BASE_LOW_ATK

    if opp_defense < 0.95:
        base += CORNER_VS_LOW_DEF_BONUS
    elif opp_defense > 1.2:
        base += CORNER_VS_HIGH_DEF_PENALTY

    return max(base, 1.0)


def _compute_card_lambda(
    elo_team: float,
    elo_opponent: float,
) -> float:
    """
    Compute expected cards per team per match.

    Calibration:
        Base: ~2 cards per team
        High ELO diff (>200): weaker team +0.5
        Competitive match (ELO diff <100): both teams +0.3
    """
    base = CARD_BASE
    elo_diff = abs(elo_team - elo_opponent)

    if elo_diff > CARD_ELO_DIFF_THRESHOLD and elo_team < elo_opponent:
        base += 0.5  # weaker team fouls more
    elif elo_diff < CARD_COMPETITIVE_THRESHOLD:
        base += 0.3  # competitive match = more intensity

    return max(base, 0.5)


def _compute_sot_lambda(attack: float) -> float:
    """
    Compute expected shots on target per team per match.

    Base: ~4 SOT/team/match, scaled by attack strength.
    """
    return max(SOT_BASE * attack, 1.0)


# ---------------------------------------------------------------------------
# Core vectorised simulation engine
# ---------------------------------------------------------------------------
@dataclass
class SimulatedMatchData:
    """Pre-computed arrays from N simulated matches for a given team pair."""
    goals_home: np.ndarray      # (N,) int – home team goals
    goals_away: np.ndarray      # (N,) int – away team goals
    corners_home: np.ndarray    # (N,) int
    corners_away: np.ndarray    # (N,) int
    cards_home: np.ndarray      # (N,) int
    cards_away: np.ndarray      # (N,) int
    sot_home: np.ndarray        # (N,) int – shots on target
    sot_away: np.ndarray        # (N,) int
    goals_home_ht: np.ndarray   # (N,) int – first half goals
    goals_away_ht: np.ndarray   # (N,) int
    first_goal_time: np.ndarray # (N,) float – minute of first goal (0–90+)
    lam_home: float             # home λ (full match)
    lam_away: float             # away λ (full match)
    n: int


def simulate_match_arrays(
    home_team: str,
    away_team: str,
    n_simulations: int = 10_000,
    seed: Optional[int] = None,
) -> SimulatedMatchData:
    """
    Run N vectorised Poisson match simulations and return all derived arrays.

    This is the engine that powers every market evaluation. It simulates:
      - Goals (full match & first half)
      - Corners
      - Cards
      - Shots on target
      - Time of first goal (exponential distribution)

    All simulations use numpy vectorised operations for speed.
    """
    rng = np.random.default_rng(seed)

    ratings = _get_team_ratings()
    home_r = _get_team_rating(home_team)
    away_r = _get_team_rating(away_team)

    avg_atk = _avg_attack_cache or 1.0
    avg_def = _avg_defense_cache or 1.0

    # --- Goals (full match) ------------------------------------------------
    is_home_host = home_team in HOST_NATIONS
    is_away_host = away_team in HOST_NATIONS

    lam_home = _compute_lambda(home_r.attack, away_r.defense, avg_atk, avg_def, is_host=is_home_host)
    lam_away = _compute_lambda(away_r.attack, home_r.defense, avg_atk, avg_def, is_host=is_away_host)

    # Blend with historical data for better calibration
    hist_home = _get_historical_goals(home_team)
    hist_away = _get_historical_goals(away_team)

    # Weighted blend: 70% model, 30% historical
    blend_weight = 0.3
    lam_home_adj = lam_home * (1 - blend_weight) + hist_home["avg_scored"] * blend_weight
    lam_away_adj = lam_away * (1 - blend_weight) + hist_away["avg_scored"] * blend_weight

    # Ensure reasonable bounds
    lam_home_adj = np.clip(lam_home_adj, 0.2, 4.5)
    lam_away_adj = np.clip(lam_away_adj, 0.2, 4.5)

    goals_home = rng.poisson(lam_home_adj, size=n_simulations)
    goals_away = rng.poisson(lam_away_adj, size=n_simulations)

    # --- Goals (first half) ------------------------------------------------
    goals_home_ht = rng.poisson(lam_home_adj * HALF_TIME_FACTOR, size=n_simulations)
    goals_away_ht = rng.poisson(lam_away_adj * HALF_TIME_FACTOR, size=n_simulations)

    # Clamp HT goals so they don't exceed FT goals
    goals_home_ht = np.minimum(goals_home_ht, goals_home)
    goals_away_ht = np.minimum(goals_away_ht, goals_away)

    # --- Corners -----------------------------------------------------------
    corner_lam_home = _compute_corner_lambda(home_r.attack, away_r.defense)
    corner_lam_away = _compute_corner_lambda(away_r.attack, home_r.defense)
    corners_home = rng.poisson(corner_lam_home, size=n_simulations)
    corners_away = rng.poisson(corner_lam_away, size=n_simulations)

    # --- Cards -------------------------------------------------------------
    card_lam_home = _compute_card_lambda(home_r.elo, away_r.elo)
    card_lam_away = _compute_card_lambda(away_r.elo, home_r.elo)
    cards_home = rng.poisson(card_lam_home, size=n_simulations)
    cards_away = rng.poisson(card_lam_away, size=n_simulations)

    # --- Shots on target ---------------------------------------------------
    sot_lam_home = _compute_sot_lambda(home_r.attack)
    sot_lam_away = _compute_sot_lambda(away_r.attack)
    sot_home = rng.poisson(sot_lam_home, size=n_simulations)
    sot_away = rng.poisson(sot_lam_away, size=n_simulations)

    # --- First goal time (exponential) -------------------------------------
    # Combined goal rate per minute = (lam_home + lam_away) / 90
    combined_rate_per_minute = (lam_home_adj + lam_away_adj) / 90.0
    # Time to first goal follows Exp(combined_rate)
    # If no goals in a sim, set time = 95 (no first goal)
    first_goal_time = np.full(n_simulations, 95.0)
    has_goals = (goals_home + goals_away) > 0
    n_with_goals = has_goals.sum()
    if n_with_goals > 0:
        first_goal_time[has_goals] = rng.exponential(
            1.0 / max(combined_rate_per_minute, 0.001),
            size=n_with_goals,
        )
        # Clamp to 0–90+ range
        first_goal_time[has_goals] = np.clip(first_goal_time[has_goals], 1.0, 90.0)

    return SimulatedMatchData(
        goals_home=goals_home,
        goals_away=goals_away,
        corners_home=corners_home,
        corners_away=corners_away,
        cards_home=cards_home,
        cards_away=cards_away,
        sot_home=sot_home,
        sot_away=sot_away,
        goals_home_ht=goals_home_ht,
        goals_away_ht=goals_away_ht,
        first_goal_time=first_goal_time,
        lam_home=lam_home_adj,
        lam_away=lam_away_adj,
        n=n_simulations,
    )


# ---------------------------------------------------------------------------
# Market-specific evaluators
#
# Each returns (successes: int, sim_details: dict)
# ---------------------------------------------------------------------------

def _identify_team_in_selection(
    selection: str,
    home_team: str,
    away_team: str,
) -> Optional[str]:
    """
    Identify which team a selection refers to.

    Handles:  "Argentina", "México o Empate", "Local", "Visitante"
    """
    sel_lower = _normalize_str(selection)
    home_lower = _normalize_str(home_team)
    away_lower = _normalize_str(away_team)

    if home_lower in sel_lower or "local" in sel_lower or "home" in sel_lower:
        return "home"
    elif away_lower in sel_lower or "visitante" in sel_lower or "away" in sel_lower:
        return "away"
    elif "empate" in sel_lower or "draw" in sel_lower:
        return "draw"
    return None


def _eval_h2h(
    data: SimulatedMatchData,
    selection: str,
    home_team: str,
    away_team: str,
) -> Tuple[int, Dict]:
    """Match Winner (1X2)."""
    home_wins = int(np.sum(data.goals_home > data.goals_away))
    draws = int(np.sum(data.goals_home == data.goals_away))
    away_wins = int(np.sum(data.goals_home < data.goals_away))

    side = _identify_team_in_selection(selection, home_team, away_team)

    if side == "home":
        successes = home_wins
    elif side == "away":
        successes = away_wins
    elif side == "draw":
        successes = draws
    else:
        # Try to parse "1" / "X" / "2"
        sel_stripped = selection.strip()
        if sel_stripped == "1":
            successes = home_wins
        elif sel_stripped.upper() == "X":
            successes = draws
        elif sel_stripped == "2":
            successes = away_wins
        else:
            logger.warning("Could not parse h2h selection: '%s'. Defaulting to home.", selection)
            successes = home_wins

    details = {
        "home_win_pct": round(home_wins / data.n * 100, 2),
        "draw_pct": round(draws / data.n * 100, 2),
        "away_win_pct": round(away_wins / data.n * 100, 2),
        "avg_goals_home": round(float(data.goals_home.mean()), 2),
        "avg_goals_away": round(float(data.goals_away.mean()), 2),
    }
    return successes, details


def _eval_totals(
    data: SimulatedMatchData,
    selection: str,
) -> Tuple[int, Dict]:
    """Over/Under total goals."""
    line = _parse_line_from_selection(selection)
    if line is None:
        logger.warning("Could not parse totals line from '%s'. Using 2.5.", selection)
        line = 2.5

    total_goals = data.goals_home + data.goals_away
    is_over = _is_over_selection(selection)

    if is_over:
        successes = int(np.sum(total_goals > line))
    else:
        successes = int(np.sum(total_goals < line))

    # Goal distribution
    unique, counts = np.unique(total_goals, return_counts=True)
    goal_dist = {int(g): round(int(c) / data.n * 100, 2) for g, c in zip(unique, counts)}

    details = {
        "line": line,
        "direction": "over" if is_over else "under",
        "avg_total_goals": round(float(total_goals.mean()), 2),
        "goal_distribution": dict(sorted(goal_dist.items())[:8]),  # top 8
    }
    return successes, details


def _eval_btts(
    data: SimulatedMatchData,
    selection: str,
) -> Tuple[int, Dict]:
    """Both Teams To Score."""
    both_scored = (data.goals_home >= 1) & (data.goals_away >= 1)
    btts_count = int(np.sum(both_scored))

    sel_lower = selection.lower()
    is_yes = "sí" in sel_lower or "si" in sel_lower or "yes" in sel_lower

    if is_yes:
        successes = btts_count
    else:
        successes = data.n - btts_count

    details = {
        "btts_yes_pct": round(btts_count / data.n * 100, 2),
        "btts_no_pct": round((data.n - btts_count) / data.n * 100, 2),
        "home_clean_sheet_pct": round(int(np.sum(data.goals_away == 0)) / data.n * 100, 2),
        "away_clean_sheet_pct": round(int(np.sum(data.goals_home == 0)) / data.n * 100, 2),
    }
    return successes, details


def _eval_corners(
    data: SimulatedMatchData,
    selection: str,
    home_team: str,
    away_team: str,
) -> Tuple[int, Dict]:
    """Total corners over/under, or team-specific corners."""
    line = _parse_line_from_selection(selection)
    if line is None:
        logger.warning("Could not parse corners line from '%s'. Using 9.5.", selection)
        line = 9.5

    # Check if team-specific or total
    side = _identify_team_in_selection(selection, home_team, away_team)
    is_over = _is_over_selection(selection)

    if side == "home":
        corners = data.corners_home
    elif side == "away":
        corners = data.corners_away
    else:
        corners = data.corners_home + data.corners_away

    if is_over:
        successes = int(np.sum(corners > line))
    else:
        successes = int(np.sum(corners < line))

    details = {
        "line": line,
        "direction": "over" if is_over else "under",
        "scope": side if side else "total",
        "avg_corners_home": round(float(data.corners_home.mean()), 2),
        "avg_corners_away": round(float(data.corners_away.mean()), 2),
        "avg_corners_total": round(float((data.corners_home + data.corners_away).mean()), 2),
    }
    return successes, details


def _eval_cards(
    data: SimulatedMatchData,
    selection: str,
    home_team: str,
    away_team: str,
) -> Tuple[int, Dict]:
    """Total cards over/under, or team-specific cards."""
    line = _parse_line_from_selection(selection)
    if line is None:
        logger.warning("Could not parse cards line from '%s'. Using 3.5.", selection)
        line = 3.5

    side = _identify_team_in_selection(selection, home_team, away_team)
    is_over = _is_over_selection(selection)

    if side == "home":
        cards = data.cards_home
    elif side == "away":
        cards = data.cards_away
    else:
        cards = data.cards_home + data.cards_away

    if is_over:
        successes = int(np.sum(cards > line))
    else:
        successes = int(np.sum(cards < line))

    details = {
        "line": line,
        "direction": "over" if is_over else "under",
        "scope": side if side else "total",
        "avg_cards_home": round(float(data.cards_home.mean()), 2),
        "avg_cards_away": round(float(data.cards_away.mean()), 2),
        "avg_cards_total": round(float((data.cards_home + data.cards_away).mean()), 2),
    }
    return successes, details


def _eval_double_chance(
    data: SimulatedMatchData,
    selection: str,
    home_team: str,
    away_team: str,
) -> Tuple[int, Dict]:
    """Double Chance: 1X, X2, or 12."""
    home_wins = data.goals_home > data.goals_away
    draws = data.goals_home == data.goals_away
    away_wins = data.goals_home < data.goals_away

    sel_lower = _normalize_str(selection)
    home_lower = _normalize_str(home_team)
    away_lower = _normalize_str(away_team)

    # Parse the selection
    has_home = home_lower in sel_lower or "local" in sel_lower or "1" in sel_lower
    has_away = away_lower in sel_lower or "visitante" in sel_lower or "2" in sel_lower
    has_draw = "empate" in sel_lower or "draw" in sel_lower or "x" in sel_lower

    if has_home and has_draw:
        # 1X: Home or Draw
        successes = int(np.sum(home_wins | draws))
        dc_type = "1X"
    elif has_away and has_draw:
        # X2: Away or Draw
        successes = int(np.sum(away_wins | draws))
        dc_type = "X2"
    elif has_home and has_away:
        # 12: Home or Away (no draw)
        successes = int(np.sum(home_wins | away_wins))
        dc_type = "12"
    else:
        # Fallback: try "1X" pattern from selection
        if "1x" in sel_lower or "1 x" in sel_lower:
            successes = int(np.sum(home_wins | draws))
            dc_type = "1X"
        elif "x2" in sel_lower or "x 2" in sel_lower:
            successes = int(np.sum(away_wins | draws))
            dc_type = "X2"
        elif "12" in sel_lower or "1 2" in sel_lower:
            successes = int(np.sum(home_wins | away_wins))
            dc_type = "12"
        else:
            logger.warning("Could not parse double_chance selection: '%s'. Defaulting to 1X.", selection)
            successes = int(np.sum(home_wins | draws))
            dc_type = "1X"

    details = {
        "dc_type": dc_type,
        "home_win_pct": round(int(np.sum(home_wins)) / data.n * 100, 2),
        "draw_pct": round(int(np.sum(draws)) / data.n * 100, 2),
        "away_win_pct": round(int(np.sum(away_wins)) / data.n * 100, 2),
    }
    return successes, details


def _eval_draw_no_bet(
    data: SimulatedMatchData,
    selection: str,
    home_team: str,
    away_team: str,
) -> Tuple[int, Dict]:
    """
    Draw No Bet: P(team wins) / (1 - P(draw)).

    Draws are voided (push), so we only count decisive results.
    """
    non_draws = data.goals_home != data.goals_away
    n_decisive = int(np.sum(non_draws))

    if n_decisive == 0:
        return 0, {"note": "All simulations were draws", "draw_pct": 100.0}

    home_wins_decisive = int(np.sum((data.goals_home > data.goals_away) & non_draws))
    away_wins_decisive = int(np.sum((data.goals_home < data.goals_away) & non_draws))

    side = _identify_team_in_selection(selection, home_team, away_team)

    if side == "home":
        successes = home_wins_decisive
    elif side == "away":
        successes = away_wins_decisive
    else:
        logger.warning("Could not parse draw_no_bet selection: '%s'. Defaulting to home.", selection)
        successes = home_wins_decisive

    # Report probability over decisive results only
    details = {
        "draw_pct": round((data.n - n_decisive) / data.n * 100, 2),
        "home_win_given_decisive": round(home_wins_decisive / max(n_decisive, 1) * 100, 2),
        "away_win_given_decisive": round(away_wins_decisive / max(n_decisive, 1) * 100, 2),
        "n_decisive": n_decisive,
    }
    # For DNB, we report probability over ALL sims (draw = push, counted as half)
    # But for successes counting, use the decisive denominator
    # The mc_probability will be successes / n_decisive * 100, BUT we want it
    # relative to all sims. DNB odds already account for draws being voided.
    # So: P(win DNB) = P(win) / (1 - P(draw)), but for MC we count:
    # successes out of n_simulations where draw = success (push = money back)
    return successes, details


def _eval_handicap(
    data: SimulatedMatchData,
    selection: str,
    home_team: str,
    away_team: str,
) -> Tuple[int, Dict]:
    """European Handicap / Spread. Applies a goal handicap to one team."""
    line = _parse_line_from_selection(selection)
    if line is None:
        logger.warning("Could not parse handicap line from '%s'. Using 0.", selection)
        line = 0.0

    side = _identify_team_in_selection(selection, home_team, away_team)
    goal_diff = data.goals_home.astype(float) - data.goals_away.astype(float)

    if side == "away":
        # Away team gets the handicap: adjusted_diff for away = -goal_diff + line
        adjusted = -goal_diff + line
    else:
        # Home team gets the handicap (default)
        adjusted = goal_diff + line

    successes = int(np.sum(adjusted > 0))

    details = {
        "handicap_line": line,
        "team": side or "home",
        "avg_goal_diff": round(float(goal_diff.mean()), 2),
        "cover_pct": round(successes / data.n * 100, 2),
    }
    return successes, details


def _eval_asian_handicap(
    data: SimulatedMatchData,
    selection: str,
    home_team: str,
    away_team: str,
) -> Tuple[int, Dict]:
    """
    Asian Handicap: supports whole, half, and quarter lines.

    Quarter lines (e.g., -0.25) are split into two half-stakes:
        -0.25 = half on 0, half on -0.5
    """
    line = _parse_line_from_selection(selection)
    if line is None:
        logger.warning("Could not parse asian_handicap line from '%s'. Using 0.", selection)
        line = 0.0

    side = _identify_team_in_selection(selection, home_team, away_team)
    goal_diff = data.goals_home.astype(float) - data.goals_away.astype(float)

    if side == "away":
        goal_diff = -goal_diff

    # Check if it's a quarter line (fractional part is 0.25 or 0.75)
    frac = abs(line) % 0.5
    is_quarter = abs(frac - 0.25) < 0.01 or abs(frac - 0.0) > 0.01

    if abs(line % 0.5) > 0.01 and abs(line % 0.5 - 0.25) < 0.01:
        # Quarter line: split into two lines
        line_a = math.floor(line * 2) / 2  # round down to nearest 0.5
        line_b = math.ceil(line * 2) / 2   # round up to nearest 0.5

        adjusted_a = goal_diff + line_a
        adjusted_b = goal_diff + line_b

        # Half stake on each. Win = +1, push = 0, lose = -1
        wins_a = np.sum(adjusted_a > 0)
        pushes_a = np.sum(adjusted_a == 0)
        wins_b = np.sum(adjusted_b > 0)
        pushes_b = np.sum(adjusted_b == 0)

        # "Success" = win full or win half
        # Full win: both legs win
        # Half win: one leg wins, other pushes
        # We count equivalent successes for probability
        equivalent_successes = (wins_a + pushes_a * 0.5 + wins_b + pushes_b * 0.5) / 2
        successes = int(round(equivalent_successes))
    else:
        # Standard half or whole line
        adjusted = goal_diff + line
        if line % 1.0 == 0:
            # Whole number: push possible
            wins = int(np.sum(adjusted > 0))
            pushes = int(np.sum(adjusted == 0))
            successes = wins + pushes // 2  # push = half refund
        else:
            # Half line: no push possible
            successes = int(np.sum(adjusted > 0))

    details = {
        "asian_handicap_line": line,
        "team": side or "home",
        "avg_goal_diff": round(float((data.goals_home - data.goals_away).mean()), 2),
    }
    return successes, details


def _eval_first_goal(
    data: SimulatedMatchData,
    selection: str,
    home_team: str,
    away_team: str,
) -> Tuple[int, Dict]:
    """
    First goal market.

    Supports:
        - "Antes del minuto 30" (first goal before minute 30)
        - "Después del minuto 60" (after minute 60)
        - Team to score first
        - Minute ranges
    """
    sel_lower = _normalize_str(selection)
    line = _parse_line_from_selection(selection)

    has_goals = (data.goals_home + data.goals_away) > 0

    if "antes" in sel_lower or "before" in sel_lower:
        # First goal before minute X
        minute = line if line and line > 0 else 30.0
        successes = int(np.sum(has_goals & (data.first_goal_time <= minute)))
    elif "despues" in sel_lower or "after" in sel_lower:
        # First goal after minute X
        minute = line if line and line > 0 else 60.0
        successes = int(np.sum(has_goals & (data.first_goal_time > minute)))
    elif "no gol" in sel_lower or "no goal" in sel_lower or "sin gol" in sel_lower:
        successes = int(np.sum(~has_goals))
    else:
        # Team to score first — approximate by who scored more in first half
        side = _identify_team_in_selection(selection, home_team, away_team)
        if side == "home":
            successes = int(np.sum(
                has_goals & (data.goals_home_ht > data.goals_away_ht)
            ))
            # Add cases where HT is tied but full-time home scored
            ht_tied = data.goals_home_ht == data.goals_away_ht
            successes += int(np.sum(
                has_goals & ht_tied & (data.goals_home > 0)
            )) // 2  # rough approximation
        elif side == "away":
            successes = int(np.sum(
                has_goals & (data.goals_away_ht > data.goals_home_ht)
            ))
            ht_tied = data.goals_home_ht == data.goals_away_ht
            successes += int(np.sum(
                has_goals & ht_tied & (data.goals_away > 0)
            )) // 2
        else:
            # Default: first goal before half time
            successes = int(np.sum(has_goals & (data.first_goal_time <= 45.0)))

    details = {
        "pct_games_with_goals": round(int(np.sum(has_goals)) / data.n * 100, 2),
        "avg_first_goal_minute": round(float(data.first_goal_time[has_goals].mean()), 1) if has_goals.sum() > 0 else None,
        "median_first_goal_minute": round(float(np.median(data.first_goal_time[has_goals])), 1) if has_goals.sum() > 0 else None,
    }
    return successes, details


def _eval_half_time(
    data: SimulatedMatchData,
    selection: str,
    home_team: str,
    away_team: str,
) -> Tuple[int, Dict]:
    """
    Half-time result / over-under.

    Supports:
        - HT winner: "Argentina al descanso"
        - HT over/under: "Más de 0.5 al descanso"
        - HT/FT: "Argentina/Argentina" (not fully implemented here, simplified)
    """
    sel_lower = _normalize_str(selection)

    # Check if it's a totals sub-market
    if _is_over_selection(selection) or _is_under_selection(selection):
        line = _parse_line_from_selection(selection)
        if line is None:
            line = 0.5
        total_ht = data.goals_home_ht + data.goals_away_ht
        if _is_over_selection(selection):
            successes = int(np.sum(total_ht > line))
        else:
            successes = int(np.sum(total_ht < line))
    else:
        # HT winner
        side = _identify_team_in_selection(selection, home_team, away_team)
        home_ht_wins = data.goals_home_ht > data.goals_away_ht
        away_ht_wins = data.goals_away_ht > data.goals_home_ht
        ht_draws = data.goals_home_ht == data.goals_away_ht

        if side == "home":
            successes = int(np.sum(home_ht_wins))
        elif side == "away":
            successes = int(np.sum(away_ht_wins))
        elif side == "draw":
            successes = int(np.sum(ht_draws))
        else:
            # Default to draw at HT (most common for fijini)
            logger.warning("Could not parse half_time selection: '%s'. Defaulting to HT draw.", selection)
            successes = int(np.sum(ht_draws))

    details = {
        "ht_home_win_pct": round(int(np.sum(data.goals_home_ht > data.goals_away_ht)) / data.n * 100, 2),
        "ht_draw_pct": round(int(np.sum(data.goals_home_ht == data.goals_away_ht)) / data.n * 100, 2),
        "ht_away_win_pct": round(int(np.sum(data.goals_away_ht > data.goals_home_ht)) / data.n * 100, 2),
        "avg_ht_goals": round(float((data.goals_home_ht + data.goals_away_ht).mean()), 2),
    }
    return successes, details


def _eval_shots_on_target(
    data: SimulatedMatchData,
    selection: str,
    home_team: str,
    away_team: str,
) -> Tuple[int, Dict]:
    """Shots on target: total or team-specific, over/under."""
    line = _parse_line_from_selection(selection)
    if line is None:
        logger.warning("Could not parse SOT line from '%s'. Using 8.5.", selection)
        line = 8.5

    side = _identify_team_in_selection(selection, home_team, away_team)
    is_over = _is_over_selection(selection)

    if side == "home":
        sot = data.sot_home
    elif side == "away":
        sot = data.sot_away
    else:
        sot = data.sot_home + data.sot_away

    if is_over:
        successes = int(np.sum(sot > line))
    else:
        successes = int(np.sum(sot < line))

    details = {
        "line": line,
        "direction": "over" if is_over else "under",
        "scope": side if side else "total",
        "avg_sot_home": round(float(data.sot_home.mean()), 2),
        "avg_sot_away": round(float(data.sot_away.mean()), 2),
        "avg_sot_total": round(float((data.sot_home + data.sot_away).mean()), 2),
    }
    return successes, details


# ---------------------------------------------------------------------------
# Market evaluator registry
# ---------------------------------------------------------------------------
_MARKET_EVALUATORS = {
    "h2h": _eval_h2h,
    "1x2": _eval_h2h,
    "match_winner": _eval_h2h,
    "ganador": _eval_h2h,
    "totals": _eval_totals,
    "total_goals": _eval_totals,
    "over_under": _eval_totals,
    "goles": _eval_totals,
    "btts": _eval_btts,
    "ambos_anotan": _eval_btts,
    "both_teams_to_score": _eval_btts,
    "corners": _eval_corners,
    "corner": _eval_corners,
    "córners": _eval_corners,
    "tiros_de_esquina": _eval_corners,
    "cards": _eval_cards,
    "tarjetas": _eval_cards,
    "yellow_cards": _eval_cards,
    "double_chance": _eval_double_chance,
    "doble_oportunidad": _eval_double_chance,
    "draw_no_bet": _eval_draw_no_bet,
    "empate_no_apuesta": _eval_draw_no_bet,
    "handicap": _eval_handicap,
    "spreads": _eval_handicap,
    "european_handicap": _eval_handicap,
    "asian_handicap": _eval_asian_handicap,
    "handicap_asiatico": _eval_asian_handicap,
    "first_goal": _eval_first_goal,
    "primer_gol": _eval_first_goal,
    "half_time": _eval_half_time,
    "halftime": _eval_half_time,
    "descanso": _eval_half_time,
    "resultado_descanso": _eval_half_time,
    "shots_on_target": _eval_shots_on_target,
    "tiros_al_arco": _eval_shots_on_target,
    "remates": _eval_shots_on_target,
}


def _get_evaluator(market_key: str):
    """Look up the market evaluator function, with fuzzy matching."""
    key = market_key.lower().strip().replace(" ", "_").replace("-", "_")

    if key in _MARKET_EVALUATORS:
        return _MARKET_EVALUATORS[key]

    # Fuzzy search
    for registered_key, func in _MARKET_EVALUATORS.items():
        if registered_key in key or key in registered_key:
            return func

    logger.warning("Unknown market_key '%s'. Falling back to h2h.", market_key)
    return _eval_h2h


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def simulate_fijini(
    home_team: str,
    away_team: str,
    market_key: str,
    selection: str,
    price: float,
    n_simulations: int = 10_000,
) -> dict:
    """
    Simulate a single fijini bet using Monte Carlo methods.

    Parameters
    ----------
    home_team : str
        Home team name in Spanish (e.g., "Argentina").
    away_team : str
        Away team name in Spanish (e.g., "Francia").
    market_key : str
        Market type identifier (e.g., "h2h", "totals", "btts", "corners").
    selection : str
        The specific bet selection (e.g., "Más de 2.5", "Argentina", "Sí").
    price : float
        Decimal odds (e.g., 1.18).
    n_simulations : int
        Number of Monte Carlo simulations (default 10,000).

    Returns
    -------
    dict
        {
            "mc_probability": float,          # Monte Carlo estimated probability (0-100)
            "implied_probability": float,      # From odds: (1/price)*100
            "edge": float,                     # mc_prob - implied_prob
            "value_rating": str,               # "GREEN" / "YELLOW" / "ORANGE" / "RED"
            "confidence_interval_95": [float, float],  # Wilson score interval
            "recommendation": str,             # "BET" / "SKIP" / "CAUTION"
            "sim_details": dict,               # Market-specific details
            "n_simulations": int,
        }
    """
    try:
        # Run simulations
        sim_data = simulate_match_arrays(home_team, away_team, n_simulations)

        # Get market evaluator
        evaluator = _get_evaluator(market_key)

        # Evaluate
        if evaluator in (_eval_h2h, _eval_corners, _eval_cards, _eval_double_chance,
                         _eval_draw_no_bet, _eval_handicap, _eval_asian_handicap,
                         _eval_first_goal, _eval_half_time, _eval_shots_on_target):
            successes, sim_details = evaluator(sim_data, selection, home_team, away_team)
        else:
            successes, sim_details = evaluator(sim_data, selection)

        # Handle draw_no_bet specially: probability is over decisive results
        if market_key.lower().replace(" ", "_").replace("-", "_") in ("draw_no_bet", "empate_no_apuesta"):
            n_decisive = sim_details.get("n_decisive", n_simulations)
            mc_prob = (successes / max(n_decisive, 1)) * 100.0 if n_decisive > 0 else 0.0
            ci = _wilson_score_interval(successes, n_decisive)
        else:
            mc_prob = (successes / n_simulations) * 100.0
            ci = _wilson_score_interval(successes, n_simulations)

        implied_prob = _implied_probability(price)
        edge = mc_prob - implied_prob

        return {
            "mc_probability": round(mc_prob, 2),
            "implied_probability": round(implied_prob, 2),
            "edge": round(edge, 2),
            "value_rating": _value_rating(edge),
            "confidence_interval_95": list(ci),
            "recommendation": _recommendation(edge, ci[0], implied_prob),
            "sim_details": sim_details,
            "n_simulations": n_simulations,
        }

    except Exception as e:
        logger.error(
            "Error simulating fijini %s/%s [%s] '%s' @ %.2f: %s",
            home_team, away_team, market_key, selection, price, e,
            exc_info=True,
        )
        implied_prob = _implied_probability(price)
        return {
            "mc_probability": 0.0,
            "implied_probability": round(implied_prob, 2),
            "edge": -implied_prob,
            "value_rating": "RED",
            "confidence_interval_95": [0.0, 0.0],
            "recommendation": "SKIP",
            "sim_details": {"error": str(e)},
            "n_simulations": 0,
        }


def simulate_match_fijinis(
    home_team: str,
    away_team: str,
    fijinis: list[dict],
    n_simulations: int = 10_000,
) -> list[dict]:
    """
    Simulate all fijinis for a single match in one batch.

    This is significantly more efficient than calling simulate_fijini() for
    each bet individually because it simulates the match ONCE and then
    evaluates every fijini against the same set of simulated results.

    Parameters
    ----------
    home_team : str
        Home team name in Spanish.
    away_team : str
        Away team name in Spanish.
    fijinis : list[dict]
        List of fijini dicts, each containing at minimum:
            - market_key: str
            - selection: str
            - price: float
    n_simulations : int
        Number of Monte Carlo simulations (default 10,000).

    Returns
    -------
    list[dict]
        List of result dicts (same format as simulate_fijini output),
        one per input fijini, in the same order.
    """
    if not fijinis:
        return []

    try:
        # Simulate the match ONCE
        sim_data = simulate_match_arrays(home_team, away_team, n_simulations)
    except Exception as e:
        logger.error(
            "Error simulating match %s vs %s: %s", home_team, away_team, e,
            exc_info=True,
        )
        # Return error results for all fijinis
        return [
            {
                "mc_probability": 0.0,
                "implied_probability": round(_implied_probability(f.get("price", 1.0)), 2),
                "edge": 0.0,
                "value_rating": "RED",
                "confidence_interval_95": [0.0, 0.0],
                "recommendation": "SKIP",
                "sim_details": {"error": str(e)},
                "n_simulations": 0,
            }
            for f in fijinis
        ]

    results = []
    for fijini in fijinis:
        market_key = fijini.get("market_key", fijini.get("market", "h2h"))
        selection = fijini.get("selection", "")
        price = fijini.get("price", 1.0)

        try:
            evaluator = _get_evaluator(market_key)

            # All evaluators that need team names
            if evaluator in (_eval_totals, _eval_btts):
                successes, sim_details = evaluator(sim_data, selection)
            else:
                successes, sim_details = evaluator(sim_data, selection, home_team, away_team)

            # Draw no bet special handling
            mk_normalized = market_key.lower().replace(" ", "_").replace("-", "_")
            if mk_normalized in ("draw_no_bet", "empate_no_apuesta"):
                n_decisive = sim_details.get("n_decisive", n_simulations)
                mc_prob = (successes / max(n_decisive, 1)) * 100.0 if n_decisive > 0 else 0.0
                ci = _wilson_score_interval(successes, n_decisive)
            else:
                mc_prob = (successes / n_simulations) * 100.0
                ci = _wilson_score_interval(successes, n_simulations)

            implied_prob = _implied_probability(price)
            edge = mc_prob - implied_prob

            results.append({
                "mc_probability": round(mc_prob, 2),
                "implied_probability": round(implied_prob, 2),
                "edge": round(edge, 2),
                "value_rating": _value_rating(edge),
                "confidence_interval_95": list(ci),
                "recommendation": _recommendation(edge, ci[0], implied_prob),
                "sim_details": sim_details,
                "n_simulations": n_simulations,
                # Passthrough original fijini data for convenience
                "market_key": market_key,
                "selection": selection,
                "price": price,
            })

        except Exception as e:
            logger.error(
                "Error evaluating fijini [%s] '%s' @ %.2f: %s",
                market_key, selection, price, e,
                exc_info=True,
            )
            implied_prob = _implied_probability(price)
            results.append({
                "mc_probability": 0.0,
                "implied_probability": round(implied_prob, 2),
                "edge": -implied_prob,
                "value_rating": "RED",
                "confidence_interval_95": [0.0, 0.0],
                "recommendation": "SKIP",
                "sim_details": {"error": str(e)},
                "n_simulations": 0,
                "market_key": market_key,
                "selection": selection,
                "price": price,
            })

    return results


# ---------------------------------------------------------------------------
# Convenience: Quick summary for a match
# ---------------------------------------------------------------------------

def match_overview(
    home_team: str,
    away_team: str,
    n_simulations: int = 10_000,
) -> dict:
    """
    Generate a quick Monte Carlo overview for a match.

    Returns key probabilities and expected stats without evaluating
    any specific bet.
    """
    sim_data = simulate_match_arrays(home_team, away_team, n_simulations)

    total_goals = sim_data.goals_home + sim_data.goals_away
    total_corners = sim_data.corners_home + sim_data.corners_away
    total_cards = sim_data.cards_home + sim_data.cards_away
    total_sot = sim_data.sot_home + sim_data.sot_away

    home_wins = int(np.sum(sim_data.goals_home > sim_data.goals_away))
    draws = int(np.sum(sim_data.goals_home == sim_data.goals_away))
    away_wins = int(np.sum(sim_data.goals_home < sim_data.goals_away))
    btts = int(np.sum((sim_data.goals_home >= 1) & (sim_data.goals_away >= 1)))

    return {
        "home_team": home_team,
        "away_team": away_team,
        "n_simulations": n_simulations,
        "probabilities": {
            "home_win": round(home_wins / n_simulations * 100, 2),
            "draw": round(draws / n_simulations * 100, 2),
            "away_win": round(away_wins / n_simulations * 100, 2),
        },
        "expected": {
            "goals_home": round(float(sim_data.goals_home.mean()), 2),
            "goals_away": round(float(sim_data.goals_away.mean()), 2),
            "total_goals": round(float(total_goals.mean()), 2),
            "corners_total": round(float(total_corners.mean()), 2),
            "cards_total": round(float(total_cards.mean()), 2),
            "sot_total": round(float(total_sot.mean()), 2),
        },
        "btts_pct": round(btts / n_simulations * 100, 2),
        "over_2_5_pct": round(int(np.sum(total_goals > 2.5)) / n_simulations * 100, 2),
        "over_1_5_pct": round(int(np.sum(total_goals > 1.5)) / n_simulations * 100, 2),
        "lambdas": {
            "home": round(sim_data.lam_home, 3),
            "away": round(sim_data.lam_away, 3),
        },
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    print("=" * 70)
    print("  FIJINI SIMULATOR — Monte Carlo Bet Evaluator")
    print("  FIFA World Cup 2026")
    print("=" * 70)

    # Demo: Match overview
    print("\n── Match Overview: Argentina vs Francia ──")
    overview = match_overview("Argentina", "Francia", n_simulations=10_000)
    print(f"  Win Argentina: {overview['probabilities']['home_win']:.1f}%")
    print(f"  Draw:          {overview['probabilities']['draw']:.1f}%")
    print(f"  Win Francia:   {overview['probabilities']['away_win']:.1f}%")
    print(f"  Expected goals: {overview['expected']['goals_home']:.2f} - {overview['expected']['goals_away']:.2f}")
    print(f"  BTTS:          {overview['btts_pct']:.1f}%")
    print(f"  Over 2.5:      {overview['over_2_5_pct']:.1f}%")
    print(f"  Corners:       {overview['expected']['corners_total']:.1f}")
    print(f"  Cards:         {overview['expected']['cards_total']:.1f}")

    # Demo: Individual fijini
    print("\n── Single Fijini: Argentina wins @ 1.22 ──")
    result = simulate_fijini(
        "Argentina", "Francia",
        market_key="h2h",
        selection="Argentina",
        price=1.22,
    )
    print(f"  MC Probability:    {result['mc_probability']:.1f}%")
    print(f"  Implied Prob:      {result['implied_probability']:.1f}%")
    print(f"  Edge:              {result['edge']:+.1f}%")
    print(f"  Value:             {result['value_rating']}")
    print(f"  95% CI:            [{result['confidence_interval_95'][0]:.1f}%, {result['confidence_interval_95'][1]:.1f}%]")
    print(f"  Recommendation:    {result['recommendation']}")

    # Demo: Batch fijinis for one match
    print("\n── Batch Fijinis: México vs Estados Unidos ──")
    batch_fijinis = [
        {"market_key": "h2h", "selection": "México", "price": 1.25},
        {"market_key": "totals", "selection": "Más de 1.5", "price": 1.18},
        {"market_key": "btts", "selection": "Sí", "price": 1.30},
        {"market_key": "corners", "selection": "Más de 8.5", "price": 1.20},
        {"market_key": "cards", "selection": "Más de 3.5", "price": 1.15},
        {"market_key": "double_chance", "selection": "México o Empate", "price": 1.10},
        {"market_key": "draw_no_bet", "selection": "México", "price": 1.15},
        {"market_key": "handicap", "selection": "México +1.5", "price": 1.12},
        {"market_key": "half_time", "selection": "Empate", "price": 1.28},
        {"market_key": "shots_on_target", "selection": "Más de 7.5", "price": 1.22},
    ]

    batch_results = simulate_match_fijinis("México", "Estados Unidos", batch_fijinis)

    print(f"  {'Market':<20} {'Selection':<22} {'Price':>6} {'MC%':>7} {'Impl%':>7} {'Edge':>7} {'Rating':<8} {'Rec':<8}")
    print(f"  {'─'*20} {'─'*22} {'─'*6} {'─'*7} {'─'*7} {'─'*7} {'─'*8} {'─'*8}")
    for r in batch_results:
        print(
            f"  {r['market_key']:<20} {r['selection']:<22} {r['price']:>6.2f} "
            f"{r['mc_probability']:>6.1f}% {r['implied_probability']:>6.1f}% "
            f"{r['edge']:>+6.1f}% {r['value_rating']:<8} {r['recommendation']:<8}"
        )

    print()
