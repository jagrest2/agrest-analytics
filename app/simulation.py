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

df_orb = pd.read_csv("app/data/ORB_Data_V1.csv")
df_efg = pd.read_csv("app/data/EFG_Data_V1.csv")
df_tov = pd.read_csv("app/data/TOV_Data_V1.csv")
df_opp = pd.read_csv("app/data/OPP_Data_V1.csv")
df_poss = pd.read_csv("app/data/POSS_Data_V1.csv")

# Create a list of all your dataframes to clean them all at once
all_dfs = [df_orb, df_efg, df_tov, df_opp, df_poss]

for d in all_dfs:
    d.columns = d.columns.str.lower().str.strip()
    d['team'] = d['team'].astype(str).str.strip()
    
    # NEW: Remove '%' from every cell in the dataframe and convert to numbers
    for col in d.columns:
        if col not in ['rank', 'team']:
            # 1. Replace the % with nothing
            # 2. Convert to numeric (turns "15.5" into 15.5)
            d[col] = pd.to_numeric(d[col].astype(str).str.replace('%', ''), errors='coerce')


def simulate_possession(offense_team, defense_team):
    # 1. Did a turnover happen?
    to_prob = (df_tov.loc[df_tov['team'] == offense_team, 'turnover'].iloc[0] + 
               df_opp.loc[df_opp['team'] == defense_team, 'turnover'].iloc[0]) / 2

    to_prob = to_prob/100
               
    if np.random.random() < to_prob:
        return 0, "Turnover"

    is_three = np.random.random() < 0.35
    
    # Get the eFG% and normalize it
    efg = df_efg.loc[df_efg['team'] == offense_team, 'efg'].iloc[0]
    if efg > 1: efg /= 100

    # --- 3. The "Make" Roll ---
    if is_three:
        # A 3pt make probability is lower because it's worth more points
        # If eFG is 50%, the 3PT make prob should be ~33%
        make_prob = efg / 1.5
        if np.random.random() < make_prob:
            return 3, f"{offense_team} MADE 3PT"
        else:
            return 0, f"{offense_team} Missed 3PT" # Now we can see missed 3s!
    else:
        # For a 2pt shot, eFG% is the same as raw FG%
        make_prob = efg
        if np.random.random() < make_prob:
            return 2, f"{offense_team} MADE 2PT"
        else:
            return 0, f"{offense_team} Missed 2PT"

# def exp_poss(home, away):
#     home_p = df_poss.loc[df_poss['Team'].str.contains(home, case=False, na=False), 'Poss'].iloc[0]
#     away_p = df_poss.loc[df_poss['Team'].str.contains(away, case=False, na=False), 'Poss'].iloc[0]
#     return 69 - (69 - home_p) - (69 - away_p) if (home_p < 69 and away_p < 69) else 69 + (home_p - 69) + (away_p - 69) if (home_p > 69 and away_p > 69) else (home_p + away_p) / 2

def run_full_game_pbp(team_h, team_a):
    total_poss = 70 
    game_log = []
    
    # Initialize the Stat Ledger
    stats = {
        team_h: {"FGM": 0, "FGA": 0, "3PM": 0, "3PA": 0, "TOV": 0, "ORB": 0, "DRB": 0},
        team_a: {"FGM": 0, "FGA": 0, "3PM": 0, "3PA": 0, "TOV": 0, "ORB": 0, "DRB": 0}
    }
    
    score_h, score_a = 0, 0

    def process_possession(off, deff, s_off, s_deff):
        pts, desc = simulate_possession(off, deff)
        
        # 1. Record Initial Stats
        if "Turnover" in desc:
            stats[off]["TOV"] += 1
        elif "3PT" in desc:
            stats[off]["FGA"] += 1
            stats[off]["3PA"] += 1
            if "MADE" in desc:
                stats[off]["FGM"] += 1
                stats[off]["3PM"] += 1
            elif "Rebound" not in desc: # It was a clean miss
                stats[deff]["DRB"] += 1
        elif "2PT" in desc or "Missed" in desc:
            stats[off]["FGA"] += 1
            if "MADE" in desc:
                stats[off]["FGM"] += 1
            elif "Rebound" not in desc:
                stats[deff]["DRB"] += 1

        # 2. Handle Offensive Rebound "Reset"
        if "Rebound" in desc:
            stats[off]["ORB"] += 1
            # Run the second shot attempt
            pts_re, desc_re = simulate_possession(off, deff)
            pts = max(0, pts_re)
            desc = f"{off} REBOUND -> {desc_re}"
            
            # Record second shot stats
            if "Turnover" in desc_re:
                stats[off]["TOV"] += 1
            else:
                stats[off]["FGA"] += 1
                if "3PT" in desc_re: stats[off]["3PA"] += 1
                if "MADE" in desc_re:
                    stats[off]["FGM"] += 1
                    if "3PT" in desc_re: stats[off]["3PM"] += 1
                else:
                    stats[deff]["DRB"] += 1 # 2nd miss always goes to defense here
        
        return max(0, pts), desc

    # --- Regulation Loop ---
    for p in range(total_poss):
        # Home Turn
        p_h, d_h = process_possession(team_h, team_a, score_h, score_a)
        score_h += p_h
        game_log.append(f"{d_h} | Score: {score_h}-{score_a}")
        
        # Away Turn
        p_a, d_a = process_possession(team_a, team_h, score_a, score_h)
        score_a += p_a
        game_log.append(f"{d_a} | Score: {score_h}-{score_a}")

    # --- Overtime Loop ---
    ot_count = 0
    while score_h == score_a:
        ot_count += 1
        game_log.append(f"--- START OF OVERTIME {ot_count} ---")
        for p in range(10): # 5 mins = ~10 possessions
            p_h, d_h = process_possession(team_h, team_a, score_h, score_a)
            score_h += p_h
            game_log.append(f"OT{ot_count} {d_h} | Score: {score_h}-{score_a}")
            
            p_a, d_a = process_possession(team_a, team_h, score_a, score_h)
            score_a += p_a
            game_log.append(f"OT{ot_count} {d_a} | Score: {score_h}-{score_a}")

    return score_h, score_a, game_log, stats

team_list = sorted(df_orb['team'].unique())
team_home = st.selectbox("Select Home Team", team_list)
team_away = st.selectbox("Select Away Team", team_list)
show_stats = st.checkbox("Show Team Box Scores")
show_log = st.checkbox("Show Play-by-Play Log")

if st.button("🎲 Simulate Matchup"):
    score_home, score_away, game_log, stats = run_full_game_pbp(team_home, team_away)
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
        if show_stats == True:
            home_stats_df = pd.DataFrame(stats[team_home], index=["Stats"]).T
            st.table(home_stats_df)
    with col2:
        st.metric(f"{team_away} Total Wins", wins_a)
        st.metric(f"{team_away} 20+ Pt Blowouts", blow_a)
        if show_stats == True:
            away_stats_df = pd.DataFrame(stats[team_away], index=["Stats"]).T
            st.table(away_stats_df)

    if show_log:
        with st.expander("View Full Game Transcript", expanded=True):
            # Using a loop to print each line of the log
            for line in game_log:
                # Add a little styling to make the scores stand out
                if "Score:" in line:
                    st.write(line.replace("|", "—"))
                else:
                    st.write(line)

