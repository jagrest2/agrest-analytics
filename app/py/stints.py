import sqlite3
import pandas as pd

def extract_starters(pbp_df, team_id):
    """
    Deduces the starting 5 by scanning the first half chronologically.
    If a player does ANYTHING (shoots, fouls, subs out) before subbing in, they are a starter.
    """
    starters = set()
    subbed_in = set()
    
    # Isolate Period 1 for this team, sorting time descending (from 1200s down to 0s)
    team_plays = pbp_df[(pbp_df['team_id'] == team_id) & (pbp_df['period'] == 1)].sort_values(by=['timestamp_secs'], ascending=[False])
    
    for _, play in team_plays.iterrows():
        p_id = str(play['player_id']).strip() if pd.notna(play['player_id']) else None
        event = play['event_type']
        
        if not p_id or p_id == 'None':
            continue
            
        if event == "SUB_IN":
            subbed_in.add(p_id)
        else:
            # If they log a stat or sub out BEFORE ever subbing in, they started the game.
            if p_id not in subbed_in:
                starters.add(p_id)
                
        if len(starters) == 5:
            break
            
    return starters

def save_stint(records, game_id, team_id, lineup_set, stats):
    """Saves the active stint to the master record list."""
    if stats['secs'] > 0 or stats['poss'] > 0 or stats['pts_for'] > 0:
        players = sorted(list(lineup_set))
        
        # ESPN Data Glitch Guard: Pad with UNKNOWN if they missed tracking a player
        while len(players) < 5:
            players.append("UNKNOWN")
            
        records.append({
            "game_id": game_id,
            "team_id": team_id,
            "p1": players[0],
            "p2": players[1],
            "p3": players[2],
            "p4": players[3],
            "p5": players[4],  # Slices at 5 just in case ESPN missed a sub-out and logged 6 players
            "seconds_played": stats['secs'],
            "possessions": stats['poss'],
            "points_for": stats['pts_for'],
            "points_against": stats['pts_against']
        })

def rebuild_lineup_stints(db_path="agrest_analytics.db"):
    print("Connecting to database and initializing fresh stint table...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("DROP TABLE IF EXISTS lineup_stints;")
    cursor.execute("""
    CREATE TABLE lineup_stints (
        stint_id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT,
        team_id INTEGER,
        p1 TEXT, p2 TEXT, p3 TEXT, p4 TEXT, p5 TEXT,
        seconds_played INTEGER,
        possessions REAL,
        points_for INTEGER,
        points_against INTEGER
    );
    """)
    
    games_df = pd.read_sql_query("SELECT DISTINCT game_id FROM games_pbp", conn)
    print(f"Rebuilding stints across {len(games_df):,} total games...")
    
    stint_records = []

    for idx, game in games_df.iterrows():
        game_id = game['game_id']
        
        query = """
        SELECT period, timestamp_secs, event_type, team_id, player_id, points
        FROM games_pbp 
        WHERE game_id = ? 
        ORDER BY period ASC, timestamp_secs DESC
        """
        pbp = pd.read_sql_query(query, conn, params=(game_id,))
        
        current_lineups = {}
        stint_stats = {}
        
        # Initialize the Starting 5 for both teams before the clock starts
        teams_in_game = pbp['team_id'].dropna().unique()
        for t_id in teams_in_game:
            current_lineups[t_id] = extract_starters(pbp, t_id)
            stint_stats[t_id] = {'secs': 0, 'poss': 0.0, 'pts_for': 0, 'pts_against': 0}
        
        last_timestamp = None
        
        for _, play in pbp.iterrows():
            t_id = play['team_id']
            p_id = str(play['player_id']).strip() if pd.notna(play['player_id']) else None
            event = play['event_type']
            pts = play['points']
            current_time = play['timestamp_secs']
            
            # --- SUBSTITUTION LOGIC ---
            if event == "SUB_IN" and p_id and pd.notna(t_id):
                save_stint(stint_records, game_id, t_id, current_lineups.get(t_id, set()), stint_stats.get(t_id, {}))
                stint_stats[t_id] = {'secs': 0, 'poss': 0.0, 'pts_for': 0, 'pts_against': 0}
                if t_id in current_lineups:
                    current_lineups[t_id].add(p_id)
                
            elif event == "SUB_OUT" and p_id and pd.notna(t_id):
                save_stint(stint_records, game_id, t_id, current_lineups.get(t_id, set()), stint_stats.get(t_id, {}))
                stint_stats[t_id] = {'secs': 0, 'poss': 0.0, 'pts_for': 0, 'pts_against': 0}
                if t_id in current_lineups and p_id in current_lineups[t_id]:
                    current_lineups[t_id].remove(p_id)

            # --- STAT ATTRIBUTION ---
            if pts > 0 and pd.notna(t_id) and t_id in current_lineups:
                stint_stats[t_id]['pts_for'] += pts
                # Award points_against to the opposing team currently on the floor
                for opp_id in current_lineups:
                    if opp_id != t_id:
                        stint_stats[opp_id]['pts_against'] += pts
            
            # Estimate possession change triggers
            if event in ["FGA", "TOV"] and pd.notna(t_id) and t_id in current_lineups:
                stint_stats[t_id]['poss'] += 1.0

            # Accumulate time between plays
            if last_timestamp is not None and current_time < last_timestamp:
                time_delta = last_timestamp - current_time
                for team in current_lineups:
                    stint_stats[team]['secs'] += time_delta
                        
            last_timestamp = current_time
            
            # Handle Halftime/Overtime resets (where timestamps jump back up to 1200 or 300)
            if current_time == 0:
                last_timestamp = None
                
        # End of Game: Save final stints on the floor
        for t_id in current_lineups:
            save_stint(stint_records, game_id, t_id, current_lineups[t_id], stint_stats[t_id])

        # Progress tracker for the terminal
        if (idx + 1) % 500 == 0:
            print(f"Processed {idx + 1:,} / {len(games_df):,} games...")

    print(f"\nBulk inserting {len(stint_records):,} calculated stints into database...")
    stints_df = pd.DataFrame(stint_records)
    stints_df.to_sql("lineup_stints", conn, if_exists="append", index=False)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stints_team ON lineup_stints(team_id);")
    conn.commit()
    conn.close()
    
    print("\n🎉 SUCCESS: 5-Man Lineup Stint Engine fully rebuilt!")

if __name__ == "__main__":
    rebuild_lineup_stints()