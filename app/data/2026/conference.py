print("!!! PYTHON HAS STARTED READING THE FILE !!!")

import pandas as pd
import os
import re
import urllib.request
import json

TEAM_ALIASES = {
    "stjohns": "St. John's",
    "uconn": "UConn",
    "connecticut": "UConn",
    "olemiss": "Ole Miss",
    "mississippi": "Ole Miss",
}

def normalize_name(s):
    """Strips all punctuation, spaces, and casing for bulletproof matching."""
    if pd.isna(s):
        return ""
    return re.sub(r'[^a-z0-9]', '', str(s).lower())

def fetch_conference_registry():
    """Fetches clean D1 conference assignments via ESPN's verified live groups endpoint."""
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/groups"
    print(f"Connecting to live sports database endpoint...")
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            raw_json = json.loads(response.read().decode())
            
        conf_lookup = {}
        groups = raw_json.get('groups', [])
        
        for group in groups:
            conf_name = group.get('name', '')
            if not conf_name or "Tournament" in conf_name or "Class" in conf_name:
                continue
                
            for team_wrapper in group.get('teams', []):
                team_name = team_wrapper.get('displayName', '').strip()
                if team_name:
                    conf_lookup[team_name] = conf_name
                    conf_lookup[normalize_name(team_name)] = conf_name
                    
        if conf_lookup:
            print("-> Successfully retrieved data from live API!")
            return conf_lookup
    except Exception as e:
        print(f"-> Live API could not be reached: {e}")
    
    # --- COMPREHENSIVE OFFLINE DATA MATRIX ---
    print("-> Activating complete built-in conference database...")
    fallback_data = {
        "ACC": [
            "Duke", "North Carolina", "Virginia", "Wake Forest", "Clemson", "NC State", 
            "Pittsburgh", "Virginia Tech", "Florida State", "Miami", "Boston College", 
            "Syracuse", "Notre Dame", "Louisville", "Georgia Tech", "Stanford", "California", "SMU"
        ],
        "Big 12": [
            "Houston", "Iowa State", "Kansas", "Baylor", "BYU", "Texas Tech", "TCU", 
            "Texas", "Oklahoma", "Oklahoma State", "Cincinnati", "UCF", "West Virginia", 
            "Kansas State", "Arizona", "Arizona State", "Colorado", "Utah"
        ],
        "Big Ten": [
            "Purdue", "Illinois", "Nebraska", "Northwestern", "Wisconsin", "Michigan State", 
            "Minnesota", "Ohio State", "Iowa", "Maryland", "Penn State", "Indiana", 
            "Michigan", "Rutgers", "UCLA", "USC", "Oregon", "Washington"
        ],
        "SEC": [
            "Tennessee", "Auburn", "Alabama", "South Carolina", "Kentucky", "Florida", 
            "Mississippi State", "Texas A&M", "LSU", "Ole Miss", "Georgia", "Arkansas", 
            "Vanderbilt", "Missouri", "Oklahoma", "Texas"
        ],
        "Big East": [
            "UConn", "Marquette", "Creighton", "Seton Hall", "St. John's", "Villanova", 
            "Providence", "Butler", "Xavier", "Georgetown", "DePaul"
        ],
        "Mountain West": [
            "Utah State", "Nevada", "Boise State", "San Diego State", "UNLV", "New Mexico", 
            "Colorado State", "Wyoming", "Fresno State", "San Jose State", "Air Force"
        ],
        "West Coast": [
            "Saint Mary's", "Gonzaga", "San Francisco", "Santa Clara", "Loyola Marymount", 
            "Pepperdine", "Portland", "San Diego", "Pacific", "Washington State", "Oregon State"
        ],
        "Atlantic 10": [
            "Richmond", "Loyola Chicago", "Dayton", "UMass", "VCU", "St. Bonaventure", 
            "Saint Joseph's", "George Mason", "Duquesne", "Davidson", "Rhode Island", 
            "Fordham", "La Salle", "Saint Louis", "George Washington"
        ],
        "American": [
            "Memphis", "Florida Atlantic", "South Florida", "Charlotte", "UAB", "North Texas", 
            "UTSA", "Rice", "Tulsa", "Temple", "Wichita State", "East Carolina", "Tulane"
        ],
        "Missouri Valley": [
            "Indiana State", "Drake", "Bradley", "Southern Illinois", "Belmont", "Northern Iowa", 
            "Illinois State", "Murray State", "Missouri State", "Valparaiso", "UIC", "Evansville"
        ],
        "Sun Belt": [
            "Appalachian State", "James Madison", "Troy", "Arkansas State", "Southern Miss", 
            "Louisiana", "Georgia State", "Marshall", "South Alabama", "Georgia Southern", 
            "Texas State", "Old Dominion", "UL Monroe", "Coastal Carolina"
        ],
        "WAC": [
            "Grand Canyon", "Tarleton State", "UT Arlington", "Seattle U", "Utah Valley", 
            "Abilene Christian", "California Baptist", "Southern Utah", "Utah Tech", "UTRGV"
        ],
        "Mac": [
            "Toledo", "Akron", "Ohio", "Central Michigan", "Bowling Green", "Miami (OH)", 
            "Ball State", "Western Michigan", "Eastern Michigan", "Northern Illinois", "Kent State", "Buffalo"
        ],
        "CAA": [
            "Charleston", "Drexel", "Hofstra", "Unc Wilmington", "Towson", "Monmouth", 
            "Stony Brook", "Northeastern", "Delaware", "Campbell", "William & Mary", "Elon", "Hampton", "North Carolina A&T"
        ],
        "Horizon": [
            "Oakland", "Youngstown State", "Green Bay", "Wright State", "Northern Kentucky", 
            "Milwaukee", "Cleveland State", "Purdue Fort Wayne", "Robert Morris", "IUPUI", "Detroit Mercy"
        ],
        "Ivy League": [
            "Princeton", "Yale", "Cornell", "Harvard", "Brown", "Penn", "Columbia", "Dartmouth"
        ],
        "MAAC": [
            "Quinnipiac", "Fairfield", "Marist", "Rider", "Iona", "Siena", 
            "Mount St. Mary's", "Niagara", "Canisius", "Manhattan", "Saint Peter's"
        ],
        "ASUN": [
            "Eastern Kentucky", "Stetson", "Lipscomb", "Austin Peay", "North Florida", 
            "FGCU", "North Alabama", "Central Arkansas", "Jacksonville", "Queens", "Kennesaw State", "Bellarmine"
        ],
        "Big Sky": [
            "Eastern Washington", "Northern Colorado", "Montana", "Weber State", "Montana State", 
            "Portland State", "Northern Arizona", "Idaho State", "Idaho", "Sacramento State"
        ],
        "Big South": [
            "High Point", "Unc Asheville", "Gardner-Webb", "Winthrop", "Longwood", 
            "Presbyterian", "Charleston Southern", "Radford", "Upstate"
        ],
        "Big West": [
            "UC Irvine", "UC San Diego", "UC Davis", "Hawaii", "Long Beach State", 
            "UC Riverside", "UC Santa Barbara", "Cal State Northridge", "Cal State Fullerton", "Cal Poly", "Bakersfield"
        ],
        "America East": [
            "Vermont", "Umass Lowell", "Bryant", "New Hampshire", "Binghamton", 
            "Maine", "UMBC", "Albany", "NJIT"
        ],
        "MEAC": [
            "Norfolk State", "North Carolina Central", "South Carolina State", "Howard", 
            "Morgan State", "Maryland Eastern Shore", "Delaware State", "Coppin State"
        ],
        "OVC": [
            "Little Rock", "UT Martin", "Morehead State", "Western Illinois", "SIU Edwardsville", 
            "Eastern Illinois", "Tennessee State", "Southern Indiana", "Tennessee Tech", "Southeast Missouri", "Lindenwood"
        ],
        "Patriot": [
            "Colgate", "Lafayette", "Lehigh", "American University", "Bucknell", 
            "Boston University", "Holy Cross", "Navy", "Army", "Loyola (MD)"
        ],
        "Southern": [
            "Samford", "Unc Greensboro", "Chattanooga", "Western Carolina", "Wofford", 
            "Furman", "East Tennessee State", "Mercer", "The Citadel", "VMI"
        ],
        "Southland": [
            "McNeese", "Texas A&M-Corpus Christi", "Nicholls", "Lamar", "Southeastern Louisiana", 
            "Northwestern State", "Texas A&M-Commerce", "New Orleans", "Houston Christian", "Incarnate Word"
        ],
        "Summit League": [
            "South Dakota State", "North Dakota", "St. Thomas", "Denver", "North Dakota State", 
            "Kansas City", "Omaha", "Oral Roberts", "South Dakota"
        ],
        "SWAC": [
            "Grambling", "Alcorn State", "Southern U", "Texas Southern", "Jackson State", 
            "Bethune-Cookman", "Alabama A&M", "Alabama State", "Arkansas-Pine Bluff", "Prairie View", "Florida A&M", "Mississippi Valley State"
        ],
        "NEC": [
            "Central Connecticut", "Merrimack", "Sacred Heart", "Le Moyne", "FDU", 
            "Wagner", "Stonehill", "LIU", "Saint Francis"
        ]
    }
    
    conf_lookup = {}
    for conf, teams in fallback_data.items():
        for t in teams:
            conf_lookup[t] = conf
            conf_lookup[normalize_name(t)] = conf
            
    return conf_lookup

