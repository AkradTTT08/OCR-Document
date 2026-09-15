import psycopg2
from db_ingestion import get_db_connection

def add_board_cards_table():
    conn = get_db_connection()
    if not conn:
        print("Could not connect to DB.")
        return
        
    try:
        cursor = conn.cursor()
        
        # Create board_cards table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS board_cards (
                card_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                ext_card_id VARCHAR(50),
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(50) DEFAULT 'todo',
                card_type VARCHAR(50),
                priority VARCHAR(50),
                test_result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("board_cards table created successfully.")
    except Exception as e:
        print(f"Error creating table: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        conn.close()

if __name__ == "__main__":
    add_board_cards_table()
