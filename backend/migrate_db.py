import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
import time

def migrate_database():
    print("Connecting to postgres to create the new database...")
    
    # Connect to the default 'postgres' database to perform administrative commands
    conn = psycopg2.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "8123"),
        user=os.environ.get("DB_USER", "qa_admin"),
        password=os.environ.get("DB_PASS", "qa_password"),
        dbname="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    try:
        # Check if AIAgentQA already exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'AIAgentQA'")
        if cursor.fetchone():
            print("Database 'AIAgentQA' already exists. Migration may have already been done.")
            return

        # Attempt to disconnect other clients from qa_agent_db
        print("Terminating other connections to 'qa_agent_db' so it can be used as a template...")
        cursor.execute("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'qa_agent_db'
              AND pid <> pg_backend_pid();
        """)
        
        time.sleep(1) # Wait a moment for connections to drop
        
        print("Cloning 'qa_agent_db' into 'AIAgentQA'...")
        cursor.execute('CREATE DATABASE "AIAgentQA" WITH TEMPLATE qa_agent_db')
        print("✅ Database 'AIAgentQA' created successfully with all existing data!")
        
    except Exception as e:
        print(f"❌ Error during database migration: {e}")
        print("\nPlease ensure that the Python backend (app.py) is stopped before running this script.")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    migrate_database()
