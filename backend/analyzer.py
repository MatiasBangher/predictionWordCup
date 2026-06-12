import os
import joblib
import numpy as np

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'ml', 'model.pkl')
try:
    ml_model = joblib.load(MODEL_PATH)
except Exception:
    ml_model = None

# Catálogo de textos de análisis por tipo de mercado + escenario
MARKET_TEXTS = {
    "corners": {
        "over_high_conf": [
            "Ambos equipos presionan alto y generan muchos córners desde los costados. Estadísticamente, este tipo de choque suele superar los {line} saques de esquina.",
            "El estilo de juego dominante del local genera una alta frecuencia de tiros de esquina. El promedio de estos equipos supera {line} córners por partido.",
        ],
        "under_high_conf": [
            "Se espera un partido cerrado con pocas llegadas por banda. La defensa del equipo visitante suele ahogar el juego atacante rivalizando el volumen de córners.",
        ],
        "generic": [
            "El análisis táctico de ambos equipos indica una frecuencia de tiros de esquina que apoya esta línea.",
        ]
    },
    "totals": {
        "over_high_conf": [
            "Ninguno de estos equipos es compacto defensivamente. El promedio combinado de goles en los últimos 10 partidos supera fácilmente la línea de {line}.",
            "Partido de alta intensidad ofensiva esperado. Las estadísticas xG de ambos combinados superan el valor de {line} goles.",
        ],
        "under_high_conf": [
            "Partido de alta disputa táctica con pocas ocasiones claras esperadas. El total de goles por partido de estos equipos suele quedar por debajo de {line}.",
            "El visitante llega con un esquema defensivo muy compacto. El mercado refleja una probabilidad alta de menos de {line} goles.",
        ],
        "generic": [
            "La línea de goles proyectada es coherente con el historial reciente de estos equipos.",
        ]
    },
    "h2h": {
        "favorite_high_conf": [
            "{team} llega con una racha de victorias importante y una superioridad de ELO que el mercado no refleja del todo. Cuota con buen valor.",
            "La calidad individual de {team} es notoriamente superior. El modelo estima que este resultado es incluso más probable de lo que la cuota implica.",
        ],
        "underdog_upset": [
            "Cuota sorprendentemente baja para {team} dada la paridad histórica entre estos equipos. El modelo detecta cierto valor.",
        ],
        "generic": [
            "El modelo proyecta una probabilidad ligeramente superior a la que la cuota implica, lo que genera valor esperado positivo.",
        ]
    },
    "double_chance": {
        "generic": [
            "{team} necesita al menos un punto en este partido para su clasificación. La apuesta de Doble Oportunidad cubre la victoria y el empate a una cuota con margen.",
            "Aunque no se proyecta como equipo dominante en este partido, la Doble Oportunidad para {team} es el mercado más seguro según el modelo.",
        ]
    },
    "btts": {
        "yes": [
            "Ambos equipos anotan en alta proporción de sus partidos. El modelo estima que la probabilidad de que marque los dos supera la cuota implícita.",
        ],
        "no": [
            "El visitante llega con una defensa sólida que suele mantener la portería a cero. La probabilidad de que alguno no anote es alta.",
        ]
    },
    "cards": {
        "over_high_conf": [
            "Históricamente este tipo de encuentros acumula muchas tarjetas. El árbitro designado tiene un promedio alto de amonestaciones por partido, lo que refuerza la línea de más de {line} tarjetas.",
            "La intensidad esperada del partido y el historial de sanciones entre estos equipos sugiere superar la línea de {line} tarjetas.",
        ],
        "under_high_conf": [
            "Ambos equipos tienen un juego limpio notable y el árbitro asignado suele ser conservador con las tarjetas. Menos de {line} tarjetas es estadísticamente probable.",
        ],
        "generic": [
            "El análisis de tarjetas se basa en el historial disciplinario de ambas selecciones y el perfil del árbitro asignado.",
        ]
    },
    "first_goal": {
        "generic": [
            "La estadística muestra que en partidos de esta fase del torneo, el primer gol suele llegar temprano. La línea refleja la tendencia ofensiva de estos equipos.",
            "El modelo proyecta que la apertura del marcador ocurra dentro de la primera mitad, basándose en datos xG y ritmo de juego de ambas selecciones.",
        ]
    },
    "shots_on_target": {
        "generic": [
            "El promedio de tiros al arco de estos equipos respalda esta selección. Las métricas xG indican un alto volumen de remates encuadrados.",
            "El análisis de remates al arco por partido de ambos combinados apoya la línea seleccionada con buena confianza.",
        ]
    },
    "draw_no_bet": {
        "generic": [
            "Empate No Apuesta elimina el riesgo del empate, dando una apuesta de seguridad sobre {team}. El modelo estima buena probabilidad a favor.",
            "Con la protección del empate incluida, esta selección ofrece un margen de seguridad atractivo para {team}.",
        ]
    },
    "handicap": {
        "generic": [
            "El handicap {line} ajusta la línea a favor de {team}, compensando la diferencia de nivel entre ambos equipos según el modelo.",
            "La línea de handicap refleja la diferencia proyectada en el marcador. El análisis de xG y ELO respalda la selección.",
        ]
    },
    "asian_handicap": {
        "generic": [
            "El Handicap Asiático {line} ofrece una línea ajustada basada en la superioridad estimada. El modelo encuentra valor en esta selección.",
        ]
    },
    "half_time": {
        "generic": [
            "El resultado al descanso favorece a {team} según las tendencias de estos equipos en primeros tiempos. El modelo analiza la intensidad inicial de ambas selecciones.",
            "Históricamente, estos equipos definen el rumbo del partido en la primera mitad. La selección del descanso es coherente con el patrón táctico esperado.",
        ]
    },
    "generic": [
        "El modelo algorítmico identifica valor positivo en esta apuesta respecto a la probabilidad real estimada.",
        "Esta selección tiene una probabilidad real superior a la que la cuota implica, generando valor esperado positivo.",
    ]
}


