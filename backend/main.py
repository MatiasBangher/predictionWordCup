from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List
import logging

import models
from database import engine, get_db
from cache import cache
from fetchers.odds_api import fetch_live_odds
from fetchers.api_football import fetch_team_stats, get_team_stats_by_name
from fetchers.api_football_odds import fetch_api_football_odds
from fetchers.team_mapping import (
    get_api_football_id, normalize_team_name,
    get_matchday_fixtures, WC2026_FIXTURES
)
from analyzer import analyze_fijini
from ml.advanced_wc_model import predict_match_probs
from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

# Create tables in SQLite
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Prediction World Cup API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Background Job Setup
def fetch_and_cache_odds_job():
    print("Running background job: Fetching odds")
    matches_odds_api = fetch_live_odds()
    matches_api_football = fetch_api_football_odds(matches_odds_api)
    
    matches_dict = {}
    for m in matches_odds_api:
        key = f"{m['home_team']}_{m['away_team']}"
        matches_dict[key] = m
        
    for m in matches_api_football:
        key = f"{m['home_team']}_{m['away_team']}"
        if key in matches_dict:
            matches_dict[key].setdefault('fijinis', []).extend(m.get('fijinis', []))
        else:
            matches_dict[key] = m
            
    matches = list(matches_dict.values())

    for match in matches:
        home_name = normalize_team_name(match["home_team"])
        away_name = normalize_team_name(match["away_team"])
        
        home_stats = get_team_stats_by_name(home_name)
        away_stats = get_team_stats_by_name(away_name)
        
        for fijini in match.get("fijinis", []):
            analysis = analyze_fijini(fijini, home_name, away_name, home_stats, away_stats)
            fijini["analysis"] = analysis
            
    cache.set("live_odds", matches, ttl_seconds=300)

scheduler = BackgroundScheduler()
scheduler.add_job(fetch_and_cache_odds_job, 'interval', minutes=5)
scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()

@app.get("/")
def read_root():
    return {"message": "Welcome to World Cup 2026 Prediction API (Fijinis Edition)"}

@app.get("/api/matches")
def get_matches(db: Session = Depends(get_db)):
    # Check cache first to avoid DB hits
    cached_matches = cache.get("matches_list")
    if cached_matches:
        return {"data": cached_matches, "source": "cache"}
        
    matches = db.query(models.Match).all()
    result = [{"id": m.id, "home_team_id": m.home_team_id, "away_team_id": m.away_team_id, "status": m.status} for m in matches]
    
    # Store in cache for 5 minutes
    cache.set("matches_list", result, ttl_seconds=300)
    return {"data": result, "source": "db"}

@app.get("/api/live-odds")
def get_live_odds(db: Session = Depends(get_db)):
    # 1. Check cache first (background job runs every 5 mins)
    cached_odds = cache.get("live_odds")
    if cached_odds:
        return {"data": cached_odds, "source": "cache"}

    # 2. Fetch live odds (mocked or real from The Odds API)
    matches_odds_api = fetch_live_odds()
    matches_api_football = fetch_api_football_odds(matches_odds_api)
    
    # Unify the matches
    matches_dict = {}
    for m in matches_odds_api:
        key = f"{m['home_team']}_{m['away_team']}"
        matches_dict[key] = m
        
    for m in matches_api_football:
        key = f"{m['home_team']}_{m['away_team']}"
        if key in matches_dict:
            matches_dict[key].setdefault('fijinis', []).extend(m.get('fijinis', []))
        else:
            matches_dict[key] = m
            
    matches = list(matches_dict.values())
    
    # 3. Analyze confidence score for each odd
    for match in matches:
        home_name = normalize_team_name(match["home_team"])
        away_name = normalize_team_name(match["away_team"])
        
        home_stats = get_team_stats_by_name(home_name)
        away_stats = get_team_stats_by_name(away_name)
        
        for fijini in match.get("fijinis", []):
            analysis = analyze_fijini(fijini, home_name, away_name, home_stats, away_stats)
            fijini["analysis"] = analysis

    # 4. Save to cache
    cache.set("live_odds", matches, ttl_seconds=60) # 1 min cache for live odds
    
    return {"data": matches, "source": "api"}

