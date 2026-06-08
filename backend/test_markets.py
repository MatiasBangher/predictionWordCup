import os, httpx
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("ODDS_API_KEY")
markets = ["h2h", "totals", "spreads", "player_goals", "player_shots_on_target", "player_passes", "team_cards", "h2h_lay"]
for m in markets:
    res = httpx.get(f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/?apiKey={key}&regions=eu&markets={m}")
    print(f"Market {m}: {res.status_code}")
