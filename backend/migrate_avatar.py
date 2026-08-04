import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def migrate():
    print("Connecting to Auth DB for migration...")
    try:
        conn = psycopg2.connect(
            host=os.environ.get("AUTH_DB_HOST", "localhost"),
            port=os.environ.get("AUTH_DB_PORT", "8124"),
            dbname=os.environ.get("AUTH_DB_NAME", "postgres"),
            user=os.environ.get("AUTH_DB_USER", "postgres"),
            password=os.environ.get("AUTH_DB_PASS", "postgres")
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("Checking if avatar_path column exists in users table...")
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='avatar_path';
        """)
        
        if not cursor.fetchone():
            print("Adding avatar_path column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN avatar_path VARCHAR(255);")
            print("Migration successful.")
        else:
            print("Column avatar_path already exists.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