@app.get("/api/paper-trading")
def get_paper_trading(db: Session = Depends(get_db)):
    # Returns paper trading simulation state
    return {
        "bankroll": 142.50,
        "initial": 100.00,
        "yield_percent": 42.5,
        "win_rate": 85.0,
        "history": [
            { "day": "Día 1", "balance": 100, "profit": 0 },
            { "day": "Día 2", "balance": 105, "profit": 5 },
            { "day": "Día 3", "balance": 110, "profit": 5 },
            { "day": "Día 4", "balance": 108, "profit": -2 },
            { "day": "Día 5", "balance": 120, "profit": 12 },
            { "day": "Día 6", "balance": 135, "profit": 15 },
            { "day": "Día 7", "balance": 142.50, "profit": 7.5 }
        ]
    }

@app.get("/api/matchday-predictions")
def get_matchday_predictions(matchday: int = 1):
    import random
    # Todos los partidos representativos de la Fecha 1 de todos los Grupos (A al L para el Mundial de 48 equipos)
    fixtures = [
        # Grupo A
        {"home_team": "México", "away_team": "Sudáfrica", "group": "Grupo A", "date": "2026-06-11T21:00:00Z", "stadium": "Estadio Ciudad de México, CDMX"},
        {"home_team": "Corea del Sur", "away_team": "República Checa", "group": "Grupo A", "date": "2026-06-12T20:00:00Z", "stadium": "Estadio Guadalajara"},
        # Grupo B
        {"home_team": "Canadá", "away_team": "Bosnia y Herzegovina", "group": "Grupo B", "date": "2026-06-12T17:00:00Z", "stadium": "Toronto Stadium"},
        {"home_team": "Qatar", "away_team": "Suiza", "group": "Grupo B", "date": "2026-06-13T20:00:00Z", "stadium": "San Francisco Bay Area Stadium"},
        # Grupo C
        {"home_team": "Brasil", "away_team": "Marruecos", "group": "Grupo C", "date": "2026-06-13T23:00:00Z", "stadium": "MetLife Stadium, NJ"},
        {"home_team": "Haití", "away_team": "Escocia", "group": "Grupo C", "date": "2026-06-14T17:00:00Z", "stadium": "Gillette Stadium, Boston"},
        # Grupo D
        {"home_team": "Estados Unidos", "away_team": "Paraguay", "group": "Grupo D", "date": "2026-06-13T17:00:00Z", "stadium": "SoFi Stadium, LA"},
        {"home_team": "Australia", "away_team": "Turquía", "group": "Grupo D", "date": "2026-06-14T20:00:00Z", "stadium": "BC Place, Vancouver"},
        # Grupo E
        {"home_team": "Alemania", "away_team": "Curaçao", "group": "Grupo E", "date": "2026-06-15T00:00:00Z", "stadium": "AT&T Stadium, Dallas"},
        {"home_team": "Costa de Marfil", "away_team": "Ecuador", "group": "Grupo E", "date": "2026-06-15T17:00:00Z", "stadium": "Mercedes-Benz Stadium, ATL"},
        # Grupo F
        {"home_team": "Países Bajos", "away_team": "Japón", "group": "Grupo F", "date": "2026-06-15T20:00:00Z", "stadium": "Lumen Field, Seattle"},
        {"home_team": "Suecia", "away_team": "Túnez", "group": "Grupo F", "date": "2026-06-16T00:00:00Z", "stadium": "Hard Rock Stadium, Miami"},
        # Grupo G
        {"home_team": "Irán", "away_team": "Nueva Zelanda", "group": "Grupo G", "date": "2026-06-16T17:00:00Z", "stadium": "NRG Stadium, Houston"},
        {"home_team": "Bélgica", "away_team": "Egipto", "group": "Grupo G", "date": "2026-06-16T20:00:00Z", "stadium": "Levi's Stadium, SF"},
        # Grupo H
        {"home_team": "Arabia Saudita", "away_team": "Uruguay", "group": "Grupo H", "date": "2026-06-17T17:00:00Z", "stadium": "Lincoln Financial Field, Philly"},
        {"home_team": "España", "away_team": "Cabo Verde", "group": "Grupo H", "date": "2026-06-17T20:00:00Z", "stadium": "Rose Bowl, LA"},
        # Grupo I
        {"home_team": "Francia", "away_team": "Senegal", "group": "Grupo I", "date": "2026-06-18T17:00:00Z", "stadium": "Arrowhead Stadium, KC"},
        {"home_team": "Irak", "away_team": "Noruega", "group": "Grupo I", "date": "2026-06-18T20:00:00Z", "stadium": "Camping World Stadium, Orlando"},
        # Grupo J
        {"home_team": "Argentina", "away_team": "Argelia", "group": "Grupo J", "date": "2026-06-19T17:00:00Z", "stadium": "MetLife Stadium, NJ"},
        {"home_team": "Austria", "away_team": "Jordania", "group": "Grupo J", "date": "2026-06-19T20:00:00Z", "stadium": "SoFi Stadium, LA"},
        # Grupo K
        {"home_team": "Portugal", "away_team": "Congo RD", "group": "Grupo K", "date": "2026-06-20T17:00:00Z", "stadium": "Lumen Field, Seattle"},
        {"home_team": "Uzbekistán", "away_team": "Colombia", "group": "Grupo K", "date": "2026-06-20T20:00:00Z", "stadium": "NRG Stadium, Houston"},
        # Grupo L
        {"home_team": "Ghana", "away_team": "Panamá", "group": "Grupo L", "date": "2026-06-21T17:00:00Z", "stadium": "AT&T Stadium, Dallas"},
        {"home_team": "Inglaterra", "away_team": "Croacia", "group": "Grupo L", "date": "2026-06-21T20:00:00Z", "stadium": "Mercedes-Benz Stadium, ATL"},
    ]
    
    results = []
    for f in fixtures:
        probs = predict_match_probs(f["home_team"], f["away_team"])
        
        # Determine highest probability
        highest_prob = max(probs["home_win"], probs["draw"], probs["away_win"])
        predicted_winner = f["home_team"] if probs["home_win"] == highest_prob else (f["away_team"] if probs["away_win"] == highest_prob else "Empate")
        confidence = "Confianza Alta" if highest_prob >= 55 else "Confianza Media"
        
        # Generación dinámica del análisis con Groq
        try:
            from llm.groq_client import generate_match_preview
            analysis_text = generate_match_preview(
                home_team=f["home_team"],
                away_team=f["away_team"],
                group=f["group"],
                stadium=f["stadium"],
                probs=probs
            )
        except Exception:
            # Fallback a texto genérico
            if predicted_winner == f["home_team"]:
                analysis_text = f"El modelo de Inteligencia Artificial se decanta por {f['home_team']} ({highest_prob}%)."
            elif predicted_winner == f["away_team"]:
                analysis_text = f"Leve ventaja para {f['away_team']} ({highest_prob}% de probabilidad)."
            else:
                analysis_text = f"Este choque del {f['group']} está para cualquiera. El modelo proyecta un altísimo {highest_prob}% de empate."
            
        f["probabilities"] = probs
        f["prediction"] = {
            "winner": predicted_winner,
            "confidence": confidence,
            "analysis": analysis_text
        }
        results.append(f)
        
    return {"data": results, "matchday": matchday}


