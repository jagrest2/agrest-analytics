import pandas as pd
import numpy as np
import requests
import streamlit as st
import sqlite3

def init_db():
    conn = sqlite3.connect('matchup_tracker.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS counts 
                 (team_min TEXT, team_max TEXT, 
                  simulation_count INTEGER,
                  wins_min INTEGER DEFAULT 0,
                  wins_max INTEGER DEFAULT 0,
                  PRIMARY KEY (team_min, team_max))''')
    conn.commit()
    conn.close()

def update_count(t1, t2, winner_name):
    # Always sort so 'Kansas vs Duke' is the same as 'Duke vs Kansas'
    t_list = sorted([t1, t2])
    t_min, t_max = t_list[0], t_list[1]
    
    # Figure out which column gets the win
    win_col = "wins_min" if winner_name == t_min else "wins_max"
    
    conn = sqlite3.connect('matchup_tracker.db')
    c = conn.cursor()
    
    # This 'UPSERT' logic: Update both the total count AND the winner's count
    query = f'''INSERT INTO counts (team_min, team_max, simulation_count, {win_col}) 
                VALUES (?, ?, 1, 1)
                ON CONFLICT(team_min, team_max) 
                DO UPDATE SET 
                    simulation_count = simulation_count + 1,
                    {win_col} = {win_col} + 1'''
                    
    c.execute(query, (t_min, t_max))
    conn.commit()
    
    # Get the new totals to show the user
    c.execute("SELECT simulation_count, wins_min, wins_max FROM counts WHERE team_min=? AND team_max=?", (t_min, t_max))
    stats = c.fetchone()
    conn.close()
    return stats # Returns (total, w_min, w_max)

# Run this once at the very start of your app
init_db()

st.title("College Hoops Predictor")

# --- DATA LOADING SECTION ---
# Use your local CSV path that you've already saved
path = r"C:\Users\Josh Agrest\Desktop\agrest_analytics\app\data\kp_1220.csv"
df = pd.read_csv("app/data/kp_1220.csv")

# Ensure the 'Team' column is clean (removing numbers/ranks KenPom sometimes adds)
df['Team'] = df['Team'].str.replace(r'\d+', '', regex=True).str.strip()

# Create your calculated columns on the 'df' variable
df["Offense"] = pd.to_numeric(df["ORtg"], errors='coerce')
df["Defense"] = pd.to_numeric(df["DRtg"], errors='coerce')
df["Poss"] = pd.to_numeric(df["AdjT"], errors='coerce')

# --- LOGIC FUNCTIONS ---
def exp_poss(home, away):
    # Get possession values for both teams
    home_p = df.loc[df['Team'] == home, 'Poss'].iloc[0]
    away_p = df.loc[df['Team'] == away, 'Poss'].iloc[0]
    
    if (home_p < 69) and (away_p < 69):
        return 69 - (69 - home_p) - (69 - away_p)
    elif (home_p > 69) and (away_p > 69):
        return 69 + (home_p - 69) + (away_p - 69)
    else:
        return (home_p + away_p) / 2
    
def predict_score(home, away, home_court):
    exponent = 2.5
    points_multiplier = 0.92
    
    # Pre-fetch stats to make the math cleaner
    h_off = df.loc[df['Team'] == home, 'Offense'].iloc[0]
    a_off = df.loc[df['Team'] == away, 'Offense'].iloc[0]
    h_def = df.loc[df['Team'] == home, 'Defense'].iloc[0]
    a_def = df.loc[df['Team'] == away, 'Defense'].iloc[0]
    
    tempo = exp_poss(home, away)

    home_scaled_off = (h_off / 100) ** exponent * tempo
    away_scaled_off = (a_off / 100) ** exponent * tempo
    home_scaled_def = (h_def / 100) ** exponent * tempo
    away_scaled_def = (a_def / 100) ** exponent * tempo

    if home_court:
        home_points = round((home_scaled_off + away_scaled_def)/2 * points_multiplier + 2, 2)
        away_points = round((away_scaled_off + home_scaled_def)/2 * points_multiplier - 2, 2)
    else:
        home_points = round((home_scaled_off + away_scaled_def)/2 * points_multiplier, 2)
        away_points = round((away_scaled_off + home_scaled_def)/2 * points_multiplier, 2)
    
    return home_points, away_points

def predict_score_simulated(home, away, home_court):
    # 1. Get your baseline 'mean' scores from your existing logic
    # Let's assume your current math results in these two variables:
    base_home_mean, base_away_mean = predict_score(home, away, home_court)
    
    # 2. Set the Standard Deviation (Variance)
    std_dev = 10.5
    
    # 3. Generate a random score based on the Bell Curve
    sim_home = np.random.normal(base_home_mean, std_dev)
    sim_away = np.random.normal(base_away_mean, std_dev)
    
    # 4. Round to the nearest whole number (since you can't score half-points)
    return int(round(sim_home)), int(round(sim_away))

# 1. Drop any rows where 'Team' is empty (NaN)
df = df.dropna(subset=['Team'])

# 2. Force everything in the Team column to be a string (just to be safe)
df['Team'] = df['Team'].astype(str)

# 3. Now the sort will work perfectly
team_list = sorted(df['Team'].unique())
team_home = st.selectbox("Select Home Team", team_list)
team_away = st.selectbox("Select Away Team", team_list)
home_advantage = st.checkbox("Home Court Advantage?")

if st.button("🎲 Simulate Matchup"):
    # 1. Run your simulation logic
    score_home, score_away = predict_score_simulated(team_home, team_away, home_advantage)
    margin = round(abs(score_home - score_away), 1)
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
        st.write(f"🔥 20+ Pt Blowouts: **{blow_h}**")
    with col2:
        st.metric(f"{team_away} Total Wins", wins_a)
        st.write(f"🔥 20+ Pt Blowouts: **{blow_a}**")