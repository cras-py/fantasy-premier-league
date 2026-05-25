import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# FPL API Endpoints
BASE_URL = "https://fantasy.premierleague.com/api"

ENDPOINTS = {
    "bootstrap": f"{BASE_URL}/bootstrap-static/",
    "fixtures": f"{BASE_URL}/fixtures/",
    "player_summary": f"{BASE_URL}/element-summary/{{player_id}}/",
    "live_gw": f"{BASE_URL}/event/{{gw_id}}/live/",
    "entry": f"{BASE_URL}/entry/{{entry_id}}/",
    "entry_history": f"{BASE_URL}/entry/{{entry_id}}/history/",
    "entry_picks": f"{BASE_URL}/entry/{{entry_id}}/event/{{gw_id}}/picks/",
    "league_standings": f"{BASE_URL}/leagues-classic/{{league_id}}/standings/",
}

# Request headers to look like a standard browser request
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

# Ensure data directories exist
def create_directories():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(RAW_DIR / "players", exist_ok=True)
    os.makedirs(RAW_DIR / "gameweeks", exist_ok=True)
    os.makedirs(RAW_DIR / "user", exist_ok=True)
    os.makedirs(RAW_DIR / "league", exist_ok=True)
