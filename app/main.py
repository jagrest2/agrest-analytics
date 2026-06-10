import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import random

# Note: Make sure your "model.py" file is renamed to "simulation.py" 
# so this import works correctly!
try:
    from . import simulation
except ImportError:
    import app.simulation as simulation

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/teams")
def get_teams():
    # FIX: Point to the exact directory where the CSV lives
    df = pd.read_csv("app/data/kp_1220.csv")
    
    # Clean up the data: drop empty rows and ensure everything is a string
    df = df.dropna(subset=['Team'])
    df['Team'] = df['Team'].astype(str)
    
    # Get unique team names and sort them alphabetically
    teams = sorted(df['Team'].unique().tolist())
    return {"teams": teams}

# CHANGED: Endpoint matches HTML fetch, and home_court defaults to False
@app.get("/simulate")
def simulate(home: str, away: str, home_court: bool = False):
    score_h, score_a = simulation.predict_score_simulated(home, away, home_court)
    if score_h == score_a:
        if random.choice([0, 1]) == 0:
            score_h += 1
        else:
            score_a += 1
    winner = home if score_h > score_a else away
    margin = abs(score_h - score_a)
    
    # Track the matchup in SQLite
    db_stats = simulation.update_count(home, away, winner, margin)
    
    t_list = sorted([home, away])
    home_series_wins = db_stats[1] if home == t_list[0] else db_stats[2]
    away_series_wins = db_stats[2] if home == t_list[0] else db_stats[1]

    return {
        "home_score": score_h,
        "away_score": score_a,
        "series_record": f"{home}: {home_series_wins} wins | {away}: {away_series_wins} wins",
        "total_sims": db_stats[0]
    }

@app.get("/batch")
def batch(home: str, away: str, home_court: bool = False, sims: int = 100):
    results = simulation.batch(home, away, home_court, iterations=100)
    return results

@app.get("/")
def read_root():
    return {"status": "Online", "message": "Visit /static/index.html to use the app"}