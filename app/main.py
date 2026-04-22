import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

# The '.' tells Python to look in the current folder (app/) for simulation.py
try:
    from . import simulation
except ImportError:
    # This fallback helps if you are running it locally in certain environments
    import simulation

app = FastAPI()

# 1. CORS Setup: Vital for your HTML/CSS to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Path Logic: Finding the 'static' folder relative to this file
# This ensures it works on Render and your local machine
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_path = os.path.join(BASE_DIR, "static")

# Serve your HTML/CSS files
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/teams")
def get_teams():
    # Load your CSV (using the path logic we set up earlier)
    df = pd.read_csv("app/data/EFG_Data_V1.csv")
    # Get unique team names and sort them alphabetically
    teams = sorted(df['team'].unique().tolist())
    return {"teams": teams}

# 3. Single Game Simulation Endpoint
@app.get("/simulate")
def simulate(home: str, away: str):
    """
    Calls your existing basketball logic to run a single PBP game.
    """
    # Assuming your function is named run_full_game_pbp inside simulation.py
    score_h, score_a, game_log, stats = simulation.run_full_game_pbp(home, away)
    
    winner = home if score_h > score_a else away
    margin = abs(score_h - score_a)
        
    # 3. Update the SQLite DB and get the aggregate record
    # This calls your function and returns (sim_count, wins_min, wins_max, blow_min, blow_max)
    db_stats = simulation.update_count(home, away, winner, margin)
        
    # 4. Map the DB stats back to the specific Home/Away teams
    # (Since the DB stores them alphabetically, we have to check which is which)
    t_list = sorted([home, away])
    home_series_wins = db_stats[1] if home == t_list[0] else db_stats[2]
    away_series_wins = db_stats[2] if home == t_list[0] else db_stats[1]

    return {
        "home_score": score_h,
        "away_score": score_a,
        "log": game_log,
        "series_record": f"{home}: {home_series_wins} wins | {away}: {away_series_wins} wins",
        "total_sims": db_stats[0]
    }

# 4. Monte Carlo / Batch Endpoint
@app.get("/batch")
def batch(home: str, away: str, sims: int = 1000):
    """
    Runs multiple simulations to find win probability and average margin.
    """
    win_pct, avg_margin = simulation.run_monte_carlo(home, away, iterations=sims)
    
    return {
        "home_team": home,
        "away_team": away,
        "win_probability": win_pct,
        "projected_margin": avg_margin
    }

# Root redirect for convenience
@app.get("/")
def read_root():
    return {"status": "Online", "message": "Visit /static/index.html to use the app"}