def _get_line_from_selection(selection: str) -> str:
    """Extrae la línea numérica de una selección como 'Más de 2.5'."""
    parts = selection.split()
    for p in parts:
        try:
            float(p)
            return p
        except ValueError:
            continue
    return "X"


def analyze_fijini(fijini_dict: dict, home_team: str, away_team: str,
                   home_stats: dict, away_stats: dict) -> dict:
    price = fijini_dict.get("price", 1.15)
    implied_prob = round((1.0 / price) * 100, 1)
    selection = fijini_dict.get("selection", "")
    market_key = fijini_dict.get("market_key", fijini_dict.get("market", "")).lower()

    # ── Feature Engineering ──────────────────────────────────────────────────
    def calc_form(stats):
        if not stats or "fixtures" not in stats:
            return 0.0
        w = float(stats["fixtures"].get("wins", {}).get("total", 0))
        l = float(stats["fixtures"].get("loses", {}).get("total", 0))
        return w - l

    def calc_goals(stats):
        if not stats or "goals" not in stats:
            return 0.0
        gf = float(stats["goals"].get("for", {}).get("average", {}).get("total", 1.2))
        ga = float(stats["goals"].get("against", {}).get("average", {}).get("total", 1.0))
        return gf - ga

    form_home = calc_form(home_stats)
    form_away = calc_form(away_stats)
    form_diff = form_home - form_away
    goal_diff = calc_goals(home_stats) - calc_goals(away_stats)
    h2h_dom = 0.5 + (form_diff * 0.04)

    # ── Probabilidad Real ─────────────────────────────────────────────────────
    # Prioridad 1: Simulación Monte Carlo (lo más preciso)
    mc_result = None
    try:
        from ml.fijini_simulator import simulate_fijini
        mc_result = simulate_fijini(
            home_team=home_team,
            away_team=away_team,
            market_key=market_key,
            selection=selection,
            price=price,
            n_simulations=10_000
        )
        actual_prob = mc_result["mc_probability"]
    except Exception:
        mc_result = None

    # Prioridad 2: Modelo ML entrenado
    if mc_result is None and ml_model is not None:
        try:
            import pandas as pd
            feats = pd.DataFrame([[form_diff, goal_diff, h2h_dom]],
                                  columns=["form_diff", "goal_diff_avg", "h2h_dominance"])
            prob_ml = ml_model.predict_proba(feats)[0][1] * 100
            actual_prob = prob_ml if prob_ml >= 50 else (100 - prob_ml)
        except Exception:
            actual_prob = implied_prob * 1.05

    # Prioridad 3: Estimación heurística (fallback)
    if mc_result is None and ml_model is None:
        base = implied_prob
        boost = 0.0

        if "corner" in market_key or "córner" in market_key:
            boost = 2.5 if price < 1.20 else 1.5
        elif "total" in market_key or "gole" in market_key:
            boost = 3.0 if price < 1.20 else 1.8
        elif "h2h" in market_key or "ganador" in market_key:
            boost = 2.0 if price < 1.35 else 0.5
        elif "double" in market_key or "doble" in market_key:
            boost = 3.5
        elif "btts" in market_key or "ambos" in market_key:
            boost = 1.0
        elif "card" in market_key or "tarjeta" in market_key:
            boost = 1.5
        else:
            boost = 2.0

        if abs(form_diff) > 2:
            boost += 1.5
        elif abs(form_diff) > 1:
            boost += 0.8

        actual_prob = min(98.0, max(15.0, base + boost))

    actual_prob = round(actual_prob, 1)

    # ── Valor ─────────────────────────────────────────────────────────────────
    edge = actual_prob - implied_prob
    edge_pct = round(edge, 2)
    if edge > 8:
        color = "GREEN"
        value_tag = "valor positivo excepcional"
    elif edge > 5:
        color = "GREEN"
        value_tag = "valor positivo alto"
    elif edge > 2:
        color = "YELLOW"
        value_tag = "valor positivo marginal"
    elif edge > 0:
        color = "ORANGE"
        value_tag = "valor neutro"
    else:
        color = "RED"
        value_tag = "sin ventaja sobre el mercado"

    # ── Texto de Análisis ──────────────────────────────────────────────────────
    line = _get_line_from_selection(selection)
    is_over = "más de" in selection.lower() or "over" in selection.lower()
    is_under = "menos de" in selection.lower() or "under" in selection.lower()

    if "corner" in market_key or "córner" in market_key or "corner" in fijini_dict.get("market", "").lower():
        pool = MARKET_TEXTS["corners"]["over_high_conf" if is_over else "under_high_conf" if is_under else "generic"]
    elif "total" in market_key or "gole" in market_key:
        pool = MARKET_TEXTS["totals"]["over_high_conf" if is_over else "under_high_conf" if is_under else "generic"]
    elif "double" in market_key or "doble" in market_key:
        team = home_team if home_team.lower() in selection.lower() else away_team
        pool = [t.replace("{team}", team) for t in MARKET_TEXTS["double_chance"]["generic"]]
    elif "btts" in market_key or "ambos" in market_key:
        pool = MARKET_TEXTS["btts"]["yes" if "sí" in selection.lower() else "no"]
    elif "card" in market_key or "tarjeta" in market_key:
        pool = MARKET_TEXTS["cards"]["over_high_conf" if is_over else "under_high_conf" if is_under else "generic"]
    elif "first_goal" in market_key or "primer gol" in market_key:
        pool = MARKET_TEXTS["first_goal"]["generic"]
    elif "shots" in market_key or "tiro" in market_key:
        pool = MARKET_TEXTS["shots_on_target"]["generic"]
    elif "draw_no_bet" in market_key or "empate no" in market_key:
        team = home_team if home_team.lower() in selection.lower() else away_team
        pool = [t.replace("{team}", team) for t in MARKET_TEXTS["draw_no_bet"]["generic"]]
    elif "handicap" in market_key or "asian" in market_key:
        team = home_team if home_team.lower() in selection.lower() else away_team
        mk = "asian_handicap" if "asian" in market_key else "handicap"
        pool = [t.replace("{team}", team) for t in MARKET_TEXTS.get(mk, MARKET_TEXTS["handicap"])["generic"]]
    elif "half_time" in market_key or "descanso" in market_key:
        team = home_team if home_team.lower() in selection.lower() else away_team
        pool = [t.replace("{team}", team) for t in MARKET_TEXTS["half_time"]["generic"]]
    elif "h2h" in market_key or "ganador" in market_key:
        team = home_team if home_team.lower() in selection.lower() else away_team
        pool = [t.replace("{team}", team) for t in MARKET_TEXTS["h2h"]["favorite_high_conf" if price < 1.40 else "generic"]]
    else:
        pool = MARKET_TEXTS["generic"]

    import random
    analysis_text_base = random.choice(pool).replace("{line}", line).replace("{team}", home_team)

    if edge > 2:
        try:
            from llm.groq_client import generate_bet_analysis
            groq_analysis = generate_bet_analysis(
                home_team=home_team,
                away_team=away_team,
                market_key=market_key,
                selection=selection,
                actual_prob=actual_prob,
                implied_prob=implied_prob,
                edge=edge_pct,
                home_stats=home_stats,
                away_stats=away_stats,
                mc_result=mc_result
            )
            if groq_analysis and "El modelo encuentra valor" not in groq_analysis:
                analysis_text_base = groq_analysis
        except Exception:
            pass

    text = (f"El modelo proyecta un {actual_prob}% de probabilidad real "
            f"(cuota implica {implied_prob}%). {analysis_text_base} "
            f"→ {value_tag}.")

    return {
        "color": color,
        "text": text,
        "actual_probability": actual_prob,
        "implied_probability": implied_prob,
        "edge_percentage": edge_pct,
        "monte_carlo": mc_result if mc_result else {"status": "No disponible — usando estimación heurística"},
        "source": "monte_carlo" if mc_result else ("ml_model" if ml_model else "heuristic"),
    }
