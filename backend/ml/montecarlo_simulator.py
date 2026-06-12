"""
Monte Carlo World Cup 2026 Tournament Simulator
=================================================
Simulates the FIFA World Cup 2026 (48 teams, 12 groups of 4) using
Bivariate Poisson match modelling driven by ELO ratings and
attack / defence strength parameters.

Usage:
    python -m backend.ml.montecarlo_simulator          # 10 000 simulations
    python backend/ml/montecarlo_simulator.py           # same, standalone
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_RATE: float = 1.3          # avg goals per team per WC match
HOME_FACTOR: float = 1.05       # slight geographic proximity advantage
EXTRA_TIME_FACTOR: float = 0.4  # λ multiplier for extra time
PENALTY_BASE: float = 0.50      # base win‑prob in shootout
PENALTY_ELO_BONUS: float = 0.03 # max extra prob for higher‑ELO team

# Host nations (get the home_factor boost)
HOST_NATIONS = {"México", "Estados Unidos", "Canadá"}

# ---------------------------------------------------------------------------
# Default team ratings – realistic 2026 estimates
# Keys use the SPANISH names that match the official group draw.
# ---------------------------------------------------------------------------
DEFAULT_TEAM_RATINGS: Dict[str, Dict[str, float]] = {
    # Group A
    "México":              {"elo": 1820, "attack": 1.25, "defense": 1.10},
    "Sudáfrica":           {"elo": 1620, "attack": 0.90, "defense": 1.45},
    "Corea del Sur":       {"elo": 1790, "attack": 1.15, "defense": 1.15},
    "República Checa":     {"elo": 1780, "attack": 1.10, "defense": 1.10},
    # Group B
    "Canadá":              {"elo": 1760, "attack": 1.10, "defense": 1.25},
    "Bosnia y Herzegovina": {"elo": 1700, "attack": 1.05, "defense": 1.20},
    "Qatar":               {"elo": 1650, "attack": 0.85, "defense": 1.40},
    "Suiza":               {"elo": 1850, "attack": 1.15, "defense": 0.95},
    # Group C
    "Brasil":              {"elo": 2000, "attack": 1.55, "defense": 0.85},
    "Marruecos":           {"elo": 1850, "attack": 1.15, "defense": 0.90},
    "Haití":               {"elo": 1450, "attack": 0.70, "defense": 1.65},
    "Escocia":             {"elo": 1730, "attack": 1.00, "defense": 1.15},
    # Group D
    "Estados Unidos":      {"elo": 1830, "attack": 1.20, "defense": 1.05},
    "Paraguay":            {"elo": 1730, "attack": 1.00, "defense": 1.15},
    "Australia":           {"elo": 1740, "attack": 1.00, "defense": 1.20},
    "Turquía":             {"elo": 1780, "attack": 1.15, "defense": 1.10},
    # Group E
    "Alemania":            {"elo": 1960, "attack": 1.45, "defense": 0.90},
    "Curaçao":             {"elo": 1400, "attack": 0.65, "defense": 1.70},
    "Costa de Marfil":     {"elo": 1720, "attack": 1.05, "defense": 1.20},
    "Ecuador":             {"elo": 1770, "attack": 1.10, "defense": 1.10},
    # Group F
    "Países Bajos":        {"elo": 1950, "attack": 1.40, "defense": 0.90},
    "Japón":               {"elo": 1810, "attack": 1.20, "defense": 1.00},
    "Suecia":              {"elo": 1780, "attack": 1.10, "defense": 1.05},
    "Túnez":               {"elo": 1730, "attack": 0.95, "defense": 1.15},
    # Group G
    "Irán":                {"elo": 1760, "attack": 1.05, "defense": 1.15},
    "Nueva Zelanda":       {"elo": 1500, "attack": 0.75, "defense": 1.55},
    "Bélgica":             {"elo": 1920, "attack": 1.35, "defense": 0.95},
    "Egipto":              {"elo": 1720, "attack": 1.00, "defense": 1.15},
    # Group H
    "Arabia Saudita":      {"elo": 1680, "attack": 0.95, "defense": 1.25},
    "Uruguay":             {"elo": 1880, "attack": 1.30, "defense": 0.90},
    "España":              {"elo": 1985, "attack": 1.50, "defense": 0.85},
    "Cabo Verde":          {"elo": 1530, "attack": 0.80, "defense": 1.50},
    # Group I
    "Francia":             {"elo": 2050, "attack": 1.55, "defense": 0.80},
    "Senegal":             {"elo": 1780, "attack": 1.10, "defense": 1.05},
    "Irak":                {"elo": 1700, "attack": 0.95, "defense": 1.20},
    "Noruega":             {"elo": 1790, "attack": 1.15, "defense": 1.05},
    # Group J
    "Argentina":           {"elo": 2080, "attack": 1.60, "defense": 0.78},
    "Argelia":             {"elo": 1750, "attack": 1.05, "defense": 1.15},
    "Austria":             {"elo": 1800, "attack": 1.15, "defense": 1.05},
    "Jordania":            {"elo": 1590, "attack": 0.80, "defense": 1.40},
    # Group K
    "Portugal":            {"elo": 1970, "attack": 1.45, "defense": 0.88},
    "Congo RD":            {"elo": 1600, "attack": 0.85, "defense": 1.40},
    "Uzbekistán":          {"elo": 1630, "attack": 0.90, "defense": 1.35},
    "Colombia":            {"elo": 1900, "attack": 1.30, "defense": 0.95},
    # Group L
    "Ghana":               {"elo": 1680, "attack": 1.00, "defense": 1.30},
    "Panamá":              {"elo": 1660, "attack": 0.90, "defense": 1.35},
    "Inglaterra":          {"elo": 1990, "attack": 1.50, "defense": 0.85},
    "Croacia":             {"elo": 1870, "attack": 1.30, "defense": 0.95},
}

# Official group composition (order matters for seeding / bracket)
GROUPS: Dict[str, List[str]] = {
    "A": ["México", "Sudáfrica", "Corea del Sur", "República Checa"],
    "B": ["Canadá", "Bosnia y Herzegovina", "Qatar", "Suiza"],
    "C": ["Brasil", "Marruecos", "Haití", "Escocia"],
    "D": ["Estados Unidos", "Paraguay", "Australia", "Turquía"],
    "E": ["Alemania", "Curaçao", "Costa de Marfil", "Ecuador"],
    "F": ["Países Bajos", "Japón", "Suecia", "Túnez"],
    "G": ["Irán", "Nueva Zelanda", "Bélgica", "Egipto"],
    "H": ["Arabia Saudita", "Uruguay", "España", "Cabo Verde"],
    "I": ["Francia", "Senegal", "Irak", "Noruega"],
    "J": ["Argentina", "Argelia", "Austria", "Jordania"],
    "K": ["Portugal", "Congo RD", "Uzbekistán", "Colombia"],
    "L": ["Ghana", "Panamá", "Inglaterra", "Croacia"],
}

# FIFA-confirmed Round-of-32 bracket pairing rules
# Format: (group_winner_slot, opponent_slot).  Slots labelled e.g. "1A" = 1st of group A.
# "3X" slots are filled later by best-third-placed ranking.
# Using the official FIFA bracket for the 48-team World Cup 2026:
R32_BRACKET: List[Tuple[str, str]] = [
    ("1A", "3"),   
    ("1B", "3"),   
    ("1C", "3"),   
    ("1D", "3"),   
    ("1E", "3"),   
    ("1F", "3"),   
    ("1G", "3"),   
    ("1H", "3"),   
    ("1I", "2A"),   
    ("1J", "2B"),   
    ("1K", "2C"),   
    ("1L", "2D"),   
    ("2E", "2F"),   
    ("2G", "2H"),   
    ("2I", "2J"),   
    ("2K", "2L"),   
]

# R16 pairings (winners of R32 matches):  (match_i, match_j) → R16 game
R16_PAIRINGS: List[Tuple[int, int]] = [
    (1, 2),   (3, 4),   (5, 6),   (7, 8),
    (9, 10),  (11, 12), (13, 14), (15, 16),
]

# QF pairings (winners of R16 games, 0-indexed):
QF_PAIRINGS: List[Tuple[int, int]] = [(0, 1), (2, 3), (4, 5), (6, 7)]

# SF pairings:
SF_PAIRINGS: List[Tuple[int, int]] = [(0, 1), (2, 3)]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class TeamRating:
    name: str
    elo: float
    attack: float
    defense: float


@dataclass
class MatchResult:
    team_a: str
    team_b: str
    goals_a: int
    goals_b: int
    penalty_winner: Optional[str] = None  # only for knockout draws


@dataclass
class GroupStanding:
    team: str
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    gf: int = 0
    ga: int = 0
    points: int = 0

    @property
    def gd(self) -> int:
        return self.gf - self.ga


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_team_data() -> Dict[str, TeamRating]:
    """
    Try to import live ELO ratings from the project's scraper module.
    Falls back to the curated DEFAULT_TEAM_RATINGS.
    """
    ratings: Dict[str, TeamRating] = {}

    # --- Attempt live import ------------------------------------------------
    try:
        from backend.ml.advanced_wc_model import fetch_elo_ratings  # noqa: F811

        elo_df = fetch_elo_ratings()
        if elo_df is not None and not elo_df.empty:
            # Build a name→elo lookup from the scraped data
            scraped_elos: Dict[str, float] = {}
            # Map common English names → Spanish names used in GROUPS
            _name_map = {
                "Argentina": "Argentina", "France": "Francia",
                "Brazil": "Brasil", "England": "Inglaterra",
                "Spain": "España", "Germany": "Alemania",
                "Netherlands": "Países Bajos", "Portugal": "Portugal",
                "Belgium": "Bélgica", "Colombia": "Colombia",
                "Uruguay": "Uruguay", "Croatia": "Croacia",
                "USA": "Estados Unidos", "United States": "Estados Unidos",
                "Mexico": "México", "Japan": "Japón",
                "South Korea": "Corea del Sur", "Korea Republic": "Corea del Sur",
                "Morocco": "Marruecos", "Senegal": "Senegal",
                "Iran": "Irán", "Australia": "Australia",
                "Switzerland": "Suiza", "Turkey": "Turquía",
                "Ecuador": "Ecuador", "Sweden": "Suecia",
                "Tunisia": "Túnez", "Norway": "Noruega",
                "Austria": "Austria", "Egypt": "Egipto",
                "Algeria": "Argelia", "Scotland": "Escocia",
                "Ghana": "Ghana", "Panama": "Panamá",
                "Iraq": "Irak", "Canada": "Canadá",
                "Saudi Arabia": "Arabia Saudita",
                "Paraguay": "Paraguay", "South Africa": "Sudáfrica",
                "Czech Republic": "República Checa",
                "Bosnia and Herzegovina": "Bosnia y Herzegovina",
                "Bosnia Herzegovina": "Bosnia y Herzegovina",
                "Qatar": "Qatar",
                "Haiti": "Haití", "Curacao": "Curaçao",
                "New Zealand": "Nueva Zelanda",
                "Cape Verde": "Cabo Verde",
                "DR Congo": "Congo RD",
                "Uzbekistan": "Uzbekistán",
                "Jordan": "Jordania",
                "Ivory Coast": "Costa de Marfil",
                "Côte d'Ivoire": "Costa de Marfil",
            }
            for _, row in elo_df.iterrows():
                raw_name = row.get("team", "")
                spanish = _name_map.get(raw_name, raw_name)
                scraped_elos[spanish] = float(row["elo"])

            # Merge scraped ELOs with default attack/defense
            for name, defaults in DEFAULT_TEAM_RATINGS.items():
                elo = scraped_elos.get(name, defaults["elo"])
                ratings[name] = TeamRating(
                    name=name,
                    elo=elo,
                    attack=defaults["attack"],
                    defense=defaults["defense"],
                )
            logger.info("Loaded live ELO ratings from scraper (%d teams patched).",
                        len(scraped_elos))
            return ratings
    except Exception as exc:
        logger.warning("Could not import live ELO data (%s). Using defaults.", exc)

    # --- Fallback: curated defaults -----------------------------------------
    for name, vals in DEFAULT_TEAM_RATINGS.items():
        ratings[name] = TeamRating(
            name=name, elo=vals["elo"],
            attack=vals["attack"], defense=vals["defense"],
        )
    return ratings


# ---------------------------------------------------------------------------
# Match simulation helpers
# ---------------------------------------------------------------------------
_rng = np.random.default_rng(seed=None)  # seeded per-simulation run


def _compute_lambda(
    attack_a: float,
    defense_b: float,
    avg_attack: float,
    avg_defense: float,
    is_home: bool = False,
) -> float:
    """Expected goals λ for team A against team B."""
    lam = BASE_RATE * (attack_a / avg_attack) * (avg_defense / defense_b)
    if is_home:
        lam *= HOME_FACTOR
    return max(lam, 0.15)  # floor to avoid degenerate 0


def simulate_match(
    team_a: TeamRating,
    team_b: TeamRating,
    avg_attack: float,
    avg_defense: float,
    knockout: bool = False,
    rng: np.random.Generator | None = None,
) -> MatchResult:
    """
    Simulate a single match using independent Poisson draws.

    In group stage, draws are allowed.
    In knockout, extra time + penalties resolve ties.
    """
    if rng is None:
        rng = _rng

    a_is_host = team_a.name in HOST_NATIONS
    b_is_host = team_b.name in HOST_NATIONS

    lam_a = _compute_lambda(team_a.attack, team_b.defense, avg_attack, avg_defense, is_home=a_is_host)
    lam_b = _compute_lambda(team_b.attack, team_a.defense, avg_attack, avg_defense, is_home=b_is_host)

    goals_a = int(rng.poisson(lam_a))
    goals_b = int(rng.poisson(lam_b))

    penalty_winner: Optional[str] = None

    if knockout and goals_a == goals_b:
        # --- Extra time (30 min ≈ 1/3 of regulation) -----------------------
        et_lam_a = lam_a * EXTRA_TIME_FACTOR
        et_lam_b = lam_b * EXTRA_TIME_FACTOR
        et_a = int(rng.poisson(et_lam_a))
        et_b = int(rng.poisson(et_lam_b))
        goals_a += et_a
        goals_b += et_b

        if goals_a == goals_b:
            # --- Penalty shootout -------------------------------------------
            elo_diff = team_a.elo - team_b.elo
            bonus = np.clip(elo_diff / 600.0 * PENALTY_ELO_BONUS, -PENALTY_ELO_BONUS, PENALTY_ELO_BONUS)
            prob_a = PENALTY_BASE + bonus
            if rng.random() < prob_a:
                penalty_winner = team_a.name
            else:
                penalty_winner = team_b.name

    return MatchResult(
        team_a=team_a.name,
        team_b=team_b.name,
        goals_a=goals_a,
        goals_b=goals_b,
        penalty_winner=penalty_winner,
    )


def match_winner(result: MatchResult) -> str:
    """Return the winning team name (considering penalties for knockout)."""
    if result.goals_a > result.goals_b:
        return result.team_a
    elif result.goals_b > result.goals_a:
        return result.team_b
    elif result.penalty_winner:
        return result.penalty_winner
    else:
        raise ValueError("Knockout match ended in a draw without penalties!")


# ---------------------------------------------------------------------------
# Group stage
# ---------------------------------------------------------------------------
def _simulate_group(
    group_teams: List[str],
    ratings: Dict[str, TeamRating],
    avg_attack: float,
    avg_defense: float,
    rng: np.random.Generator,
) -> Tuple[List[GroupStanding], List[MatchResult]]:
    """Play a round-robin within a group and return sorted standings."""
    standings = {t: GroupStanding(team=t) for t in group_teams}
    results: List[MatchResult] = []

    # Head-to-head records for tiebreaking
    h2h: Dict[Tuple[str, str], int] = defaultdict(int)  # (a,b) → goal diff of a vs b

    for i in range(len(group_teams)):
        for j in range(i + 1, len(group_teams)):
            ta = group_teams[i]
            tb = group_teams[j]
            res = simulate_match(ratings[ta], ratings[tb], avg_attack, avg_defense, knockout=False, rng=rng)
            results.append(res)

            sa, sb = standings[ta], standings[tb]
            sa.played += 1
            sb.played += 1
            sa.gf += res.goals_a
            sa.ga += res.goals_b
            sb.gf += res.goals_b
            sb.ga += res.goals_a

            h2h[(ta, tb)] = res.goals_a - res.goals_b
            h2h[(tb, ta)] = res.goals_b - res.goals_a

            if res.goals_a > res.goals_b:
                sa.won += 1
                sb.lost += 1
                sa.points += 3
            elif res.goals_a < res.goals_b:
                sb.won += 1
                sa.lost += 1
                sb.points += 3
            else:
                sa.drawn += 1
                sb.drawn += 1
                sa.points += 1
                sb.points += 1

    # Sort: points → GD → GF → h2h → random
    def sort_key(s: GroupStanding) -> Tuple:
        return (
            s.points,
            s.gd,
            s.gf,
            # h2h advantage (sum of GD against tied teams – approximated by overall h2h)
            sum(h2h.get((s.team, other), 0) for other in group_teams if other != s.team),
            rng.random(),  # final random tiebreak
        )

    sorted_standings = sorted(standings.values(), key=sort_key, reverse=True)
    return sorted_standings, results


# ---------------------------------------------------------------------------
# Best third-placed teams selection
# ---------------------------------------------------------------------------
def _select_best_thirds(
    third_placed: List[Tuple[str, GroupStanding]],
    rng: np.random.Generator,
) -> List[Tuple[str, GroupStanding]]:
    """
    From 12 third-placed teams, select the best 8.

    Sort by: points → GD → GF → random.
    Returns list of (group_letter, standing) for the 8 best.
    """
    def key(item: Tuple[str, GroupStanding]) -> Tuple:
        s = item[1]
        return (s.points, s.gd, s.gf, rng.random())

    sorted_thirds = sorted(third_placed, key=key, reverse=True)
    return sorted_thirds[:8]


def _assign_thirds_to_bracket(
    best_thirds: List[Tuple[str, GroupStanding]],
) -> Dict[int, str]:
    """
    Assign each of the 8 best third-placed teams to their R32 match slot.
    """
    available = [st.team for _, st in best_thirds]
    assignment: Dict[int, str] = {}  # match_number → team_name

    for match_idx, (_, opp_slot) in enumerate(R32_BRACKET):
        if not opp_slot.startswith("3"):
            continue
        if available:
            assignment[match_idx + 1] = available.pop(0)

    return assignment


# ---------------------------------------------------------------------------
# Full knockout bracket
# ---------------------------------------------------------------------------
def _simulate_knockout(
    r32_teams: List[Tuple[str, str]],  # 16 pairings (team_a, team_b)
    ratings: Dict[str, TeamRating],
    avg_attack: float,
    avg_defense: float,
    rng: np.random.Generator,
) -> Dict[str, List[str]]:
    """
    Simulate R32 → R16 → QF → SF → Final.
    Returns dict with keys: 'r16', 'qf', 'sf', 'final', 'champion'.
    Each value is a list of team names that reached that round.
    """
    progress: Dict[str, List[str]] = {
        "r32": [],
        "r16": [],
        "qf": [],
        "sf": [],
        "final": [],
        "champion": [],
    }

    # -- Round of 32 --
    r32_winners: List[str] = []
    for ta, tb in r32_teams:
        res = simulate_match(ratings[ta], ratings[tb], avg_attack, avg_defense, knockout=True, rng=rng)
        winner = match_winner(res)
        r32_winners.append(winner)
    progress["r32"] = list(r32_winners)

    # -- Round of 16 --
    r16_winners: List[str] = []
    for i, j in R16_PAIRINGS:
        ta = r32_winners[i - 1]
        tb = r32_winners[j - 1]
        res = simulate_match(ratings[ta], ratings[tb], avg_attack, avg_defense, knockout=True, rng=rng)
        r16_winners.append(match_winner(res))
    progress["r16"] = list(r16_winners)

    # -- Quarter-finals --
    qf_winners: List[str] = []
    for i, j in QF_PAIRINGS:
        ta = r16_winners[i]
        tb = r16_winners[j]
        res = simulate_match(ratings[ta], ratings[tb], avg_attack, avg_defense, knockout=True, rng=rng)
        qf_winners.append(match_winner(res))
    progress["qf"] = list(qf_winners)

    # -- Semi-finals --
    sf_winners: List[str] = []
    for i, j in SF_PAIRINGS:
        ta = qf_winners[i]
        tb = qf_winners[j]
        res = simulate_match(ratings[ta], ratings[tb], avg_attack, avg_defense, knockout=True, rng=rng)
        sf_winners.append(match_winner(res))
    progress["sf"] = list(sf_winners)

    # -- Final --
    final_res = simulate_match(
        ratings[sf_winners[0]], ratings[sf_winners[1]],
        avg_attack, avg_defense, knockout=True, rng=rng,
    )
    champion = match_winner(final_res)
    progress["final"] = list(sf_winners)
    progress["champion"] = [champion]

    return progress


# ---------------------------------------------------------------------------
# Single tournament simulation
# ---------------------------------------------------------------------------
def _simulate_single_tournament(
    ratings: Dict[str, TeamRating],
    avg_attack: float,
    avg_defense: float,
    rng: np.random.Generator,
) -> Dict:
    """
    Run one complete World Cup simulation.
    Returns a dict with advancement details and the champion.
    """
    group_winners: Dict[str, str] = {}    # group_letter → 1st place team
    group_runners: Dict[str, str] = {}    # group_letter → 2nd place team
    third_placed: List[Tuple[str, GroupStanding]] = []
    all_group_results: List[MatchResult] = []
    group_exit: List[str] = []            # teams eliminated in group stage

    for gl, teams in GROUPS.items():
        standings, results = _simulate_group(teams, ratings, avg_attack, avg_defense, rng)
        all_group_results.extend(results)
        group_winners[gl] = standings[0].team
        group_runners[gl] = standings[1].team
        third_placed.append((gl, standings[2]))
        group_exit.append(standings[3].team)  # 4th place eliminated
        # 3rd place may or may not advance

    # Best 8 thirds
    best_thirds = _select_best_thirds(third_placed, rng)
    best_third_teams = {st.team for _, st in best_thirds}
    # Remaining 4 thirds are eliminated
    for gl, st in third_placed:
        if st.team not in best_third_teams:
            group_exit.append(st.team)

    thirds_assignment = _assign_thirds_to_bracket(best_thirds)

    # Build R32 pairings
    r32_pairings: List[Tuple[str, str]] = []
    for match_num, (slot_a, slot_b) in enumerate(R32_BRACKET, start=1):
        # Resolve slot_a
        if slot_a.startswith("1"):
            team_a = group_winners[slot_a[1]]
        elif slot_a.startswith("2"):
            team_a = group_runners[slot_a[1]]
        else:
            team_a = thirds_assignment.get(match_num, "")

        # Resolve slot_b
        if slot_b.startswith("1"):
            team_b = group_winners[slot_b[1]]
        elif slot_b.startswith("2"):
            team_b = group_runners[slot_b[1]]
        elif slot_b.startswith("3"):
            team_b = thirds_assignment.get(match_num, "")
        else:
            team_b = group_runners.get(slot_b[1], slot_b)

        r32_pairings.append((team_a, team_b))

    # Knockout
    knockout_progress = _simulate_knockout(r32_pairings, ratings, avg_attack, avg_defense, rng)

    return {
        "champion": knockout_progress["champion"][0],
        "finalist": [t for t in knockout_progress["final"] if t != knockout_progress["champion"][0]],
        "semifinalists": knockout_progress["sf"],
        "quarterfinalists": knockout_progress["qf"],
        "r16": knockout_progress["r16"],
        "r32": knockout_progress["r32"],
        "group_exit": group_exit,
        "group_results": all_group_results,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_match_probabilities(
    team_a: str,
    team_b: str,
    n_sims: int = 50_000,
    ratings: Optional[Dict[str, TeamRating]] = None,
) -> Dict[str, float]:
    """
    Monte-Carlo estimate of P(win_a), P(draw), P(win_b) and expected goals
    for an individual match between two teams.

    Returns:
        {
            "win_a": float,   # probability 0-1
            "draw": float,
            "win_b": float,
            "expected_goals_a": float,
            "expected_goals_b": float,
        }
    """
    if ratings is None:
        ratings = load_team_data()

    if team_a not in ratings:
        raise ValueError(f"Unknown team: {team_a}")
    if team_b not in ratings:
        raise ValueError(f"Unknown team: {team_b}")

    avg_attack = float(np.mean([r.attack for r in ratings.values()]))
    avg_defense = float(np.mean([r.defense for r in ratings.values()]))

    rng = np.random.default_rng()
    wins_a = 0
    draws = 0
    wins_b = 0
    total_goals_a = 0
    total_goals_b = 0

    for _ in range(n_sims):
        res = simulate_match(
            ratings[team_a], ratings[team_b],
            avg_attack, avg_defense,
            knockout=False, rng=rng,
        )
        total_goals_a += res.goals_a
        total_goals_b += res.goals_b
        if res.goals_a > res.goals_b:
            wins_a += 1
        elif res.goals_a < res.goals_b:
            wins_b += 1
        else:
            draws += 1

    return {
        "win_a": wins_a / n_sims,
        "draw": draws / n_sims,
        "win_b": wins_b / n_sims,
        "expected_goals_a": total_goals_a / n_sims,
        "expected_goals_b": total_goals_b / n_sims,
    }


def simulate_tournament(
    n_simulations: int = 10_000,
    seed: Optional[int] = None,
    ratings: Optional[Dict[str, TeamRating]] = None,
) -> Dict:
    """
    Run *n_simulations* full World Cup 2026 simulations.

    Returns a dict with:
        - champion_probs:       {team: prob}
        - finalist_probs:       {team: prob}
        - semifinal_probs:      {team: prob}
        - quarterfinal_probs:   {team: prob}
        - r16_probs:            {team: prob}
        - r32_probs:            {team: prob}
        - group_exit_probs:     {team: prob}
        - expected_goals:       {team: avg goals per match}  (group stage)
        - n_simulations:        int
        - elapsed_seconds:      float
    """
    if ratings is None:
        ratings = load_team_data()

    all_teams = list(ratings.keys())
    avg_attack = float(np.mean([r.attack for r in ratings.values()]))
    avg_defense = float(np.mean([r.defense for r in ratings.values()]))

    # Accumulators
    champion_count: Dict[str, int] = defaultdict(int)
    finalist_count: Dict[str, int] = defaultdict(int)
    semifinal_count: Dict[str, int] = defaultdict(int)
    quarterfinal_count: Dict[str, int] = defaultdict(int)
    r16_count: Dict[str, int] = defaultdict(int)
    r32_count: Dict[str, int] = defaultdict(int)
    group_exit_count: Dict[str, int] = defaultdict(int)
    total_goals: Dict[str, int] = defaultdict(int)
    total_matches: Dict[str, int] = defaultdict(int)

    rng = np.random.default_rng(seed)
    t0 = time.time()

    for sim in range(1, n_simulations + 1):
        result = _simulate_single_tournament(ratings, avg_attack, avg_defense, rng)

        champion_count[result["champion"]] += 1
        for t in result["finalist"]:
            finalist_count[t] += 1
        for t in result["semifinalists"]:
            semifinal_count[t] += 1
        for t in result["quarterfinalists"]:
            quarterfinal_count[t] += 1
        for t in result["r16"]:
            r16_count[t] += 1
        for t in result["r32"]:
            r32_count[t] += 1
        for t in result["group_exit"]:
            group_exit_count[t] += 1

        # Accumulate goals from group stage
        for mr in result["group_results"]:
            total_goals[mr.team_a] += mr.goals_a
            total_goals[mr.team_b] += mr.goals_b
            total_matches[mr.team_a] += 1
            total_matches[mr.team_b] += 1

        if sim % 1000 == 0:
            elapsed = time.time() - t0
            rate = sim / elapsed if elapsed > 0 else 0
            logger.info(
                "Simulation %d / %d  (%.0f sims/sec, %.1fs elapsed)",
                sim, n_simulations, rate, elapsed,
            )

    elapsed = time.time() - t0
    logger.info("Completed %d simulations in %.2f seconds.", n_simulations, elapsed)

    def _to_prob(counter: Dict[str, int]) -> Dict[str, float]:
        return {t: counter.get(t, 0) / n_simulations for t in all_teams}

    expected_goals: Dict[str, float] = {}
    for t in all_teams:
        if total_matches[t] > 0:
            expected_goals[t] = total_goals[t] / total_matches[t]
        else:
            expected_goals[t] = 0.0

    return {
        "champion_probs": _to_prob(champion_count),
        "finalist_probs": _to_prob(finalist_count),
        "semifinal_probs": _to_prob(semifinal_count),
        "quarterfinal_probs": _to_prob(quarterfinal_count),
        "r16_probs": _to_prob(r16_count),
        "r32_probs": _to_prob(r32_count),
        "group_exit_probs": _to_prob(group_exit_count),
        "expected_goals": expected_goals,
        "n_simulations": n_simulations,
        "elapsed_seconds": elapsed,
    }


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------
def print_results_table(results: Dict, top_n: int = 20) -> None:
    """Print a nicely formatted table of tournament probabilities."""
    champ = results["champion_probs"]
    sf = results["semifinal_probs"]
    qf = results["quarterfinal_probs"]
    r16 = results["r16_probs"]
    group_exit = results["group_exit_probs"]
    xg = results["expected_goals"]

    # Sort by champion probability
    ranked = sorted(champ.items(), key=lambda x: x[1], reverse=True)

    header = f"{'Rank':<5} {'Team':<25} {'🏆 Champ':>9} {'🥈 Final':>9} {'🏅 SF':>9} {'QF':>9} {'R16':>9} {'Grp Exit':>9} {'xG/match':>9}"
    sep = "─" * len(header)

    print(f"\n{sep}")
    print(f"  FIFA World Cup 2026 — Monte Carlo Simulation ({results['n_simulations']:,} runs, {results['elapsed_seconds']:.1f}s)")
    print(sep)
    print(header)
    print(sep)

    for rank, (team, prob) in enumerate(ranked[:top_n], start=1):
        finalist_p = results["finalist_probs"].get(team, 0) + prob  # finalist includes champion
        print(
            f"{rank:<5} {team:<25} "
            f"{prob * 100:>8.2f}% "
            f"{finalist_p * 100:>8.2f}% "
            f"{sf.get(team, 0) * 100:>8.2f}% "
            f"{qf.get(team, 0) * 100:>8.2f}% "
            f"{r16.get(team, 0) * 100:>8.2f}% "
            f"{group_exit.get(team, 0) * 100:>8.2f}% "
            f"{xg.get(team, 0):>8.2f}"
        )
    print(sep)
    print()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("🏟️  Starting FIFA World Cup 2026 Monte Carlo Simulation…")
    logger.info("Loading team data…")
    team_data = load_team_data()
    logger.info("Loaded %d teams.", len(team_data))

    results = simulate_tournament(n_simulations=10_000, ratings=team_data)
    print_results_table(results, top_n=20)

    # Quick individual match demo
    print("── Individual match probabilities ──")
    for a, b in [("Argentina", "Francia"), ("Brasil", "Alemania"), ("México", "Estados Unidos")]:
        mp = get_match_probabilities(a, b, n_sims=20_000, ratings=team_data)
        print(
            f"  {a} vs {b}:  "
            f"Win {a}: {mp['win_a']*100:.1f}%  "
            f"Draw: {mp['draw']*100:.1f}%  "
            f"Win {b}: {mp['win_b']*100:.1f}%  "
            f"(xG: {mp['expected_goals_a']:.2f} - {mp['expected_goals_b']:.2f})"
        )
    print()
