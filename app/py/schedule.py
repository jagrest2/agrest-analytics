import time
from apscheduler.schedulers.background import BackgroundScheduler
# Import your game scraper and ratings logic functions
from analytics_pipeline import fetch_latest_games, calculate_iterative_sos


def run_pipeline():
  print("🔄 [Cron] Pulling latest game data and updating SQLite...")
  try:
    # 1. Fetch updated games dataframe
    games_df_2026 = fetch_latest_games(season=2026)

    # 2. Recalculate ratings & write directly to SQLite (using season=2026)
    calculate_iterative_sos(games_df_2026, season=2026)

    print("✅ [Cron] Ratings successfully refreshed in database.")
  except Exception as e:
    print(f"❌ [Cron Error]: {e}")


if __name__ == "__main__":
  scheduler = BackgroundScheduler()

  # Run immediately on boot, then every 30 minutes
  scheduler.add_job(run_pipeline, "interval", minutes=30)
  scheduler.start()

  print("🚀 Continuous updater started. Press Ctrl+C to stop.")
  try:
    while True:
      time.sleep(1)
  except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()