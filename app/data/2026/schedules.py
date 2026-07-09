import pandas as pd
import json
import os

# 1. Paste your name translation dictionary here to keep everything uniform
TEAM_ALIASES = {
    # "Name in games.csv" : "Name in output3.csv"
    "Iowa St": "Iowa State",
    "Michigan St": "Michigan State",
    "St John's": "St. John's",
    "St Mary's CA": "Saint Mary's",
    "Ohio St": "Ohio State",
    "Utah St": "Utah State",
    "St Louis": "Saint Louis",
    "Miami FL": "Miami (FL)",
    "San Diego St": "San Diego State",
    "Boise St": "Boise State",
    "Florida St": "Florida State",
    "Arizona St": "Arizona State",
    "Wichita St": "Wichita State",
    "Colorado St": "Colorado State",
    "Oklahoma St": "Oklahoma State",
    "Miami OH": "Miami (OH)",
    "G Washington": "George Washington",
    "E Washington": "Eastern Washington",
    "Kansas St": "Kansas State",
    "Illinois St": "Illinois State",
    "Mississippi St": "Mississippi State",
    "FL Atlantic": "FAU",
    "SF Austin": "Stephen F. Austin",
    "Montana St": "Montana State",
    "Kennesaw": "Kennesaw State",
    "IL Chicago": "Illinois-Chicago",
    "St Thomas MN": "St. Thomas",
    "St Joseph's PA" : "St. Joseph's",
    "N Dakota St": "North Dakota State",
    "Fresno St": "Fresno State",
    "Penn St": "Penn State",
    "S Illinois": "Southern Illinois",
    "Washington St": "Washington State",
    "Murray St": "Murray State",
    "St Bonaventure" : "St. Bonaventure",
    "Cal Baptist" : "California Baptist",
    "TAM C. Christi" : "Texas A&M CC",
    "N Colorado" : "Northern Colorado",
    "Portland St": "Portland State",
    "Wright St": "Wright State",
    "Loy Marymount" : "Loyola Marymount",
    "Florida Intl" : "Florida International",
    "WKU" : "Western Kentucky",
    "Kent": "Kent State",
    "New Mexico St": "New Mexico State",
    "Jacksonville St": "Jacksonville State",
    "CS Fullerton" : "Cal State Fullerton",
    "Penn" : "Pennsylvania",
    "Weber St": "Weber State",
    "Appalachian St": "Appalachian State",
    "Cent Arkansas" : "Central Arkansas",
    "N Kentucky" : "Northern Kentucky",
    "Oregon St": "Oregon State",
    "Arkansas St": "Arkansas State",
    "Missouri St": "Missouri State",
    "San Jose St": "San Jose State",
    "S Dakota St": "South Dakota State",
    "Indiana St": "Indiana State",
    "Monmouth NJ" : "Monmouth",
    "CS Northridge" : "Cal State Northridge",
    "Col Charleston" : "College of Charleston",
    "Tarleton St": "Tarleton State",
    "TN Martin" : "UT Martin",
    "Tennessee St": "Tennessee State",
    "PFW" : "IPFW",
    "Idaho St": "Idaho State",
    "Long Beach St": "Long Beach State",
    "W Carolina" : "Western Carolina",
    "Abilene Chr" : "Abilene Christian",
    "Texas St": "Texas State",
    "American Univ" : "American",
    "WI Green Bay" : "Green Bay",
    "E Michigan" : "Eastern Michigan",
    "Detroit" : "Detroit Mercy",
    "SE Missouri St" : "Southeast Missouri State",
    "NE Omaha" : "Omaha",
    "CS Sacramento": "Sacramento State",
    "LIU Brooklyn" : "LIU",
    "Queens NC" : "Queens (NC)",
    "Charleston So" : "Charleston Southern",
    "Coastal Car" : "Coastal Carolina",
    "Ga Southern" : "Georgia Southern",
    "Nicholls St" : "Nicholls State",
    "St Peter's" : "Saint Peter's",
    "WI Milwaukee" : "Milwaukee",
    "Southern Univ" : "Southern",
    "SC Upstate" : "USC Upstate",
    "C Michigan" : "Central Michigan",
    "Loyola-Chicago" : "Loyola Chicago",
    "Ball St" : "Ball State",
    "Morehead St" : "Morehead State",
    "E Kentucky" : "Eastern Kentucky",
    "Northwestern LA" : "Northwestern St",
    "Central Conn" : "Central Connecticut State",
    "Prairie View" : "Prairie View A&M",
    "Boston Univ" : "Boston University",
    "NC A&T" : "North Carolina A&T",
    "W Michigan" : "Western Michigan",
    "Norfolk St" : "Norfolk State",
    "SE Louisiana" : "Southeastern Louisiana",
    "Georgia St" : "Georgia State",
    "Houston Chr" : "Houston Christian",
    "IUPUI" : "IU Indy",
    "Mt St Mary's" : "Mount St. Mary's",
    "E Illinois" : "Eastern Illinois",
    "Cleveland St" : "Cleveland State",
    "SUNY Albany" : "Albany",
    "UT San Antonio" : "UTSA",
    "MA Lowell" : "UMASS Lowell",
    "F Dickinson" : "FDU",
    "CS Bakersfield" : "Cal State Bakersfield",
    "Ark Pine Bluff" : "Arkansas-Pine Bluff",
    "TX Southern" : "Texas Southern",
    "Loyola MD" : "Loyola Maryland",
    "Ark Little Rock" : "Little Rock",
    "N Illinois" : "Northern Illinois",
    "Alabama St" : "Alabama State",
    "NC Central" : "North Carolina Central",
    "Citadel" : "The Citadel",
    "Morgan St" : "Morgan State",
    "St Francis PA" : "Saint Francis (PA)",
    "MD E Shore" : "UMES",
    "Chicago St" : "Chicago State",
    "Missouri KC" : "Kansas City",
    "ULM" : "Louisiana-Monroe",
    "Jackson St" : "Jackson State",
    "S Carolina St" : "South Carolina State",
    "Alcorn St" : "Alcorn State",
    "Delaware St" : "Delaware State",
    "W Illinois" : "Western Illinois",
    "Coppin St" : "Coppin State",
    "MS Valley St" : "Mississippi Valley State",
}

