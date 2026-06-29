import os
from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import random
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import json
from fastapi import HTTPException


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
    df = pd.read_csv("app/data/2026/output3.csv")
    
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
def batch(home: str, away: str, home_court: bool = False, games: int = 100):
    print(f"--- SERVER RECEIVED GAMES: {games} ---") # <-- Add this
    results = simulation.batch(home, away, home_court, iterations=games)
    return results

@app.get("/")
def read_root():
    return {"status": "Online", "message": "Visit /static/index.html to use the app"}

# Calculate the exact, absolute path to your 'static' folder on your hard drive
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(CURRENT_DIR, "static")
TABLE_HTML_PATH = os.path.join(STATIC_DIR, "table.html")
TEAM_HTML_PATH = os.path.join(STATIC_DIR, "team.html")

# 1. Your Data API Endpoint (The frontend JavaScript calls this)
@app.get("/api/efficiencies")
async def get_efficiencies():
    df = pd.read_csv("app/data/2026/output3.csv")
    df = df.fillna(0)
    df = df[df["Possessions"] != 0]
    return df.to_dict(orient="records")

# 2. ROUTE FALLBACK A: If you type http://127.0.0.1:8000/table
@app.get("/table")
async def serve_table_no_ext():
    if os.path.exists(TABLE_HTML_PATH):
        return FileResponse(TABLE_HTML_PATH)
    return {"error": f"Could not find table.html at verified path: {TABLE_HTML_PATH}"}

# 3. ROUTE FALLBACK B: If you type http://127.0.0.1:8000/table.html
@app.get("/table.html")
async def serve_table_with_ext():
    if os.path.exists(TABLE_HTML_PATH):
        return FileResponse(TABLE_HTML_PATH)
    return {"error": f"Could not find table.html at verified path: {TABLE_HTML_PATH}"}

# --- TEAM PROFILE API ENDPOINT ---
@app.get("/api/team-profile")
async def get_team_profile(name: str):
    try:
        # Load the exact same file your efficiencies table uses
        df = pd.read_csv("app/data/2026/output3.csv")
        
        # Search the 'Team' column for the requested name
        team_row = df[df["Team"] == name]
        
        if team_row.empty:
            return {"error": "Team not found"}
            
        # Convert that single matching row into a dictionary to send to JS
        # .fillna("-") handles any blank CSV cells so JSON doesn't crash
        team_data = team_row.fillna("-").iloc[0].to_dict()
        
        return team_data
        
    except Exception as e:
        return {"error": f"Failed to load data: {str(e)}"}
    

@app.get("/api/player-stats")
async def get_player_stats():
    try:
        # This calculates the exact folder main.py lives in
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, "player_stats4.json")
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found. Looked in: {file_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ROUTE FALLBACK A: /team ---
@app.get("/team")
async def serve_team_no_ext():
    if os.path.exists(TEAM_HTML_PATH):
        return FileResponse(TEAM_HTML_PATH)
    return {"error": f"Could not find team.html at verified path: {TEAM_HTML_PATH}"}

# --- ROUTE FALLBACK B: /team.html ---
@app.get("/team.html")
async def serve_team_with_ext():
    if os.path.exists(TEAM_HTML_PATH):
        return FileResponse(TEAM_HTML_PATH)
    return {"error": f"Could not find team.html at verified path: {TEAM_HTML_PATH}"}

# ALWAYS AT BOTTOM
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")