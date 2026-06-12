import os
import httpx
import logging
import random
from typing import List, Dict, Any
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

ODDS_API_KEY = os.getenv("ODDS_API_KEY")
BASE_URL = "https://api.the-odds-api.com/v4"
SPORT_KEY = "soccer_fifa_world_cup"

logger = logging.getLogger(__name__)

# ── Configuración de Fijinis ──────────────────────────────────────────────────
FIJINI_PRICE_MIN = 1.10
FIJINI_PRICE_MAX = 1.30
FIJINI_MAX_PER_MATCH = 8

# Mercados disponibles con sus traducciones
MARKET_LABELS = {
    "h2h": "Ganador del Partido",
    "double_chance": "Doble Oportunidad",
    "totals": "Goles Totales",
    "btts": "Ambos Equipos Marcan",
    "corners": "Córners Totales",
    "cards": "Tarjetas Totales",
    "shots_on_target": "Tiros al Arco",
    "player_to_score": "Jugador Anota",
    "spreads": "Handicap",
    "draw_no_bet": "Empate No Apuesta",
    "alternate_totals": "Línea Alternativa de Goles",
    "alternate_spreads": "Handicap Alternativo",
    "asian_handicap": "Handicap Asiático",
    "first_goal": "Primer Gol en 1ª Mitad",
    "half_time": "Resultado al Descanso",
}

from fetchers.team_mapping import normalize_team_name

def fetch_live_odds() -> List[Dict[str, Any]]:
    if not ODDS_API_KEY:
        logger.warning("ODDS_API_KEY not found. Using MOCK data for odds.")
        return get_mock_odds()

    url = f"{BASE_URL}/sports/{SPORT_KEY}/odds/"
    # Traemos los mercados principales. The Odds API permite pedir varios.
    # btts a veces requiere query por evento, pero probamos pedirlo globalmente.
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "eu,us",
        "markets": "h2h,totals,spreads"
    }
    try:
        response = httpx.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        
        # Normalizar nombres de equipos para que coincidan con la app
        for match in data:
            match["home_team"] = normalize_team_name(match.get("home_team", ""))
            match["away_team"] = normalize_team_name(match.get("away_team", ""))
            
            # Normalizar nombres en los outcomes para H2H
            for bookmaker in match.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market["key"] == "h2h":
                        for out in market.get("outcomes", []):
                            if out["name"].lower() != "draw":
                                out["name"] = normalize_team_name(out["name"])
                                
        return filter_fijinis(data)
    except Exception as e:
        logger.error(f"Error fetching odds: {e}")
        logger.warning("Using MOCK data for odds due to API error.")
        return get_mock_odds()


