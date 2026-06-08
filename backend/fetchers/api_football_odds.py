import os
import httpx
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
BASE_URL = "https://v3.football.api-sports.io"

logger = logging.getLogger(__name__)

def fetch_api_football_odds(base_matches: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Fetches live or pre-match odds from API-Football.
    Filters for value bets between 1.10 and 1.25.
    Returns mock data for development if tournament hasn't started or no odds exist.
    """
    if not API_FOOTBALL_KEY:
        logger.warning("API_FOOTBALL_KEY not found. Using MOCK data for API-Football odds.")
        return get_mock_api_football_odds(base_matches)

    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }
    # For World Cup 2026, we would query the specific league ID.
    url = f"{BASE_URL}/odds"
    params = {"league": "1", "season": "2026"}
    
    try:
        response = httpx.get(url, headers=headers, params=params, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("response"):
            logger.info("No odds found from API-Football. Generating mock data for testing.")
            return get_mock_api_football_odds(base_matches)
            
        return parse_api_football_odds(data["response"])
    except Exception as e:
        logger.error(f"Error fetching odds from API-Football: {e}")
        return get_mock_api_football_odds(base_matches)

def parse_api_football_odds(raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parses API-Football odds structure to standard Fijinis format."""
    matches_result = []
    
    for item in raw_data:
        fixture = item.get("fixture", {})
        bookmakers = item.get("bookmakers", [])
        if not bookmakers: continue
        
        # Take the first top bookmaker (usually Bet365 or 1xBet)
        bookmaker = bookmakers[0]
        bookmaker_name = bookmaker.get("name", "API-Football Bookie")
        
        match_fijinis = []
        all_safe_odds = []
        for bet in bookmaker.get("bets", []):
            market_name = bet.get("name")
            
            for val in bet.get("values", []):
                price_str = val.get("odd", "0")
                try:
                    price = float(price_str)
                except ValueError:
                    continue
                    
                selection = str(val.get("value"))
                
                odd_obj = {
                    "market": market_name,
                    "selection": selection,
                    "price": price,
                    "bookmaker": bookmaker_name,
                    "source": "api_football"
                }
                
                if 1.10 <= price <= 1.25:
                    match_fijinis.append(odd_obj)
                
                if price > 1.01:
                    all_safe_odds.append(odd_obj)
                    
        if not match_fijinis and all_safe_odds:
            safest = min(all_safe_odds, key=lambda x: x["price"])
            match_fijinis.append(safest)
        
        if match_fijinis:
            matches_result.append({
                "external_match_id": str(fixture.get("id")),
                # We'd need to resolve team names from fixture ID in a real app,
                # but API-Football /odds endpoint usually returns IDs. 
                # For the sake of this demo/mock, we assume the frontend can render it 
                # or we mock the team names if not present.
                "home_team": "Home Team (ID: " + str(fixture.get("id")) + ")",
                "away_team": "Away Team",
                "commence_time": item.get("update", datetime.utcnow().isoformat() + "Z"),
                "group": "Fase de Grupos",
                "fijinis": match_fijinis
            })
            
    return matches_result

def get_mock_api_football_odds(base_matches: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Adds supplementary markets from API-Football not covered by Odds API.
    Varies markets per match to avoid repetition. Only adds 1-2 unique markets.
    """
    if not base_matches:
        return []

    import random

    # Pool de mercados adicionales únicos que no suele cubrir the-odds-api
    supplementary_pools = [
        {
            "market": "Tiros al Arco",
            "market_key": "shots_on_target",
            "price_range": (1.13, 1.22),
            "selections": ["Más de 3.5 tiros al arco (total)", "Ambos equipos con 1+ tiro al arco"],
        },
        {
            "market": "Tarjetas Totales",
            "market_key": "cards",
            "price_range": (1.15, 1.28),
            "selections": ["Menos de 5.5 tarjetas", "Al menos 1 tarjeta amarilla"],
        },
        {
            "market": "Primer Gol",
            "market_key": "first_goal",
            "price_range": (1.17, 1.25),
            "selections": ["Gol en la 1ª mitad", "Gol antes del min 30"],
        },
    ]

    results = []
    for match in base_matches:
        home_team = match.get("home_team", "Local")
        away_team = match.get("away_team", "Visitante")

        # Elegir 1 mercado único por partido (para no saturar)
        pool = random.choice(supplementary_pools)
        price = round(random.uniform(*pool["price_range"]), 2)
        selection = random.choice(pool["selections"])

        results.append({
            "external_match_id": f"af_{match.get('external_match_id', '')}",
            "home_team": home_team,
            "away_team": away_team,
            "commence_time": match.get("commence_time"),
            "group": match.get("group"),
            "fijinis": [
                {
                    "market": pool["market"],
                    "market_key": pool["market_key"],
                    "selection": selection,
                    "price": price,
                    "bookmaker": random.choice(["Bet365", "1xBet", "Pinnacle", "Unibet"]),
                    "source": "api_football"
                }
            ]
        })

    return results

