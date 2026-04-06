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


def simulate_possession(offense_name, defense_name):
    # --- 1. Turnover Check ---
    off_tov = df_tov.loc[df_tov['team'] == offense_name, 'turnover'].iloc[0]
    def_tov = df_opp.loc[df_opp['team'] == defense_name, 'turnover'].iloc[0]
    to_prob = (off_tov + def_tov) / 2
    if to_prob > 1: to_prob /= 100
               
    if np.random.random() < to_prob:
        return 0, f"{offense_name} Turnover"

    # --- 2. Shot Selection ---
    is_three = np.random.random() < 0.35 
    efg = df_efg.loc[df_efg['team'] == offense_name, 'efg'].iloc[0]
    if efg > 1: efg /= 100

    # Determine shot outcome
    shot_made = False
    shot_type = "3PT" if is_three else "2PT"
    
    if is_three:
        if np.random.random() < (efg / 1.5):
            return 3, f"{offense_name} MADE 3PT"
    else:
        if np.random.random() < efg:
            return 2, f"{offense_name} MADE 2PT"

    # --- 3. Rebound Check (ONLY reached if shot was missed) ---
    or_rate = df_orb.loc[df_orb['team'] == offense_name, 'orb'].iloc[0]
    if or_rate > 1: or_rate /= 100
    
    if np.random.random() < or_rate:
        # We return -1 to signal a rebound, but include the shot type 
        # so the Stat Ledger can record the miss correctly.
        return -1, f"{offense_name} Missed {shot_type} -> Offensive Rebound"
        
    return 0, f"{offense_name} Missed {shot_type}"

def run_full_game_pbp(team_h, team_a):
    total_poss = 70 
    game_log = []
    
    # Initialize the Stat Ledger
    stats = {
        team_h: {"FGM": 0, "FGA": 0, "3PM": 0, "3PA": 0, "TOV": 0, "ORB": 0, "DRB": 0},
        team_a: {"FGM": 0, "FGA": 0, "3PM": 0, "3PA": 0, "TOV": 0, "ORB": 0, "DRB": 0}
    }
    
    score_h, score_a = 0, 0

    

    def process_possession(off, deff):
        pts, desc = simulate_possession(off, deff)
        
        # 1. Record the Initial Attempt Stats
        if "Turnover" in desc:
            stats[off]["TOV"] += 1
        elif "3PT" in desc:
            stats[off]["FGA"] += 1
            stats[off]["3PA"] += 1
            if "MADE" in desc:
                stats[off]["FGM"] += 1
                stats[off]["3PM"] += 1
        elif "2PT" in desc:
            stats[off]["FGA"] += 1
            if "MADE" in desc:
                stats[off]["FGM"] += 1
            
        # 2. Handle Rebound Logic
        if "Rebound" in desc:
            stats[off]["ORB"] += 1
            # Run the second shot attempt (the 'putback')
            pts_re, desc_re = simulate_possession(off, deff)
                
            # Record the second shot stats
            if "Turnover" in desc_re:
                stats[off]["TOV"] += 1
            elif "3PT" in desc_re:
                stats[off]["FGA"] += 1
                stats[off]["3PA"] += 1
                if "MADE" in desc_re:
                    stats[off]["FGM"] += 1
                    stats[off]["3PM"] += 1
                else:
                    stats[deff]["DRB"] += 1
            elif "2PT" in desc_re or "Missed" in desc_re:
                stats[off]["FGA"] += 1
                if "MADE" in desc_re:
                    stats[off]["FGM"] += 1
                else:
                    stats[deff]["DRB"] += 1
                
                # Combine the descriptions for the log
            return max(0, pts_re), f"{desc} -> {desc_re}"
                
            # 3. If it was a clean miss with NO rebound, credit the defense
        if "Missed" in desc and "Rebound" not in desc:
            stats[deff]["DRB"] += 1
                
        return max(0, pts), desc
    
    for p in range(total_poss):
        # Home Turn
        p_h, d_h = process_possession(team_h, team_a)
        score_h += p_h
        game_log.append(f"{d_h} | Score: {score_h}-{score_a}")
        
        # Away Turn
        p_a, d_a = process_possession(team_a, team_h)
        score_a += p_a
        game_log.append(f"{d_a} | Score: {score_h}-{score_a}")

    # --- Overtime Loop ---
    ot_count = 0
    while score_h == score_a:
        ot_count += 1
        game_log.append(f"--- START OF OVERTIME {ot_count} ---")
        for p in range(10): # 5 mins = ~10 possessions
            p_h, d_h = process_possession(team_h, team_a)
            score_h += p_h
            game_log.append(f"OT{ot_count} {d_h} | Score: {score_h}-{score_a}")

    return score_h, score_a, game_log, stats

def run_monte_carlo(team_h, team_a, iterations):
    wins_h = 0
    wins_a = 0
    total_margin = 0
    
    progress_bar = st.progress(0)
    
    for i in range(iterations):
        # Pass True for fast_mode so we skip the strings
        s_h, s_a, _, _ = run_full_game_pbp(team_h, team_a, fast_mode=True)
        
        if s_h > s_a:
            wins_h += 1
        elif s_a > s_h:
            wins_a += 1
            
        total_margin += (s_h - s_a)
        
        # Update progress bar
        if i % (max(1, iterations // 10)) == 0:
            progress_bar.progress(i / iterations)
            
    progress_bar.empty()
    
    win_pct_h = (wins_h / iterations) * 100
    avg_margin = total_margin / iterations
    
    return win_pct_h, avg_margin

team_list = sorted(df_orb['team'].unique())
team_home = st.selectbox("Select Home Team", team_list)
team_away = st.selectbox("Select Away Team", team_list)

# Sidebar UI
st.sidebar.header("Simulation Settings")
sim_mode = st.sidebar.radio("Simulation Mode", ["Single Game", "Batch"])

# Only show the number input if we are in Batch mode
if sim_mode == "Batch":
    num_sims = st.sidebar.number_input(
        "Number of Simulations", 
        min_value=1, 
        max_value=5000, 
        value=1000, 
        step=100,
        help="Maximum allowed is 5,000 simulations per click."
    )
else:
    num_sims = 1 # Default for single game
    
show_stats = st.checkbox("Show Team Box Scores (Single Game Only)")
show_log = st.checkbox("Show Play-by-Play Log (Single Game Only)")

if st.button("🎲 Run Simulation"):
    if sim_mode == "Single Game":
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
    else:
        # Run the Monte Carlo batch
        win_pct, avg_margin = run_monte_carlo(team_home, team_away, num_sims)
        
        st.write(f"### Results over {num_sims} Games")
        st.metric(f"{team_home} Win %", f"{win_pct:.1f}%")
        st.metric("Average Margin", f"{avg_margin:.1f}")
