from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
# Import your existing functions
from . simulation import run_full_game_pbp, run_monte_carlo

app = FastAPI()

# 1. Security: Allow your website to talk to your backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Serve your HTML/CSS files
app.mount("/static", StaticFiles(directory="static"), name="static")

# 3. The Single Game Endpoint
@app.get("/simulate")
def simulate(home: str, away: str):
    score_h, score_a, log, stats = run_full_game_pbp(home, away)
    return {
        "home_score": score_h,
        "away_score": score_a,
        "game_log": log,
        "stats": stats
    }

# 4. The Batch Simulation Endpoint
@app.get("/batch")
def batch(home: str, away: str, sims: int = 1000):
    win_pct, avg_margin = run_monte_carlo(home, away, iterations=sims)
    return {
        "win_probability": win_pct,
        "projected_margin": avg_margin
    }