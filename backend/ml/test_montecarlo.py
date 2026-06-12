"""
Tests for the Monte Carlo World Cup 2026 simulator.

Run with:
    python -m pytest backend/ml/test_montecarlo.py -v
    python backend/ml/test_montecarlo.py              # standalone
"""

from __future__ import annotations

import sys
import os
import unittest
from pathlib import Path

# Ensure the project root is on sys.path so standalone execution works
_project_root = str(Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.ml.montecarlo_simulator import (
    DEFAULT_TEAM_RATINGS,
    GROUPS,
    GroupStanding,
    MatchResult,
    TeamRating,
    _compute_lambda,
    _select_best_thirds,
    _simulate_group,
    get_match_probabilities,
    load_team_data,
    match_winner,
    simulate_match,
    simulate_tournament,
)

import numpy as np


class TestTeamData(unittest.TestCase):
    """Verify that team data loading works and all 48 teams are present."""

    def test_default_ratings_has_48_teams(self):
        self.assertEqual(len(DEFAULT_TEAM_RATINGS), 48)

    def test_load_team_data_returns_48_ratings(self):
        data = load_team_data()
        self.assertEqual(len(data), 48)
        for name, rating in data.items():
            self.assertIsInstance(rating, TeamRating)
            self.assertGreater(rating.elo, 1000)
            self.assertGreater(rating.attack, 0)
            self.assertGreater(rating.defense, 0)

    def test_groups_contain_all_48_teams(self):
        all_teams = set()
        for teams in GROUPS.values():
            all_teams.update(teams)
        self.assertEqual(len(all_teams), 48)
        # Every team in groups must be in DEFAULT_TEAM_RATINGS
        for t in all_teams:
            self.assertIn(t, DEFAULT_TEAM_RATINGS, f"Team '{t}' missing from ratings")


class TestMatchSimulation(unittest.TestCase):
    """Test individual match simulation produces valid results."""

    def setUp(self):
        self.ratings = load_team_data()
        attacks = [r.attack for r in self.ratings.values()]
        defenses = [r.defense for r in self.ratings.values()]
        self.avg_attack = float(np.mean(attacks))
        self.avg_defense = float(np.mean(defenses))
        self.rng = np.random.default_rng(42)

    def test_group_match_returns_valid_scores(self):
        res = simulate_match(
            self.ratings["Argentina"],
            self.ratings["Jordania"],
            self.avg_attack, self.avg_defense,
            knockout=False, rng=self.rng,
        )
        self.assertIsInstance(res, MatchResult)
        self.assertGreaterEqual(res.goals_a, 0)
        self.assertGreaterEqual(res.goals_b, 0)
        self.assertIsNone(res.penalty_winner)  # no penalties in group stage

    def test_knockout_match_has_winner(self):
        """Knockout matches must always produce a winner."""
        for _ in range(200):
            res = simulate_match(
                self.ratings["Brasil"],
                self.ratings["Alemania"],
                self.avg_attack, self.avg_defense,
                knockout=True, rng=self.rng,
            )
            winner = match_winner(res)
            self.assertIn(winner, ["Brasil", "Alemania"])

    def test_lambda_positive(self):
        lam = _compute_lambda(1.5, 0.9, self.avg_attack, self.avg_defense, is_home=True)
        self.assertGreater(lam, 0)

    def test_lambda_home_advantage(self):
        lam_neutral = _compute_lambda(1.3, 1.0, self.avg_attack, self.avg_defense, is_home=False)
        lam_home = _compute_lambda(1.3, 1.0, self.avg_attack, self.avg_defense, is_home=True)
        self.assertGreater(lam_home, lam_neutral)


class TestGroupStage(unittest.TestCase):
    """Test group stage simulation."""

    def setUp(self):
        self.ratings = load_team_data()
        attacks = [r.attack for r in self.ratings.values()]
        defenses = [r.defense for r in self.ratings.values()]
        self.avg_attack = float(np.mean(attacks))
        self.avg_defense = float(np.mean(defenses))
        self.rng = np.random.default_rng(123)

    def test_group_standings_complete(self):
        teams = GROUPS["A"]
        standings, results = _simulate_group(teams, self.ratings, self.avg_attack, self.avg_defense, self.rng)
        self.assertEqual(len(standings), 4)
        # Each team plays 3 matches (round-robin of 4)
        for s in standings:
            self.assertEqual(s.played, 3)
        # 6 matches total in a group of 4
        self.assertEqual(len(results), 6)

    def test_standings_sorted_by_points(self):
        teams = GROUPS["C"]
        standings, _ = _simulate_group(teams, self.ratings, self.avg_attack, self.avg_defense, self.rng)
        for i in range(len(standings) - 1):
            # Points should be >= next team (primary sort)
            self.assertGreaterEqual(standings[i].points, standings[i + 1].points)


class TestBestThirds(unittest.TestCase):
    """Test best third-placed team selection."""

    def test_selects_8_from_12(self):
        rng = np.random.default_rng(77)
        thirds = []
        for gl in "ABCDEFGHIJKL":
            thirds.append((gl, GroupStanding(
                team=f"Team_{gl}",
                played=3,
                points=rng.integers(0, 7),
                gf=rng.integers(0, 8),
                ga=rng.integers(0, 8),
            )))
        best = _select_best_thirds(thirds, rng)
        self.assertEqual(len(best), 8)


class TestTournamentSimulation(unittest.TestCase):
    """Integration tests for full tournament simulation."""

    @classmethod
    def setUpClass(cls):
        """Run a small simulation once for all tests in this class."""
        cls.results = simulate_tournament(n_simulations=2000, seed=42)

    def test_champion_probs_sum_to_one(self):
        total = sum(self.results["champion_probs"].values())
        self.assertAlmostEqual(total, 1.0, places=2,
                               msg=f"Champion probabilities sum to {total:.4f}, expected ~1.0")

    def test_group_exit_probs_reasonable(self):
        """At least some teams should exit in group stage."""
        total_exit = sum(self.results["group_exit_probs"].values())
        # 16 teams exit in groups each sim → expected sum = 16
        # As probability per team: sum ~ 16/48 * 48 = 16
        self.assertGreater(total_exit, 10, "Too few group exits detected")

    def test_top_teams_significant_champion_prob(self):
        """Argentina, France, and Brazil should each have > 5% champion probability."""
        champ = self.results["champion_probs"]
        for team in ["Argentina", "Francia", "Brasil"]:
            prob = champ.get(team, 0)
            self.assertGreater(
                prob, 0.05,
                f"{team} champion prob ({prob:.3f}) should be > 5%"
            )

    def test_weak_teams_low_champion_prob(self):
        """Curaçao and Haití should have < 2% champion probability."""
        champ = self.results["champion_probs"]
        for team in ["Curaçao", "Haití"]:
            prob = champ.get(team, 0)
            self.assertLess(
                prob, 0.02,
                f"{team} champion prob ({prob:.3f}) should be < 2%"
            )

    def test_all_48_teams_present_in_results(self):
        self.assertEqual(len(self.results["champion_probs"]), 48)
        self.assertEqual(len(self.results["group_exit_probs"]), 48)

    def test_expected_goals_positive(self):
        for team, xg in self.results["expected_goals"].items():
            self.assertGreaterEqual(xg, 0, f"{team} has negative xG")

    def test_strong_team_higher_sf_prob_than_weak(self):
        sf = self.results["semifinal_probs"]
        self.assertGreater(
            sf.get("Argentina", 0),
            sf.get("Haití", 0),
            "Argentina should reach SF more often than Haití"
        )

    def test_n_simulations_recorded(self):
        self.assertEqual(self.results["n_simulations"], 2000)


class TestMatchProbabilities(unittest.TestCase):
    """Test the get_match_probabilities public API."""

    def test_probabilities_sum_to_one(self):
        probs = get_match_probabilities("Argentina", "Francia", n_sims=5000)
        total = probs["win_a"] + probs["draw"] + probs["win_b"]
        self.assertAlmostEqual(total, 1.0, places=2)

    def test_expected_goals_positive(self):
        probs = get_match_probabilities("Brasil", "Haití", n_sims=5000)
        self.assertGreater(probs["expected_goals_a"], 0)
        self.assertGreater(probs["expected_goals_b"], 0)

    def test_stronger_team_favored(self):
        probs = get_match_probabilities("Argentina", "Haití", n_sims=10000)
        self.assertGreater(
            probs["win_a"], probs["win_b"],
            "Argentina should be favored over Haití"
        )

    def test_unknown_team_raises(self):
        with self.assertRaises(ValueError):
            get_match_probabilities("Narnia", "Argentina")


if __name__ == "__main__":
    unittest.main(verbosity=2)
