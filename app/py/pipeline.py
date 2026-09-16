import os
import sqlite3
import requests
import pandas as pd
from dotenv import load_dotenv

# Load API key from environment
load_dotenv()
API_KEY = os.getenv("CBB_API_KEY")

# Choose endpoint (CollegeBasketballData API or CBBData API endpoint)
BASE_URL = "https://api.collegebasketballdata.com"  # or https://api.cbbdata.aweatherman.com
DB_NAME = "agrest_analytics.db"


def get_db_connection():
    """Establish connection to SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create initial schema for college basketball team ratings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_ratings (
            team_id TEXT PRIMARY KEY,
            team_name TEXT NOT NULL,
            conference TEXT,
            season INTEGER NOT NULL,
            adj_o REAL,
            adj_d REAL,
            net_rating REAL,
            tempo REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()


def fetch_cbb_ratings(season=2026):
    """Fetch seasonal efficiency ratings from the API."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }
    
    # Example endpoint for adjusted metrics
    endpoint = f"{BASE_URL}/ratings/adjusted"
    params = {"season": season}
    
    response = requests.get(endpoint, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"API Request Failed [{response.status_code}]: {response.text}")
        return None


def upsert_ratings(data, season=2026):
    """Insert or update team ratings into SQLite."""
    if not data:
        print("No data received to database.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    upsert_query = """
        INSERT INTO team_ratings (team_id, team_name, conference, season, adj_o, adj_d, net_rating, tempo)
        VALUES (:team_id, :team, :conference, :season, :adj_o, :adj_d, :net_rating, :tempo)
        ON CONFLICT(team_id) DO UPDATE SET
            adj_o = excluded.adj_o,
            adj_d = excluded.adj_d,
            net_rating = excluded.net_rating,
            tempo = excluded.tempo,
            updated_at = CURRENT_TIMESTAMP;
    """

    # Format records for insertion
    records = []
    for row in data:
        records.append({
            "team_id": f"{row.get('team', '')}_{season}",
            "team": row.get("team"),
            "conference": row.get("conference"),
            "season": season,
            "adj_o": row.get("offense", {}).get("rating") if isinstance(row.get("offense"), dict) else row.get("adj_o"),
            "adj_d": row.get("defense", {}).get("rating") if isinstance(row.get("defense"), dict) else row.get("adj_d"),
            "net_rating": row.get("net_rating"),
            "tempo": row.get("tempo")
        })

    cursor.executemany(upsert_query, records)
    conn.commit()
    print(f"Successfully upserted {len(records)} team records into SQLite.")
    conn.close()


if __name__ == "__main__":
    init_db()
    ratings_data = fetch_cbb_ratings(season=2026)
    if ratings_data:
        upsert_ratings(ratings_data, season=2026)