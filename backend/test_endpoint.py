import asyncio
from main import get_matchday_fijinis
import json

def test():
    import time
    start = time.time()
    res = get_matchday_fijinis(1)
    end = time.time()
    print(f"Time taken: {end - start:.2f}s")
    print(f"Total matches: {res.get('total_matches')}")
    print(f"Total fijinis: {res.get('total_fijinis')}")
    print(f"Green value bets: {res.get('green_value_bets')}")
    if res.get("data") and res["data"][0]["fijinis"]:
        print("\nSample fijini simulation result:")
        print(json.dumps(res["data"][0]["fijinis"][0], indent=2, ensure_ascii=False))
        
if __name__ == "__main__":
    test()
