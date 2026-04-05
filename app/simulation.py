import pandas as pd
import numpy as np
import requests
import streamlit as st
import sqlite3


df_orb = pd.read_csv("app/data/ORB_Data_V1.csv")
df_efg = pd.read_csv("app/data/EFG_Data_V1.csv")
df_tov = pd.read_csv("app/data/TOV_Data_V1.csv")
df_opp = pd.read_csv("app/data/OPP_Data_V1.csv")
df_poss = pd.read_csv("app/data/POSS_Data_V1.csv")

# Create a list of all your dataframes to clean them all at once
all_dfs = [df_orb, df_efg, df_tov, df_opp, df_poss]

for d in all_dfs:
    # 1. Force columns to lowercase
    d.columns = d.columns.str.lower()
    # 2. STRIP hidden spaces from column names (The "KeyError" Killer)
    d.columns = d.columns.str.strip()
    # 3. STRIP hidden spaces from the actual Team names inside the rows
    d['team'] = d['team'].astype(str).str.strip()

def simulate_possession(offense_team, defense_team):
    # 1. Did a turnover happen?
    to_prob = (df_tov.loc[df_tov['team'] == offense_team, 'tov%'].iloc[0] + 
               df_opp.loc[df_opp['team'] == defense_team, 'tov%'].iloc[0]) / 2
               
    if np.random.random() < to_prob:
        return 0, "Turnover"

    # 2. If no turnover, they take a shot. Did it go in?
    efg = df_efg.loc[df_efg['team'] == offense_team, 'efg%'].iloc[0]
    if np.random.random() < efg:
        return 2, "Made 2pt Basket" # Simplified for now
    
    # 3. If they missed, did they get the offensive board?
    or_rate = df_orb.loc[df_orb['team'] == offense_team, 'orb%'].iloc[0]
    if np.random.random() < or_rate:
        points, desc = simulate_possession(offense_team, defense_team) # Recursive reset
        return points, f"Missed Shot -> Off Rebound -> {desc}"
        
    return 0, "Missed Shot"

# def exp_poss(home, away):
#     home_p = df_poss.loc[df_poss['Team'].str.contains(home, case=False, na=False), 'Poss'].iloc[0]
#     away_p = df_poss.loc[df_poss['Team'].str.contains(away, case=False, na=False), 'Poss'].iloc[0]
#     return 69 - (69 - home_p) - (69 - away_p) if (home_p < 69 and away_p < 69) else 69 + (home_p - 69) + (away_p - 69) if (home_p > 69 and away_p > 69) else (home_p + away_p) / 2

def run_full_game_pbp(team_h, team_a):
    total_poss = 70 ## we will figure this out int(exp_poss(team_h, team_a))
    game_log = []
    score_h, score_a = 0, 0
    
    for p in range(total_poss):
        # Home Team Possession
        pts, desc = simulate_possession(team_h, team_a)
        score_h += pts
        game_log.append(f"Home: {desc} | Score: {score_h}-{score_a}")
        
        # Away Team Possession
        pts, desc = simulate_possession(team_a, team_h)
        score_a += pts
        game_log.append(f"Away: {desc} | Score: {score_h}-{score_a}")
        
    return score_h, score_a, game_log

team_list = sorted(df_orb['team'].unique())
team_home = st.selectbox("Select Home Team", team_list)
team_away = st.selectbox("Select Away Team", team_list)

if st.button("🎲 Simulate Matchup"):
    score_home, score_away, game_log = run_full_game_pbp(team_home, team_away)
    margin = abs(score_home - score_away)
    winner = team_home if score_home > score_away else team_away
    
    st.write(f"**Predicted Winner:** {winner} by {margin}")
    st.subheader(f"{team_home} {score_home} - {team_away} {score_away}")