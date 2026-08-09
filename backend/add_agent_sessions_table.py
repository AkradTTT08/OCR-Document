import psycopg2
from db_ingestion import get_db_connection

def create_agent_sessions_table():
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        print("Creating agent_evaluation_sessions table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS agent_evaluation_sessions (
                session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                target_email VARCHAR(255),
                document_type VARCHAR(100),
                skill_id UUID REFERENCES agent_skills(skill_id) ON DELETE SET NULL,
                attempt_count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        print("agent_evaluation_sessions table created successfully.")
    except Exception as e:
        print(f"Error creating table: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    create_agent_sessions_table()
