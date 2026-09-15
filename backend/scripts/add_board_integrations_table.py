import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db_ingestion import get_db_connection

def add_board_integrations_table():
    conn = get_db_connection()
    if not conn:
        print("Could not connect to DB.")
        return
        
    try:
        cursor = conn.cursor()
        
        # Create board_integrations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS board_integrations (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID UNIQUE REFERENCES projects(project_id) ON DELETE CASCADE,
                provider VARCHAR(20) NOT NULL, -- 'trello' or 'github'
                trello_api_key TEXT,
                trello_token TEXT,
                trello_board_id TEXT,
                trello_todo_list_id TEXT,
                trello_done_list_id TEXT,
                github_token TEXT,
                github_owner TEXT,
                github_repo TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()
        print("board_integrations table created successfully.")
    except Exception as e:
        print(f"Error creating table: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        conn.close()

if __name__ == "__main__":
    add_board_integrations_table()
