import pandas as pd
import json
import os

def compile_conference_profiles():
    csv_path = "app/data/2026/output3.csv"
    json_output_path = "app/data/2026/conferences.json"
    
    # 1. Match these to your exact CSV headers if they differ!
    TEAM_K = "Team"
    CONF_K = "Conference"
    NET_K = "Net"  # Change to 'NET' if that's your column name
    OFF_K = "Offensive"     # Change to 'Offense' or 'AdjO' if needed
    DEF_K = "Defensive"     # Change to 'Defense' or 'AdjD' if needed

    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    
    # Force numeric conversions so strings don't break the math
    df[NET_K] = pd.to_numeric(df[NET_K], errors='coerce')
    df[OFF_K] = pd.to_numeric(df[OFF_K], errors='coerce')
    df[DEF_K] = pd.to_numeric(df[DEF_K], errors='coerce')
    df = df.dropna(subset=[CONF_K, NET_K, OFF_K, DEF_K])

    # 2. Calculate global conference averages to build power rankings
    conf_group = df.groupby(CONF_K)
    avg_net_series = conf_group[NET_K].mean().sort_values(ascending=False)
    
    # Map conference names to their overall rating rank (1 being the highest Avg NET)
    conf_ranks = {conf: index + 1 for index, conf in enumerate(avg_net_series.index)}

    conference_matrix = {}

    # 3. Drill down into individual conference metrics
    for conf_name, group in conf_group:
        # Find the standout teams across categories
        best_team_row = group.loc[group[NET_K].idxmax()]
        best_off_row = group.loc[group[OFF_K].idxmax()]
        best_def_row = group.loc[group[DEF_K].idxmin()] # Lower defensive efficiency is better

        # Gather and sort all individual team entries inside this group
        sorted_teams = group.sort_values(by=NET_K, ascending=False)
        team_list = []
        
        for _, row in sorted_teams.iterrows():
            team_list.append({
                "name": row[TEAM_K],
                "net": round(float(row[NET_K]), 2),
                "off": round(float(row[OFF_K]), 2),
                "def": round(float(row[DEF_K]), 2)
            })

        conference_matrix[conf_name] = {
            "conferenceName": conf_name,
            "rank": conf_ranks[conf_name],
            "avgNet": round(float(avg_net_series[conf_name]), 2),
            "bestTeam": best_team_row[TEAM_K],
            "bestOffense": best_off_row[TEAM_K],
            "bestDefense": best_def_row[TEAM_K],
            "teams": team_list
        }

    # Write out the static database file
    os.makedirs(os.path.dirname(json_output_path), exist_ok=True)
    with open(json_output_path, "w") as f:
        json.dump(conference_matrix, f, indent=4)
        
    print(f"SUCCESS: Compiled stats for {len(conference_matrix)} conferences into {json_output_path}!")

if __name__ == "__main__":
    compile_conference_profiles()