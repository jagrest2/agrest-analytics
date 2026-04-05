import pandas as pd
import numpy as np
import requests
import streamlit as st
import sqlite3

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
df = pd.read_csv("app/data/kp_1220.csv")
df_opp = pd.read_csv("app/data/opp_stats.csv")


df["Offense"] = pd.to_numeric(df["ORtg"], errors='coerce')
df["Defense"] = pd.to_numeric(df["DRtg"], errors='coerce')
df["Poss"] = pd.to_numeric(df["AdjT"], errors='coerce')

# --- LOGIC FUNCTIONS ---
def exp_poss(home, away):
    home_p = df.loc[df['Team'].str.contains(home, case=False, na=False), 'Poss'].iloc[0]
    away_p = df.loc[df['Team'].str.contains(away, case=False, na=False), 'Poss'].iloc[0]
    return 69 - (69 - home_p) - (69 - away_p) if (home_p < 69 and away_p < 69) else 69 + (home_p - 69) + (away_p - 69) if (home_p > 69 and away_p > 69) else (home_p + away_p) / 2
    
def predict_score(home, away, home_court):
    exponent, points_multiplier = 2.5, 0.92
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


df = df.dropna(subset=['Team'])
df['Team'] = df['Team'].astype(str)
team_list = sorted(df['Team'].unique())

team_home = st.selectbox("Select Home Team", team_list)
team_away = st.selectbox("Select Away Team", team_list)
home_advantage = st.checkbox("Home Court Advantage?")

if st.button("🎲 Simulate Matchup"):
    score_home, score_away = predict_score_simulated(team_home, team_away, home_advantage)
    margin = abs(score_home - score_away)
    winner = team_home if score_home > score_away else team_away
    
    st.write(f"**Predicted Winner:** {winner} by {margin}")
    st.subheader(f"{team_home} {score_home} - {team_away} {score_away}")
    
    # UPDATE DATABASE WITH MARGIN
    total_sims, w_min, w_max, b_min, b_max = update_count(team_home, team_away, winner, margin)
    
    t_min = sorted([team_home, team_away])[0]
    wins_h, wins_a = (w_min, w_max) if team_home == t_min else (w_max, w_min)
    blow_h, blow_a = (b_min, b_max) if team_home == t_min else (b_max, b_min)
    
    st.info(f"📈 Matchup simulated **{total_sims}** times.")
    
    st.write("### 📊 Community History")
    col1, col2 = st.columns(2)
    with col1:
        st.metric(f"{team_home} Total Wins", wins_h)
        st.metric(f"{team_home} 20+ Pt Blowouts", blow_h)
    with col2:
        st.metric(f"{team_away} Total Wins", wins_a)
        st.metric(f"{team_away} 20+ Pt Blowouts", blow_a)