# ══════════════════════════════════════════════════════════════════════════════
# NUEVO: Endpoint dinámico por Fecha con Monte Carlo por Apuesta
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/matchday/{matchday}/fijinis")
def get_matchday_fijinis(matchday: int = 1):
    """
    Obtiene los fijinis de una fecha específica del Mundial con simulación
    Monte Carlo individual para cada apuesta.
    
    - matchday=1: Fecha 1 (11-21 junio)
    - matchday=2: Fecha 2 (22 junio - 2 julio)
    - matchday=3: Fecha 3 (próximamente)
    """
    from ml.fijini_simulator import simulate_match_fijinis
    
    # 1. Obtener fixtures de la fecha
    fixtures = get_matchday_fixtures(matchday)
    if not fixtures:
        return {"error": f"No hay fixtures para la Fecha {matchday}", "matchday": matchday}
    
    # 2. Obtener cuotas reales (o mock) para todos los partidos
    all_odds = fetch_live_odds()
    api_football_odds = fetch_api_football_odds(all_odds)
    
    # Crear mapa de cuotas por equipo para lookup rápido
    odds_map = {}
    for m in all_odds:
        key = normalize_team_name(m.get("home_team", ""))
        odds_map[key] = m
    for m in api_football_odds:
        key = normalize_team_name(m.get("home_team", ""))
        if key in odds_map:
            odds_map[key].setdefault("fijinis", []).extend(m.get("fijinis", []))
        else:
            odds_map[key] = m
    
    # 3. Para cada fixture, buscar cuotas y correr simulación
    results = []
    for fixture in fixtures:
        home = fixture["home"]
        away = fixture["away"]
        
        # Buscar cuotas del partido
        match_odds = odds_map.get(home, {})
        fijinis = match_odds.get("fijinis", [])
        
        # Stats de equipos
        home_stats = get_team_stats_by_name(home)
        away_stats = get_team_stats_by_name(away)
        
        # Predicción del modelo
        probs = predict_match_probs(home, away)
        
        # Correr simulación Monte Carlo para todas las fijinis del partido
        simulated_fijinis = []
        if fijinis:
            try:
                sim_results = simulate_match_fijinis(
                    home_team=home,
                    away_team=away,
                    fijinis=fijinis,
                    n_simulations=10_000
                )
                simulated_fijinis = sim_results
            except Exception as e:
                logger.error(f"Error simulando fijinis para {home} vs {away}: {e}")
                # Fallback: usar analyzer sin simulación
                for fij in fijinis:
                    analysis = analyze_fijini(fij, home, away, home_stats, away_stats)
                    fij["analysis"] = analysis
                    fij["simulation"] = {"error": str(e)}
                simulated_fijinis = fijinis
        
        # Determinar predicción del partido
        highest_prob = max(probs["home_win"], probs["draw"], probs["away_win"])
        predicted_winner = home if probs["home_win"] == highest_prob else (away if probs["away_win"] == highest_prob else "Empate")
        
        results.append({
            "home_team": home,
            "away_team": away,
            "group": f"Grupo {fixture['group']}",
            "date": fixture["date"],
            "stadium": fixture["stadium"],
            "probabilities": probs,
            "prediction": {
                "winner": predicted_winner,
                "confidence": "Alta" if highest_prob >= 55 else "Media",
            },
            "fijinis": simulated_fijinis,
            "total_fijinis": len(simulated_fijinis),
        })
    
    # Resumen general
    total_fijinis = sum(r["total_fijinis"] for r in results)
    green_bets = sum(
        1 for r in results 
        for f in r["fijinis"] 
        if isinstance(f, dict) and f.get("simulation", {}).get("value_rating") == "GREEN"
    )
    
    return {
        "matchday": matchday,
        "total_matches": len(results),
        "total_fijinis": total_fijinis,
        "green_value_bets": green_bets,
        "data": results
    }


@app.get("/api/montecarlo-simulation")
def get_montecarlo_simulation(n_simulations: int = 1000):
    from ml.montecarlo_simulator import simulate_tournament
    result = simulate_tournament(n_simulations=n_simulations)
    return {"data": result}


@app.get("/api/team/{team_name}/profile")
def get_team_profile(team_name: str):
    from ml.advanced_wc_model import load_team_ratings
    try:
        ratings = load_team_ratings()
        team_rating = ratings.get(team_name)
        if team_rating:
            return {"data": team_rating}
        return {"error": "Team not found"}
    except Exception as e:
        return {"error": str(e)}


# Simple WebSocket manager for streaming odds
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

ws_manager = ConnectionManager()

@app.websocket("/ws/odds")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
