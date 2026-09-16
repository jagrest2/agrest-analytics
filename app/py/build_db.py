import sqlite3
import time
import requests

def build_master_database(db_path="agrest_analytics.db"):
    print("Initializing SQLite database and creating tables...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Create Teams Table
    cursor.execute("DROP TABLE IF EXISTS teams;")
    cursor.execute("""
    CREATE TABLE teams (
        team_id INTEGER PRIMARY KEY,
        abbreviation TEXT,
        display_name TEXT,
        conference TEXT
    );
    """)
    
    # 2. Create Players Table
    cursor.execute("DROP TABLE IF EXISTS players;")
    cursor.execute("""
    CREATE TABLE players (
        player_id TEXT PRIMARY KEY,
        team_id INTEGER,
        full_name TEXT,
        jersey TEXT,
        position TEXT,
        FOREIGN KEY (team_id) REFERENCES teams (team_id)
    );
    """)
    
    # 3. Fetch all D1 Teams from ESPN API
    print("Fetching Division I teams from ESPN API...")
    teams_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=400"
    
    try:
        response = requests.get(teams_url).json()
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to connect to ESPN teams endpoint: {e}")
        return
        
    # ESPN nests teams inside: sports -> leagues -> teams
    sports = response.get("sports", [])
    if not sports:
        print("Error: Could not retrieve sports data structure.")
        return
        
    leagues = sports[0].get("leagues", [])
    teams_list = leagues[0].get("teams", []) if leagues else []
    
    print(f"Found {len(teams_list)} college basketball programs. Scraping rosters...")
    
    team_records = []
    player_records = []
    
    for item in teams_list:
        team_data = item.get("team", {})
        team_id = int(team_data.get("id", 0))
        abbrev = team_data.get("abbreviation", "")
        display_name = team_data.get("displayName", "")
        
        # Get conference info if available
        groups = team_data.get("groups", {})
        conference = groups.get("name", "Independent") if isinstance(groups, dict) else "Unknown"
        
        team_records.append((team_id, abbrev, display_name, conference))
        
        # 4. Fetch the specific roster for this team ID
        roster_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{team_id}/roster"
        try:
            roster_res = requests.get(roster_url).json()
            athletes = roster_res.get("athletes", [])
            
            for athlete in athletes:
                player_id = str(athlete.get("id", "")).strip()
                full_name = athlete.get("fullName") or athlete.get("displayName", "Unknown Player")
                jersey = str(athlete.get("jersey", "")).strip()
                
                pos_obj = athlete.get("position", {})
                position = pos_obj.get("abbreviation") or pos_obj.get("name", "")
                
                if player_id:
                    player_records.append((player_id, team_id, full_name, jersey, position))
                    
        except Exception as e:
            print(f"Warning: Could not load roster for {display_name} (ID: {team_id}): {e}")
            
        # 0.1s sleep to prevent rate-limiting while looping through 360+ schools
        time.sleep(0.1)
        
    # 5. Bulk insert data into SQLite
    print(f"Inserting {len(team_records):,} teams into database...")
    cursor.executemany("INSERT OR REPLACE INTO teams VALUES (?, ?, ?, ?);", team_records)
    
    print(f"Inserting {len(player_records):,} players into database...")
    cursor.executemany("INSERT OR REPLACE INTO players VALUES (?, ?, ?, ?, ?);", player_records)
    
    # 6. Create Indexes for lightning-fast frontend and PBP lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_players_name ON players(full_name);")
    
    conn.commit()
    conn.close()
    
    print("🎉 SUCCESS: Master database created! Saved as 'agrest_analytics.db'")

if __name__ == "__main__":
    build_master_database()