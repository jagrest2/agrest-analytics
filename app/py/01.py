import os
import requests
import pandas as pd
from dotenv import load_dotenv

# Load key from .env file
load_dotenv()
API_KEY = os.getenv("CBB_API_KEY")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json"
}

def fetch_and_export_season_stats(season=2026):
    """
    Fetches team game-level stats for ALL teams in a given season
    and saves the raw dataset to a CSV file.
    """
    print(f"Fetching full-season game stats for {season}...")
    
    url = "https://api.collegebasketballdata.com/games/teams"
    params = {"season": season}

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        
        # Convert JSON list of dictionaries directly into a Pandas DataFrame
        df = pd.DataFrame(data)
        
        print(f"Successfully fetched {len(df)} game records!")
        
        # Ensure output directory exists
        os.makedirs("data", exist_ok=True)
        
        # Save output to CSV
        output_path = f"cbb_team_games_{season}.csv"
        df.to_csv(output_path, index=False)
        print(f"Dataset saved to: {output_path}")
        
        return df
    else:
        print(f"Failed to fetch data [{response.status_code}]: {response.text}")
        return None

if __name__ == "__main__":
    df_2026 = fetch_and_export_season_stats(2026)