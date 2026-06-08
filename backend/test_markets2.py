import os, httpx
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("ODDS_API_KEY")
for m in ["btts", "draw_no_bet"]:
    res = httpx.get(f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/?apiKey={key}&regions=eu&markets={m}")
    print(f"Market {m}: {res.status_code}")