def main():
    # Paths to your files (adjust if your folders are structured differently)
    games_file = "app/data/2026/games.csv"
    master_teams_file = "app/data/2026/output3.csv"
    output_json_file = "app/data/2026/schedules.json"

    print("Checking files...")
    if not os.path.exists(games_file) or not os.path.exists(master_teams_file):
        print("Error: Ensure games.csv and output3.csv exist in the data path.")
        return

    # 2. Load master D1 team names so we filter out non-D1 schools (like Mt Olive)
    master_df = pd.read_csv(master_teams_file)
    d1_teams = set(master_df["Team"].astype(str).str.strip())

    # 3. Read games.csv safely without headers using column positions
    # Position 2 = Team A, Position 4 = Team B
    games_df = pd.read_csv(games_file, header=None)
    
    schedules = {}

    print(f"Processing {len(games_df)} total game records...")

    # 4. Loop through every single game row
    for _, row in games_df.iterrows():
        try:
            # Grab team names safely from their positional columns
            team_a = str(row[2]).strip()
            team_b = str(row[4]).strip()

            # Apply alias corrections permanently
            team_a = TEAM_ALIASES.get(team_a, team_a)
            team_b = TEAM_ALIASES.get(team_b, team_b)

            # FILTER: Only count the game if BOTH opponents are verified D1 schools
            if team_a in d1_teams and team_b in d1_teams:
                
                # Add Team B to Team A's schedule
                if team_a not in schedules:
                    schedules[team_a] = []
                schedules[team_a].append(team_b)

                # Add Team A to Team B's schedule
                if team_b not in schedules:
                    schedules[team_b] = []
                schedules[team_b].append(team_a)
                
        except Exception as e:
            # Skip corrupted rows gracefully
            continue

    # 5. Export everything into a clean JSON file
    with open(output_json_file, "w", encoding="utf-8") as f:
        json.dump(schedules, f, indent=4, ensure_ascii=False)

    print(f"Success! Saved complete schedule mappings for {len(schedules)} D1 schools to {output_json_file}")

if __name__ == "__main__":
    main()