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
import sqlite3
from itertools import combinations


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
    try:
        # Load your team statistics
        df = pd.read_csv("app/data/2026/output3.csv")
        df = df.fillna(0)
        df = df[df["Possessions"] != 0]

        # Read your newly pre-built schedules lookup map
        json_path = "app/data/2026/schedules.json"
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                schedules_data = json.load(f)
            
            # Map the clean opponent arrays straight into each row record
            df['Opponents'] = df['Team'].map(lambda team_name: schedules_data.get(team_name.strip(), []))
        else:
            df['Opponents'] = [[] for _ in range(len(df))]

        return df.to_dict(orient="records")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        # 1. Load the CSV file
        df = pd.read_csv("app/data/2026/output3.csv")
        
        # 2. Search for the requested team
        team_row = df[df["Team"] == name]
        
        if team_row.empty:
            return {"error": "Team not found"}
            
        # 3. Convert the row to a raw dictionary
        raw_data = team_row.iloc[0].to_dict()
        
        # 4. Clean and format every column explicitly for the frontend
        team_data = {}
        for key, val in raw_data.items():
            if pd.isna(val):
                team_data[key] = "-"
            # Format numeric metrics, but skip text columns like Team and Conference
            elif isinstance(val, (float, int)) and key not in ["Team", "Conference"]:
                # If it's a specific whole-number column like Rank, you can keep it as an int:
                if key.lower() == "rank":
                    team_data[key] = int(val)
                else:
                    team_data[key] = f"{float(val):.2f}"
            else:
                team_data[key] = val
        
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

@app.get("/api/conferences")
def get_conferences():
    file_path = "app/data/2026/conferences.json"
    
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, 
            detail="The conference analysis database file was not found on the server."
        )
    
@app.get("/api/team-analytics")
def get_team_analytics(name: str):
    """Fetches full roster efficiencies and the best lineup combinations for a specific team."""
    db_path = "agrest_analytics.db"
    if not os.path.exists(db_path):
        raise HTTPException(status_code=500, detail="Database not found.")
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Lookup Team ID based on the display name
    cursor.execute("""
        SELECT team_id
        FROM teams
        WHERE display_name = ?
        OR display_name LIKE ? || ' %'
        COLLATE NOCASE
        """, (name, name))
    team_row = cursor.fetchone()
    if not team_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Team not found in master database.")
    team_id = team_row["team_id"]

    # 2. Get the Master Roster for this team to map IDs to Names
    cursor.execute("SELECT player_id, full_name, jersey, position FROM players WHERE team_id = ?", (team_id,))
    players_dict = {str(row["player_id"]): dict(row) for row in cursor.fetchall()}

    # 3. Load all stints for this team
    cursor.execute("""
        SELECT p1, p2, p3, p4, p5, possessions, points_for, points_against, seconds_played 
        FROM lineup_stints WHERE team_id = ?
    """, (team_id,))
    stints = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # 4. In-Memory Combinatorics Engine
    combo_stats = {}
    
    for stint in stints:
        # Extract active players, ignoring empty slots or UNKNOWN errors
        lineup = [str(stint[f"p{i}"]) for i in range(1, 6) if stint[f"p{i}"] and stint[f"p{i}"] != "UNKNOWN"]
        poss = stint["possessions"]
        
        if poss == 0 and stint["seconds_played"] == 0:
            continue
            
        # Explode this stint into 1-man, 2-man, 3-man, 4-man, and 5-man sub-combinations
        for r in range(1, len(lineup) + 1):
            for combo in combinations(lineup, r):
                combo_key = tuple(sorted(combo))
                if combo_key not in combo_stats:
                    combo_stats[combo_key] = {"poss": 0.0, "pf": 0, "pa": 0, "secs": 0}
                
                combo_stats[combo_key]["poss"] += poss
                combo_stats[combo_key]["pf"] += stint["points_for"]
                combo_stats[combo_key]["pa"] += stint["points_against"]
                combo_stats[combo_key]["secs"] += stint["seconds_played"]

    # 5. Format the data for the Frontend
    roster_stats = []
    best_lineups = {2: [], 3: [], 4: [], 5: []}

    for combo_key, stats in combo_stats.items():
        poss = stats["poss"]
        if poss == 0:
            continue

        off_eff = (stats["pf"] / poss) * 100.0
        def_eff = (stats["pa"] / poss) * 100.0
        net_eff = off_eff - def_eff
        
        names = [players_dict.get(pid, {}).get("full_name", f"Unknown ({pid})") for pid in combo_key]
        
        record = {
            "ids": list(combo_key),
            "names": names,
            "possessions": round(poss, 1),
            "minutes": round(stats["secs"] / 60.0, 1),
            "off_eff": round(off_eff, 2),
            "def_eff": round(def_eff, 2),
            "net_eff": round(net_eff, 2)
        }

        size = len(combo_key)
        if size == 1:
            pid = combo_key[0]
            record["jersey"] = players_dict.get(pid, {}).get("jersey", "-")
            record["position"] = players_dict.get(pid, {}).get("position", "-")
            # Only include players who actually played
            if record["minutes"] > 0:
                roster_stats.append(record)
        elif size in best_lineups and poss >= 20: # Must have at least 20 possessions together!
            best_lineups[size].append(record)

    # Sort Roster by Minutes Played
    roster_stats.sort(key=lambda x: x["minutes"], reverse=True)
    
    # Sort Lineups by Net Efficiency and keep the Top 10
    for size in best_lineups:
        best_lineups[size].sort(key=lambda x: x["net_eff"], reverse=True)
        best_lineups[size] = best_lineups[size][:10]

    return {
        "team_id": team_id,
        "team_name": name,
        "roster": roster_stats,
        "best_lineups": best_lineups
    }

