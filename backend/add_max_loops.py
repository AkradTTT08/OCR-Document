import sys
import psycopg2
from db_ingestion import get_db_connection

def add_column():
    conn = get_db_connection()
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE exit_criteria_templates ADD COLUMN IF NOT EXISTS max_loops INTEGER DEFAULT 3;")
        print("Added max_loops successfully.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_column()
