import psycopg2
from db_ingestion import get_db_connection

def add_workflows_table():
    conn = get_db_connection()
    if not conn:
        print("Could not connect to DB.")
        return
        
    try:
        cursor = conn.cursor()
        
        # Create workflows table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                description TEXT,
                nodes JSONB NOT NULL DEFAULT '[]'::jsonb,
                edges JSONB NOT NULL DEFAULT '[]'::jsonb,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("workflows table created successfully.")
    except Exception as e:
        print(f"Error creating table: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        conn.close()

if __name__ == "__main__":
    add_workflows_table()