@app.get("/api/custom-lineup")
def calculate_custom_lineup(team_id: int, pids: str):
    """Calculates efficiency for a specific user-selected combination of players."""
    conn = sqlite3.connect("agrest_analytics.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # The user sends comma-separated player IDs (e.g., "4431678,4500123")
    selected_set = set(pids.split(","))

    cursor.execute("""
        SELECT p1, p2, p3, p4, p5, possessions, points_for, points_against, seconds_played 
        FROM lineup_stints WHERE team_id = ?
    """, (team_id,))
    
    total_poss = 0.0
    total_pf = 0
    total_pa = 0
    total_secs = 0

    for row in cursor.fetchall():
        lineup = {str(row["p1"]), str(row["p2"]), str(row["p3"]), str(row["p4"]), str(row["p5"])}
        
        # Core Logic: If the selected players are a subset of the 5 guys on the floor, count the stats!
        if selected_set.issubset(lineup):
            total_poss += row["possessions"]
            total_pf += row["points_for"]
            total_pa += row["points_against"]
            total_secs += row["seconds_played"]
            
    conn.close()

    if total_poss == 0:
        return {"error": "This combination has not logged a single possession together."}

    off_eff = (total_pf / total_poss) * 100.0
    def_eff = (total_pa / total_poss) * 100.0
    net_eff = off_eff - def_eff

    return {
        "possessions": round(total_poss, 1),
        "minutes": round(total_secs / 60.0, 1),
        "off_eff": round(off_eff, 2),
        "def_eff": round(def_eff, 2),
        "net_eff": round(net_eff, 2)
    }


# Enable CORS so your frontend can communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/ratings/{season}")
async def get_ratings(season: int):
    try:
        conn = sqlite3.connect("app/ratings.db")
        cursor = conn.cursor()

        # Check against both string and int representation to catch SQLite type mismatches
        cursor.execute(
            "SELECT * FROM efficiency_ratings WHERE season = ? OR season = ?", 
            (str(season), season)
        )
        
        # Check if query returned columns/rows
        if not cursor.description:
            conn.close()
            return []

        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return []

        # Convert SQLite rows to a list of dicts
        data = [dict(zip(columns, row)) for row in rows]
        return data

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ALWAYS AT BOTTOM
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
