import asyncio
import aiohttp
import sqlite3
import pandas as pd
import time
from datetime import datetime, timedelta

DB_PATH = "agrest_analytics.db"
MAX_CONCURRENT_REQUESTS = 25  # Safe limit for ESPN servers

def parse_clock_to_seconds(clock_str):
    try:
        parts = str(clock_str).split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1].split('.')[0])
        return 0
    except Exception:
        return 0

async def fetch_daily_scoreboard(session, date_str):
    """Fetches all games played on a specific date."""
    
    # --- ADD &groups=50 RIGHT HERE TO OVERRIDE THE TOP 25 DEFAULT ---
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates={date_str}&groups=50&limit=400"
    
    try:
        async with session.get(url, timeout=15) as response:
            if response.status == 200:
                data = await response.json()
                events = data.get("events", [])
                
                game_ids = []
                for event in events:
                    # Scoreboard status is strictly defined here
                    status = event.get("status", {}).get("type", {}).get("completed", False)
                    if status:
                        game_ids.append(str(event["id"]))
                return game_ids
    except Exception:
        pass
    return []

async def fetch_and_parse_pbp(session, game_id, semaphore):
    """Fetches raw play-by-play data for a single game and normalizes it."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={game_id}"
    async with semaphore:
        try:
            async with session.get(url, timeout=15) as response:
                if response.status != 200:
                    return None
                res = await response.json()
                
                plays_data = res.get("plays", [])
                if not plays_data:
                    return None

                parsed_plays = []
                for play in plays_data:
                    period = play.get("period", {}).get("number", 1)
                    clock_str = play.get("clock", {}).get("displayValue", "0:00")
                    timestamp_secs = parse_clock_to_seconds(clock_str)
                    
                    detail = play.get("text", "")
                    type_text = play.get("type", {}).get("text", "").lower()
                    score_val = int(play.get("scoreValue", 0))
                    
                    team_id = play.get("team", {}).get("id")
                    team_id = int(team_id) if team_id else None
                        
                    player_id = None
                    participants = play.get("participants", [])
                    if participants:
                        player_id = str(participants[0].get("athlete", {}).get("id", "")).strip()
                        if not player_id:
                            player_id = None

                    event_type = "OTHER"
                    if "sub in" in type_text or "enters the game" in detail.lower():
                        event_type = "SUB_IN"
                    elif "sub out" in type_text or "leaves the game" in detail.lower():
                        event_type = "SUB_OUT"
                    elif score_val > 0 or "made" in type_text:
                        event_type = "MADE_SHOT"
                    elif "missed" in type_text or "shot" in type_text:
                        event_type = "FGA"
                    elif "turnover" in type_text:
                        event_type = "TOV"
                        
                    parsed_plays.append((
                        str(game_id), int(period), int(timestamp_secs),
                        event_type, team_id, player_id, score_val, detail
                    ))
                return parsed_plays
        except Exception:
            return None

def get_season_dates(start_date="20251101", end_date="20260410"):
    """Generates a list of all YYYYMMDD date strings for the college basketball season."""
    start = datetime.strptime(start_date, "%Y%m%d")
    end = datetime.strptime(end_date, "%Y%m%d")
    dates = []
    while start <= end:
        dates.append(start.strftime("%Y%m%d"))
        start += timedelta(days=1)
    return dates

async def main():
    start_time = time.time()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS games_pbp (
        play_id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT,
        period INTEGER,
        timestamp_secs INTEGER,
        event_type TEXT,
        team_id INTEGER,
        player_id TEXT,
        points INTEGER,
        detail TEXT
    );
    """)
    
    season_dates = get_season_dates()
    print(f"Scanning the entire season ({len(season_dates)} days) for completed games concurrently...")
    
    async with aiohttp.ClientSession() as session:
        # 1. Fetch all days of the season simultaneously
        scoreboard_tasks = [fetch_daily_scoreboard(session, d) for d in season_dates]
        daily_results = await asyncio.gather(*scoreboard_tasks)
        
        all_game_ids = set()
        for gids in daily_results:
            all_game_ids.update(gids)
            
        print(f"Identified {len(all_game_ids):,} completed games across the season.")
        
        # 2. Filter out already scraped games
        existing_games = pd.read_sql_query("SELECT DISTINCT game_id FROM games_pbp", conn)['game_id'].tolist()
        existing_games_set = set(existing_games)
        games_to_scrape = [gid for gid in all_game_ids if gid not in existing_games_set]
        
        print(f"Skipping {len(existing_games_set):,} already scraped games.")
        print(f"Remaining to fetch: {len(games_to_scrape):,}")
        
        if not games_to_scrape:
            print("Database is entirely up to date.")
            conn.close()
            return

        # 3. Fetch Play-by-Play logs concurrently
        print(f"Initiating high-speed Play-by-Play scrape for {len(games_to_scrape)} games...")
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        pbp_tasks = [fetch_and_parse_pbp(session, gid, semaphore) for gid in games_to_scrape]
        
        chunk_size = 200
        total_inserted_games = 0
        
        for i in range(0, len(pbp_tasks), chunk_size):
            chunk = pbp_tasks[i:i+chunk_size]
            results = await asyncio.gather(*chunk)
            
            flat_plays = []
            successful_chunk_games = 0
            for r in results:
                if r:
                    flat_plays.extend(r)
                    successful_chunk_games += 1
            
            if flat_plays:
                cursor.executemany("""
                    INSERT INTO games_pbp (game_id, period, timestamp_secs, event_type, team_id, player_id, points, detail)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, flat_plays)
                conn.commit()
                
            total_inserted_games += successful_chunk_games
            print(f"Progress: Processed {min(i + chunk_size, len(pbp_tasks)):,}/{len(pbp_tasks):,} games...")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pbp_game ON games_pbp(game_id);")
    conn.commit()
    conn.close()
    
    elapsed = time.time() - start_time
    print(f"\n🎉 PIPELINE COMPLETE: Successfully ingested data for {total_inserted_games:,} new games in {elapsed/60:.2f} minutes!")

if __name__ == "__main__":
    asyncio.run(main())