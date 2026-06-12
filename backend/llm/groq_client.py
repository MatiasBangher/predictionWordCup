import os
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Groq client
# It will automatically pick up GROQ_API_KEY from environment variables
try:
    client = Groq()
    MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
except Exception as e:
    logger.error(f"Failed to initialize Groq client: {e}")
    client = None
    MODEL = None


def generate_bet_analysis(home_team: str, away_team: str, market_key: str, selection: str, 
                          actual_prob: float, implied_prob: float, edge: float, 
                          home_stats: dict, away_stats: dict, mc_result: dict = None) -> str:
    """
    Generates a deep, contextual analysis for a value bet using Llama 4 Scout via Groq.
    """
    if not client:
        return "El modelo encuentra valor estadístico positivo en esta selección basado en el algoritmo interno."
        
    system_prompt = (
        "Eres un experto analista táctico de fútbol y pronosticador deportivo. "
        "Tu tarea es explicar por qué una apuesta específica tiene 'valor positivo' (Edge) comparando "
        "la probabilidad real (calculada por Monte Carlo/ML) con la cuota implícita de la casa de apuestas. "
        "Sé conciso (máximo 3-4 oraciones), profesional, objetivo y persuasivo. "
        "No uses saludos ni despedidas, ve directo al análisis táctico y estadístico."
    )
    
    # Extract some basic stats to feed the prompt
    def get_wld(stats):
        if not stats or "fixtures" not in stats:
            return "N/A"
        f = stats["fixtures"]
        w = f.get("wins", {}).get("total", 0)
        d = f.get("draws", {}).get("total", 0)
        l = f.get("loses", {}).get("total", 0)
        return f"{w}V-{d}E-{l}D"

    home_form = get_wld(home_stats)
    away_form = get_wld(away_stats)
    
    user_prompt = (
        f"Partido: {home_team} vs {away_team}\n"
        f"Forma reciente: {home_team} ({home_form}), {away_team} ({away_form})\n"
        f"Mercado: {market_key} | Selección: {selection}\n"
        f"Probabilidad Implícita (Casa de Apuestas): {implied_prob}%\n"
        f"Probabilidad Real (Nuestro Modelo): {actual_prob}%\n"
        f"Ventaja (Edge): +{edge}%\n\n"
        "Escribe un breve análisis táctico que justifique esta ventaja, mencionando las tendencias de los equipos."
    )
    
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3, # Keep it analytical and grounded
            max_tokens=150
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error calling Groq API for bet analysis: {e}")
        return "El modelo encuentra valor estadístico positivo en esta selección basado en el algoritmo interno."


def generate_match_preview(home_team: str, away_team: str, group: str, stadium: str, probs: dict) -> str:
    """
    Generates a match preview and prediction explanation using Llama 4 Scout via Groq.
    """
    if not client:
        highest_prob = max(probs["home_win"], probs["draw"], probs["away_win"])
        return f"El modelo proyecta una probabilidad de {highest_prob}% para el resultado más probable."
        
    system_prompt = (
        "Eres un comentarista experto de la Copa del Mundo 2026. "
        "Tu tarea es generar una previa narrativa corta de 3 a 4 oraciones sobre un partido, "
        "resaltando el pronóstico de nuestro modelo de Inteligencia Artificial."
    )
    
    user_prompt = (
        f"Partido: {home_team} vs {away_team}\n"
        f"Contexto: {group}, {stadium}\n"
        f"Probabilidades del Modelo IA:\n"
        f"- Victoria {home_team}: {probs['home_win']}%\n"
        f"- Empate: {probs['draw']}%\n"
        f"- Victoria {away_team}: {probs['away_win']}%\n\n"
        "Escribe la previa destacando el resultado más probable, la dinámica esperada del partido "
        "y algún toque de color sobre el Mundial (ej: presión del estadio, necesidad de puntos)."
    )
    
    try:
        completion = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7, # Slightly more creative for match previews
            max_tokens=200
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error calling Groq API for match preview: {e}")
        highest_prob = max(probs["home_win"], probs["draw"], probs["away_win"])
        return f"El modelo proyecta una probabilidad de {highest_prob}% para el resultado más probable."