def main():
    master_path = "app/data/2026/output3.csv"
    
    if not os.path.exists(master_path):
        print(f"Error: Could not find your data file at {master_path}")
        return

    print("Reading your master output3.csv data...")
    master_df = pd.read_csv(master_path)
    
    conf_lookup = fetch_conference_registry()

    for alias_key, standard_name in TEAM_ALIASES.items():
        if standard_name in conf_lookup:
            conf_lookup[normalize_name(alias_key)] = conf_lookup[standard_name]

    print("Cross-referencing and mapping conferences using fuzzy matching...")
    assigned_conferences = []
    
    for raw_team in master_df['Team']:
        team_str = str(raw_team).strip()
        norm_team = normalize_name(team_str)
        
        if team_str in conf_lookup:
            assigned_conferences.append(conf_lookup[team_str])
        elif norm_team in conf_lookup:
            assigned_conferences.append(conf_lookup[norm_team])
        else:
            matched = False
            for key in conf_lookup.keys():
                if len(norm_team) > 3 and (norm_team in key or key in norm_team):
                    assigned_conferences.append(conf_lookup[key])
                    matched = True
                    break
            if not matched:
                assigned_conferences.append("Mid-Major Fallback")

    master_df['Conference'] = assigned_conferences
    
    # Rearrange structural columns
    columns = list(master_df.columns)
    if 'Conference' in columns and 'Team' in columns:
        columns.remove('Conference')
        team_index = columns.index('Team')
        columns.insert(team_index + 1, 'Conference')
        master_df = master_df[columns]

    master_df.to_csv(master_path, index=False)
    
    fallback_count = assigned_conferences.count("Mid-Major Fallback")
    print(f"\nSUCCESS! Total teams processed: {len(master_df)}")
    print(f"Successfully mapped: {len(master_df) - fallback_count} teams.")
    print(f"Assigned to Fallback Bracket: {fallback_count}")

print("Triggering main() function now...")
main()