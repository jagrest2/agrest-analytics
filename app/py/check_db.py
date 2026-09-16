import sqlite3
from pathlib import Path

# Adjust path if ratings.db is inside an app/ folder
db_path = Path("app/ratings.db") 

if not db_path.exists():
    # Fallback to current folder if app/ isn't present
    db_path = Path("ratings.db")

print(f"--- Checking Database at: {db_path.resolve()} ---")

if not db_path.exists():
    print("ERROR: Database file does not exist at this path!")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Get all tables in database
    tables = [t[0] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
    print(f"Tables found: {tables}")

    if "efficiency_ratings" in tables:
        # 2. Get distinct seasons stored in efficiency_ratings
        seasons = cursor.execute("SELECT DISTINCT season FROM efficiency_ratings;").fetchall()
        print(f"Seasons available in 'efficiency_ratings': {[s[0] for s in seasons]}")

        # 3. Count rows specifically for 2026
        count_2026_str = cursor.execute("SELECT COUNT(*) FROM efficiency_ratings WHERE season = '2025';").fetchone()[0]
        count_2026_int = cursor.execute("SELECT COUNT(*) FROM efficiency_ratings WHERE season = 2025;").fetchone()[0]
        print(f"Rows matching season '2026' (string): {count_2026_str}")
        print(f"Rows matching season 2026 (integer): {count_2026_int}")
    else:
        print("ERROR: Table 'efficiency_ratings' does not exist in this database!")

    conn.close()