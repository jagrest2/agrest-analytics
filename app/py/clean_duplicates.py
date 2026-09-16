import sqlite3
from pathlib import Path

# Adjust path if ratings.db is in an app/ directory
db_path = Path("app/ratings.db")
if not db_path.exists():
    db_path = Path("ratings.db")

print(f"Connecting to database at: {db_path.resolve()}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Check current row count before deletion
cursor.execute("SELECT COUNT(*) FROM efficiency_ratings;")
initial_count = cursor.fetchone()[0]
print(f"Total rows BEFORE cleaning: {initial_count}")

# 2. Delete duplicate rows based on team name and season, keeping the smallest rowid
# Update 'team' if your team column in SQLite is named differently (e.g., 'team_name' or 'Team')
delete_query = """
DELETE FROM efficiency_ratings
WHERE rowid NOT IN (
    SELECT MIN(rowid)
    FROM efficiency_ratings
    GROUP BY season, team
);
"""

try:
    cursor.execute(delete_query)
    conn.commit()
    
    # 3. Check row count after deletion
    cursor.execute("SELECT COUNT(*) FROM efficiency_ratings;")
    final_count = cursor.fetchone()[0]
    
    print(f"Total rows AFTER cleaning: {final_count}")
    print(f"Successfully removed {initial_count - final_count} duplicate rows!")

except Exception as e:
    print(f"Error removing duplicates: {e}")
    conn.rollback()

finally:
    conn.close()