def filter_fijinis(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filtra cuotas entre FIJINI_PRICE_MIN y FIJINI_PRICE_MAX.
    Máximo FIJINI_MAX_PER_MATCH fijinis por partido,
    priorizando mercados con mejor relación cuota/valor y variedad de mercados.
    """
    matches_result = []

    for match in raw_data:
        best_odds_map = {}

        for bookmaker in match.get("bookmakers", []):
            bookmaker_name = bookmaker.get("title", bookmaker.get("key", "Bookie"))
            if "betfair" in bookmaker_name.lower() or "matchbook" in bookmaker_name.lower():
                continue

            for market in bookmaker.get("markets", []):
                market_key = market["key"]
                if "lay" in market_key:
                    continue

                # Calcular Doble Oportunidad desde H2H
                if market_key == "h2h":
                    home_name = match.get("home_team", "")
                    away_name = match.get("away_team", "")
                    home_p = draw_p = away_p = 0
                    for out in market.get("outcomes", []):
                        nm = out["name"]
                        if nm == home_name: home_p = out["price"]
                        elif nm == away_name: away_p = out["price"]
                        elif nm.lower() == "draw": draw_p = out["price"]

                    existing = [o["name"] for o in market.get("outcomes", [])]
                    if home_p and draw_p and f"{home_name} o Empate" not in existing:
                        dc = round(1 / ((1/home_p) + (1/draw_p)), 2)
                        market["outcomes"].append({"name": f"{home_name} o Empate", "price": dc, "_dc": True})
                    if away_p and draw_p and f"{away_name} o Empate" not in existing:
                        dc = round(1 / ((1/away_p) + (1/draw_p)), 2)
                        market["outcomes"].append({"name": f"{away_name} o Empate", "price": dc, "_dc": True})

                    # Derivar Draw No Bet desde H2H
                    if home_p and away_p:
                        dnb_home = round(home_p * (draw_p - 1) / draw_p if draw_p else home_p * 0.85, 2)
                        dnb_away = round(away_p * (draw_p - 1) / draw_p if draw_p else away_p * 0.85, 2)
                        # Guardar para procesar como mercado derivado
                        dnb_outcomes = [
                            {"name": home_name, "price": max(1.01, min(dnb_home, 5.0))},
                            {"name": away_name, "price": max(1.01, min(dnb_away, 5.0))},
                        ]
                        # Inyectar mercado draw_no_bet sintético
                        bookmaker.setdefault("_derived_markets", []).append(
                            {"key": "draw_no_bet", "outcomes": dnb_outcomes}
                        )

                # Derivar Handicap Asiático desde spreads
                if market_key == "spreads":
                    ah_outcomes = []
                    for out in market.get("outcomes", []):
                        ah_price = round(out["price"] * 0.97, 2)  # Ligero ajuste
                        point = out.get("point", 0)
                        ah_outcomes.append({
                            "name": out["name"],
                            "price": max(1.01, ah_price),
                            "point": point
                        })
                    if ah_outcomes:
                        bookmaker.setdefault("_derived_markets", []).append(
                            {"key": "asian_handicap", "outcomes": ah_outcomes}
                        )

                # Procesar outcomes del mercado actual + mercados derivados
                all_markets_to_process = [(market_key, market)]
                for dm in bookmaker.get("_derived_markets", []):
                    all_markets_to_process.append((dm["key"], dm))
                bookmaker["_derived_markets"] = []  # Limpiar después de recoger

                for proc_key, proc_market in all_markets_to_process:
                    for outcome in proc_market.get("outcomes", []):
                        price = outcome["price"]
                        selection = outcome["name"]

                        if "point" in outcome:
                            selection = f"{selection} {outcome['point']}"

                        selection = (selection
                            .replace("Over", "Más de")
                            .replace("Under", "Menos de"))
                        if FIJINI_PRICE_MIN <= price <= FIJINI_PRICE_MAX:
                            dict_key = f"{proc_key}_{selection}"
                            if dict_key not in best_odds_map or price > best_odds_map[dict_key]["price"]:
                                best_odds_map[dict_key] = {
                                    "market": MARKET_LABELS.get(proc_key, proc_key),
                                    "market_key": proc_key,
                                    "selection": selection,
                                    "price": price,
                                    "bookmaker": bookmaker_name
                                }

        all_fijinis = list(best_odds_map.values())

        # Si no hay ninguna, forzar la más segura disponible
        if not all_fijinis:
            all_safe = []
            for bk in match.get("bookmakers", []):
                for mkt in bk.get("markets", []):
                    for out in mkt.get("outcomes", []):
                        p = out["price"]
                        if 1.01 < p < 1.45:
                            all_safe.append({
                                "market": MARKET_LABELS.get(mkt["key"], mkt["key"]),
                                "market_key": mkt["key"],
                                "selection": out["name"].replace("Over", "Más de").replace("Under", "Menos de"),
                                "price": p,
                                "bookmaker": bk.get("title", "Bookie")
                            })
            if all_safe:
                all_fijinis = [min(all_safe, key=lambda x: x["price"])]

        # Limitar a máximo FIJINI_MAX_PER_MATCH, priorizando variedad de mercados
        selected = _pick_best_varied(all_fijinis, max_count=FIJINI_MAX_PER_MATCH)

        if selected:
            matches_result.append({
                "external_match_id": match.get("id"),
                "home_team": match.get("home_team"),
                "away_team": match.get("away_team"),
                "commence_time": match.get("commence_time"),
                "group": match.get("group", "Fase de Grupos"),
                "fijinis": selected
            })

    return matches_result


def _pick_best_varied(fijinis: List[Dict], max_count: int = FIJINI_MAX_PER_MATCH) -> List[Dict]:
    """Selecciona hasta max_count fijinis asegurando variedad de mercados."""
    if not fijinis:
        return []

    # Ordenar por cuota descendente (mejor cuota = más valor)
    fijinis_sorted = sorted(fijinis, key=lambda x: x["price"], reverse=True)

    selected = []
    used_markets = set()

    for f in fijinis_sorted:
        mkt = f.get("market_key", f.get("market", ""))
        if mkt not in used_markets:
            selected.append(f)
            used_markets.add(mkt)
        if len(selected) >= max_count:
            break

    # Si no llegamos al máximo, completar con lo que quede
    if len(selected) < max_count:
        for f in fijinis_sorted:
            if f not in selected:
                selected.append(f)
            if len(selected) >= max_count:
                break

    return selected


# ─────────────────────────────────────────────
# MOCK DATA – Fecha 1 del Mundial 2026 completa
# ─────────────────────────────────────────────
WC2026_MATCHDAY1 = [
    # Grupo A
    {
        "id": "a1", "home_team": "México", "away_team": "Sudáfrica",
        "group": "Grupo A", "commence_time": "2026-06-11T21:00:00Z",
        "bookmakers": [{"title": "Bet365", "key": "bet365", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "México", "price": 1.55},
                {"name": "Sudáfrica", "price": 5.80},
                {"name": "Draw", "price": 3.60},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.22, "point": 2.5},
                {"name": "Under", "price": 1.66, "point": 2.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.85},
                {"name": "No", "price": 1.90},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.40, "point": 3.5},
                {"name": "Under", "price": 2.80, "point": 3.5},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.19, "point": 9.5},
                {"name": "Under", "price": 1.75, "point": 9.5},
            ]},
        ]}]
    },
    {
        "id": "a2", "home_team": "Corea del Sur", "away_team": "República Checa",
        "group": "Grupo A", "commence_time": "2026-06-12T20:00:00Z",
        "bookmakers": [{"title": "1xBet", "key": "1xbet", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Corea del Sur", "price": 2.40},
                {"name": "República Checa", "price": 2.90},
                {"name": "Draw", "price": 3.20},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.80},
                {"name": "No", "price": 1.95},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.35, "point": 3.5},
                {"name": "Under", "price": 3.00, "point": 3.5},
            ]},
            {"key": "first_goal", "outcomes": [
                {"name": "Gol en la 1ª mitad", "price": 1.30},
                {"name": "Sin gol en la 1ª mitad", "price": 3.40},
            ]},
        ]}]
    },
    # Grupo B
    {
        "id": "b1", "home_team": "Canadá", "away_team": "Bosnia y Herzegovina",
        "group": "Grupo B", "commence_time": "2026-06-12T17:00:00Z",
        "bookmakers": [{"title": "Betano", "key": "betano", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Canadá", "price": 1.70},
                {"name": "Bosnia y Herzegovina", "price": 4.80},
                {"name": "Draw", "price": 3.40},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.28, "point": 1.5},
                {"name": "Under", "price": 3.90, "point": 1.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.75},
                {"name": "No", "price": 2.00},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.16, "point": 8.5},
                {"name": "Under", "price": 1.85, "point": 8.5},
            ]},
        ]}]
    },
    {
        "id": "b2", "home_team": "Qatar", "away_team": "Suiza",
        "group": "Grupo B", "commence_time": "2026-06-13T20:00:00Z",
        "bookmakers": [{"title": "William Hill", "key": "williamhill", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Qatar", "price": 5.50},
                {"name": "Suiza", "price": 1.62},
                {"name": "Draw", "price": 3.70},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.14, "point": 2.5},
                {"name": "Under", "price": 1.80, "point": 2.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 2.10},
                {"name": "No", "price": 1.70},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.45, "point": 3.5},
                {"name": "Under", "price": 2.60, "point": 3.5},
            ]},
        ]}]
    },
    # Grupo C
    {
        "id": "c1", "home_team": "Brasil", "away_team": "Marruecos",
        "group": "Grupo C", "commence_time": "2026-06-13T23:00:00Z",
        "bookmakers": [{"title": "Bet365", "key": "bet365", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Brasil", "price": 1.45},
                {"name": "Marruecos", "price": 7.00},
                {"name": "Draw", "price": 4.20},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.26, "point": 1.5},
                {"name": "Under", "price": 3.60, "point": 1.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.70},
                {"name": "No", "price": 2.10},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.21, "point": 10.5},
                {"name": "Under", "price": 1.69, "point": 10.5},
            ]},
        ]}]
    },
    {
        "id": "c2", "home_team": "Haití", "away_team": "Escocia",
        "group": "Grupo C", "commence_time": "2026-06-14T17:00:00Z",
        "bookmakers": [{"title": "Unibet", "key": "unibet", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Haití", "price": 4.10},
                {"name": "Escocia", "price": 1.88},
                {"name": "Draw", "price": 3.30},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.90, "point": 2.5},
                {"name": "Under", "price": 1.90, "point": 2.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.85},
                {"name": "No", "price": 1.90},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.50, "point": 4.5},
                {"name": "Under", "price": 2.40, "point": 4.5},
            ]},
        ]}]
    },
    # Grupo D
    {
        "id": "d1", "home_team": "Estados Unidos", "away_team": "Paraguay",
        "group": "Grupo D", "commence_time": "2026-06-13T17:00:00Z",
        "bookmakers": [{"title": "Pinnacle", "key": "pinnacle", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Estados Unidos", "price": 1.65},
                {"name": "Paraguay", "price": 5.10},
                {"name": "Draw", "price": 3.50},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.18, "point": 9.5},
                {"name": "Under", "price": 1.74, "point": 9.5},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.24, "point": 1.5},
                {"name": "Under", "price": 4.00, "point": 1.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.80},
                {"name": "No", "price": 1.95},
            ]},
            {"key": "first_goal", "outcomes": [
                {"name": "Gol en la 1ª mitad", "price": 1.25},
                {"name": "Sin gol en la 1ª mitad", "price": 3.60},
            ]},
        ]}]
    },
    {
        "id": "d2", "home_team": "Australia", "away_team": "Turquía",
        "group": "Grupo D", "commence_time": "2026-06-14T20:00:00Z",
        "bookmakers": [{"title": "Bwin", "key": "bwin", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Australia", "price": 2.60},
                {"name": "Turquía", "price": 2.70},
                {"name": "Draw", "price": 3.10},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.75},
                {"name": "No", "price": 2.00},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.38, "point": 3.5},
                {"name": "Under", "price": 2.90, "point": 3.5},
            ]},
            {"key": "first_goal", "outcomes": [
                {"name": "Gol en la 1ª mitad", "price": 1.28},
                {"name": "Sin gol en la 1ª mitad", "price": 3.50},
            ]},
        ]}]
    },
    # Grupo E
    {
        "id": "e1", "home_team": "Alemania", "away_team": "Curaçao",
        "group": "Grupo E", "commence_time": "2026-06-15T00:00:00Z",
        "bookmakers": [{"title": "Bet365", "key": "bet365", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Alemania", "price": 1.18},
                {"name": "Curaçao", "price": 14.00},
                {"name": "Draw", "price": 7.50},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.13, "point": 3.5},
                {"name": "Under", "price": 7.00, "point": 3.5},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.15, "point": 11.5},
                {"name": "Under", "price": 5.50, "point": 11.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.45},
                {"name": "No", "price": 2.60},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.55, "point": 4.5},
                {"name": "Under", "price": 2.30, "point": 4.5},
            ]},
        ]}]
    },
    {
        "id": "e2", "home_team": "Costa de Marfil", "away_team": "Ecuador",
        "group": "Grupo E", "commence_time": "2026-06-15T17:00:00Z",
        "bookmakers": [{"title": "1xBet", "key": "1xbet", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Costa de Marfil", "price": 2.45},
                {"name": "Ecuador", "price": 2.85},
                {"name": "Draw", "price": 3.10},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.90, "point": 2.5},
                {"name": "Under", "price": 1.90, "point": 2.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.80},
                {"name": "No", "price": 1.95},
            ]},
            {"key": "first_goal", "outcomes": [
                {"name": "Gol en la 1ª mitad", "price": 1.32},
                {"name": "Sin gol en la 1ª mitad", "price": 3.20},
            ]},
        ]}]
    },
    # Grupo F
    {
        "id": "f1", "home_team": "Países Bajos", "away_team": "Japón",
        "group": "Grupo F", "commence_time": "2026-06-15T20:00:00Z",
        "bookmakers": [{"title": "Unibet", "key": "unibet", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Países Bajos", "price": 1.60},
                {"name": "Japón", "price": 5.50},
                {"name": "Draw", "price": 3.80},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.20, "point": 9.5},
                {"name": "Under", "price": 1.72, "point": 9.5},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.29, "point": 1.5},
                {"name": "Under", "price": 3.50, "point": 1.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.90},
                {"name": "No", "price": 1.85},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.42, "point": 3.5},
                {"name": "Under", "price": 2.70, "point": 3.5},
            ]},
        ]}]
    },
    {
        "id": "f2", "home_team": "Suecia", "away_team": "Túnez",
        "group": "Grupo F", "commence_time": "2026-06-16T00:00:00Z",
        "bookmakers": [{"title": "William Hill", "key": "williamhill", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Suecia", "price": 1.80},
                {"name": "Túnez", "price": 4.60},
                {"name": "Draw", "price": 3.30},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.50, "point": 2.5},
                {"name": "Under", "price": 2.40, "point": 2.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.88},
                {"name": "No", "price": 1.88},
            ]},
            {"key": "first_goal", "outcomes": [
                {"name": "Gol en la 1ª mitad", "price": 1.35},
                {"name": "Sin gol en la 1ª mitad", "price": 3.10},
            ]},
        ]}]
    },
    # Grupo G
    {
        "id": "g1", "home_team": "Irán", "away_team": "Nueva Zelanda",
        "group": "Grupo G", "commence_time": "2026-06-16T17:00:00Z",
        "bookmakers": [{"title": "Betano", "key": "betano", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Irán", "price": 2.10},
                {"name": "Nueva Zelanda", "price": 3.40},
                {"name": "Draw", "price": 3.20},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 2.10, "point": 2.5},
                {"name": "Under", "price": 1.70, "point": 2.5},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.22, "point": 8.5},
                {"name": "Under", "price": 1.65, "point": 8.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 2.00},
                {"name": "No", "price": 1.78},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.48, "point": 3.5},
                {"name": "Under", "price": 2.50, "point": 3.5},
            ]},
        ]}]
    },
    {
        "id": "g2", "home_team": "Bélgica", "away_team": "Egipto",
        "group": "Grupo G", "commence_time": "2026-06-16T20:00:00Z",
        "bookmakers": [{"title": "Bet365", "key": "bet365", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Bélgica", "price": 1.50},
                {"name": "Egipto", "price": 6.50},
                {"name": "Draw", "price": 4.00},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.25, "point": 1.5},
                {"name": "Under", "price": 3.80, "point": 1.5},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.17, "point": 10.5},
                {"name": "Under", "price": 5.20, "point": 10.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.72},
                {"name": "No", "price": 2.05},
            ]},
            {"key": "first_goal", "outcomes": [
                {"name": "Gol en la 1ª mitad", "price": 1.22},
                {"name": "Sin gol en la 1ª mitad", "price": 3.80},
            ]},
        ]}]
    },
    # Grupo H
    {
        "id": "h1", "home_team": "Arabia Saudita", "away_team": "Uruguay",
        "group": "Grupo H", "commence_time": "2026-06-17T17:00:00Z",
        "bookmakers": [{"title": "1xBet", "key": "1xbet", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Arabia Saudita", "price": 3.80},
                {"name": "Uruguay", "price": 1.95},
                {"name": "Draw", "price": 3.40},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.80, "point": 2.5},
                {"name": "Under", "price": 2.00, "point": 2.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.82},
                {"name": "No", "price": 1.93},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.52, "point": 4.5},
                {"name": "Under", "price": 2.35, "point": 4.5},
            ]},
        ]}]
    },
    {
        "id": "h2", "home_team": "España", "away_team": "Cabo Verde",
        "group": "Grupo H", "commence_time": "2026-06-17T20:00:00Z",
        "bookmakers": [{"title": "Unibet", "key": "unibet", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "España", "price": 1.22},
                {"name": "Cabo Verde", "price": 12.00},
                {"name": "Draw", "price": 6.50},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.16, "point": 2.5},
                {"name": "Under", "price": 5.80, "point": 2.5},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.12, "point": 11.5},
                {"name": "Under", "price": 6.00, "point": 11.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.60},
                {"name": "No", "price": 2.25},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.35, "point": 3.5},
                {"name": "Under", "price": 3.00, "point": 3.5},
            ]},
        ]}]
    },
    # Grupo I
    {
        "id": "i1", "home_team": "Francia", "away_team": "Senegal",
        "group": "Grupo I", "commence_time": "2026-06-18T17:00:00Z",
        "bookmakers": [{"title": "Pinnacle", "key": "pinnacle", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Francia", "price": 1.55},
                {"name": "Senegal", "price": 5.90},
                {"name": "Draw", "price": 3.70},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.27, "point": 1.5},
                {"name": "Under", "price": 3.55, "point": 1.5},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.20, "point": 10.5},
                {"name": "Under", "price": 1.72, "point": 10.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.68},
                {"name": "No", "price": 2.12},
            ]},
        ]}]
    },
    {
        "id": "i2", "home_team": "Irak", "away_team": "Noruega",
        "group": "Grupo I", "commence_time": "2026-06-18T20:00:00Z",
        "bookmakers": [{"title": "Bwin", "key": "bwin", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Irak", "price": 4.20},
                {"name": "Noruega", "price": 1.75},
                {"name": "Draw", "price": 3.50},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.50, "point": 2.5},
                {"name": "Under", "price": 2.40, "point": 2.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.78},
                {"name": "No", "price": 1.98},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.40, "point": 3.5},
                {"name": "Under", "price": 2.80, "point": 3.5},
            ]},
            {"key": "first_goal", "outcomes": [
                {"name": "Gol en la 1ª mitad", "price": 1.38},
                {"name": "Sin gol en la 1ª mitad", "price": 2.90},
            ]},
        ]}]
    },
    # Grupo J
    {
        "id": "j1", "home_team": "Argentina", "away_team": "Argelia",
        "group": "Grupo J", "commence_time": "2026-06-19T17:00:00Z",
        "bookmakers": [{"title": "Bet365", "key": "bet365", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Argentina", "price": 1.30},
                {"name": "Argelia", "price": 9.00},
                {"name": "Draw", "price": 5.20},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.14, "point": 2.5},
                {"name": "Under", "price": 6.50, "point": 2.5},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.19, "point": 11.5},
                {"name": "Under", "price": 4.80, "point": 11.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.55},
                {"name": "No", "price": 2.35},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.30, "point": 3.5},
                {"name": "Under", "price": 3.30, "point": 3.5},
            ]},
            {"key": "first_goal", "outcomes": [
                {"name": "Gol en la 1ª mitad", "price": 1.18},
                {"name": "Sin gol en la 1ª mitad", "price": 4.20},
            ]},
        ]}]
    },
    {
        "id": "j2", "home_team": "Austria", "away_team": "Jordania",
        "group": "Grupo J", "commence_time": "2026-06-19T20:00:00Z",
        "bookmakers": [{"title": "Unibet", "key": "unibet", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Austria", "price": 1.55},
                {"name": "Jordania", "price": 6.00},
                {"name": "Draw", "price": 3.80},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.23, "point": 1.5},
                {"name": "Under", "price": 3.90, "point": 1.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.92},
                {"name": "No", "price": 1.83},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.44, "point": 3.5},
                {"name": "Under", "price": 2.65, "point": 3.5},
            ]},
        ]}]
    },
    # Grupo K
    {
        "id": "k1", "home_team": "Portugal", "away_team": "Congo RD",
        "group": "Grupo K", "commence_time": "2026-06-20T17:00:00Z",
        "bookmakers": [{"title": "Betano", "key": "betano", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Portugal", "price": 1.25},
                {"name": "Congo RD", "price": 10.50},
                {"name": "Draw", "price": 6.00},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.18, "point": 2.5},
                {"name": "Under", "price": 5.20, "point": 2.5},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.14, "point": 10.5},
                {"name": "Under", "price": 6.20, "point": 10.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.58},
                {"name": "No", "price": 2.30},
            ]},
            {"key": "first_goal", "outcomes": [
                {"name": "Gol en la 1ª mitad", "price": 1.20},
                {"name": "Sin gol en la 1ª mitad", "price": 4.00},
            ]},
        ]}]
    },
    {
        "id": "k2", "home_team": "Uzbekistán", "away_team": "Colombia",
        "group": "Grupo K", "commence_time": "2026-06-20T20:00:00Z",
        "bookmakers": [{"title": "1xBet", "key": "1xbet", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Uzbekistán", "price": 4.00},
                {"name": "Colombia", "price": 1.80},
                {"name": "Draw", "price": 3.40},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.60, "point": 2.5},
                {"name": "Under", "price": 2.20, "point": 2.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.75},
                {"name": "No", "price": 2.00},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.46, "point": 3.5},
                {"name": "Under", "price": 2.55, "point": 3.5},
            ]},
        ]}]
    },
    # Grupo L
    {
        "id": "l1", "home_team": "Ghana", "away_team": "Panamá",
        "group": "Grupo L", "commence_time": "2026-06-21T17:00:00Z",
        "bookmakers": [{"title": "Bwin", "key": "bwin", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Ghana", "price": 2.20},
                {"name": "Panamá", "price": 3.10},
                {"name": "Draw", "price": 3.20},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.80, "point": 2.5},
                {"name": "Under", "price": 1.95, "point": 2.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.82},
                {"name": "No", "price": 1.93},
            ]},
            {"key": "first_goal", "outcomes": [
                {"name": "Gol en la 1ª mitad", "price": 1.40},
                {"name": "Sin gol en la 1ª mitad", "price": 2.75},
            ]},
        ]}]
    },
    {
        "id": "l2", "home_team": "Inglaterra", "away_team": "Croacia",
        "group": "Grupo L", "commence_time": "2026-06-21T20:00:00Z",
        "bookmakers": [{"title": "Bet365", "key": "bet365", "markets": [
            {"key": "h2h", "outcomes": [
                {"name": "Inglaterra", "price": 1.65},
                {"name": "Croacia", "price": 5.00},
                {"name": "Draw", "price": 3.60},
            ]},
            {"key": "totals", "outcomes": [
                {"name": "Over", "price": 1.28, "point": 1.5},
                {"name": "Under", "price": 3.55, "point": 1.5},
            ]},
            {"key": "corners", "outcomes": [
                {"name": "Over", "price": 1.18, "point": 9.5},
                {"name": "Under", "price": 1.75, "point": 9.5},
            ]},
            {"key": "btts", "outcomes": [
                {"name": "Sí", "price": 1.78},
                {"name": "No", "price": 1.98},
            ]},
            {"key": "cards", "outcomes": [
                {"name": "Over", "price": 1.36, "point": 3.5},
                {"name": "Under", "price": 3.00, "point": 3.5},
            ]},
        ]}]
    },
]


def get_mock_odds() -> List[Dict[str, Any]]:
    """Todos los partidos reales de la Fecha 1 del Mundial 2026 con cuotas realistas."""
    return filter_fijinis(WC2026_MATCHDAY1)
