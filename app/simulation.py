import pandas as pd
import numpy as np
import requests
import streamlit as st
import sqlite3
import random

def init_db():
    conn = sqlite3.connect('matchup_tracker.db')
    c = conn.cursor()
    
    # 1. Create the base table if it doesn't exist at all
    c.execute('''CREATE TABLE IF NOT EXISTS counts 
                 (team_min TEXT, team_max TEXT, 
                  simulation_count INTEGER,
                  wins_min INTEGER DEFAULT 0,
                  wins_max INTEGER DEFAULT 0,
                  PRIMARY KEY (team_min, team_max))''')
                  
    # 2. The "Migration": Safely try to add the new blowout columns to existing tables
    try:
        c.execute("ALTER TABLE counts ADD COLUMN blowouts_min INTEGER DEFAULT 0")
        c.execute("ALTER TABLE counts ADD COLUMN blowouts_max INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        # If the columns already exist, SQLite throws an error. We just ignore it and move on!
        pass
        
    conn.commit()
    conn.close()

def update_count(t1, t2, winner_name, margin):
    t_list = sorted([t1, t2])
    t_min, t_max = t_list[0], t_list[1]
    
    # Determine win column
    win_col = "wins_min" if winner_name == t_min else "wins_max"
    
    # Determine blowout column (if margin is 20 or more)
    blowout_query = ""
    if margin >= 20:
        blowout_col = "blowouts_min" if winner_name == t_min else "blowouts_max"
        blowout_query = f", {blowout_col} = {blowout_col} + 1"
    
    conn = sqlite3.connect('matchup_tracker.db')
    c = conn.cursor()
    
    # Update total sims, wins, and potentially blowouts
    query = f'''INSERT INTO counts (team_min, team_max, simulation_count, {win_col} {', blowouts_min' if margin >= 20 and winner_name == t_min else ''} {', blowouts_max' if margin >= 20 and winner_name == t_max else ''}) 
                VALUES (?, ?, 1, 1 {', 1' if margin >= 20 else ''})
                ON CONFLICT(team_min, team_max) 
                DO UPDATE SET 
                    simulation_count = simulation_count + 1,
                    {win_col} = {win_col} + 1
                    {blowout_query}'''
                    
    c.execute(query, (t_min, t_max))
    conn.commit()
    
    c.execute("SELECT simulation_count, wins_min, wins_max, blowouts_min, blowouts_max FROM counts WHERE team_min=? AND team_max=?", (t_min, t_max))
    stats = c.fetchone()
    conn.close()
    return stats 


# Run this once at the very start of your app
init_db()

st.title("College Hoops Predictor")

# --- DATA LOADING SECTION ---
df = pd.read_csv("app/data/2026/output.csv")

df["Offense"] = pd.to_numeric(df["Offensive"], errors='coerce')
df["Defense"] = pd.to_numeric(df["Defensive"], errors='coerce')
df["Poss"] = pd.to_numeric(df["Possessions"], errors='coerce')

# --- LOGIC FUNCTIONS ---
def exp_poss(home, away):
    home_p = df.loc[df['Team'].str.contains(home, case=False, na=False), 'Poss'].iloc[0]
    away_p = df.loc[df['Team'].str.contains(away, case=False, na=False), 'Poss'].iloc[0]
    return 69 - (69 - home_p) - (69 - away_p) if (home_p < 69 and away_p < 69) else 69 + (home_p - 69) + (away_p - 69) if (home_p > 69 and away_p > 69) else (home_p + away_p) / 2
    
def predict_score(home, away, home_court):
    exponent, points_multiplier = 2.5, 0.89
    h_off, a_off = df.loc[df['Team'] == home, 'Offense'].iloc[0], df.loc[df['Team'] == away, 'Offense'].iloc[0]
    h_def, a_def = df.loc[df['Team'] == home, 'Defense'].iloc[0], df.loc[df['Team'] == away, 'Defense'].iloc[0]
    tempo = exp_poss(home, away)
    h_s_off, a_s_off = (h_off / 100)**exponent * tempo, (a_off / 100)**exponent * tempo
    h_s_def, a_s_def = (h_def / 100)**exponent * tempo, (a_def / 100)**exponent * tempo
    h_pts = round((h_s_off + a_s_def)/2 * points_multiplier + (2 if home_court else 0), 2)
    a_pts = round((a_s_off + h_s_def)/2 * points_multiplier - (2 if home_court else 0), 2)
    return h_pts, a_pts

def predict_score_simulated(home, away, home_court):
    base_h, base_a = predict_score(home, away, home_court)
    return int(round(np.random.normal(base_h, 10.5))), int(round(np.random.normal(base_a, 10.5)))

def batch(home, away, home_court, iterations = 100):
    home_wins = 0
    away_wins = 0
    total_home_score = 0
    total_away_score = 0
    
    for _ in range(iterations):
        # 1. Generate the random scores using your existing function
        score_h, score_a = predict_score_simulated(home, away, home_court)
        
        # 2. Handle ties immediately in the loop
        if score_h == score_a:
            if np.random.choice([0, 1]) == 0:
                score_h += 1
            else:
                score_a += 1
                
        # 3. Aggregate wins
        if score_h > score_a:
            home_wins += 1
        else:
            away_wins += 1
            
        # 4. Aggregate scores for the average calculation
        total_home_score += score_h
        total_away_score += score_a
        
    # Calculate averages rounded to 1 decimal place
    avg_home = round(total_home_score / iterations, 1)
    avg_away = round(total_away_score / iterations, 1)
    
    return {
        "home_wins": home_wins,
        "away_wins": away_wins,
        "avg_home_score": avg_home,
        "avg_away_score": avg_away
    }


