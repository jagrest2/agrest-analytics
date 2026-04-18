import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

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

# 3. Single Game Simulation Endpoint
@app.get("/simulate")
def simulate(home: str, away: str):
    """
    Calls your existing basketball logic to run a single PBP game.
    """
    # Assuming your function is named run_full_game_pbp inside simulation.py
    score_h, score_a, game_log, stats = simulation.run_full_game_pbp(home, away)
    
    return {
        "home_score": score_h,
        "away_score": score_a,
        "log": game_log,
        "stats": stats
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