import psycopg2
from db_ingestion import get_db_connection

def migrate_workflows_add_project_id():
    conn = get_db_connection()
    if not conn:
        print("Could not connect to DB.")
        return
        
    try:
        cursor = conn.cursor()
        
        # Add project_id column
        cursor.execute("""
            ALTER TABLE workflows 
            ADD COLUMN IF NOT EXISTS project_id VARCHAR(255)
        """)
        
        conn.commit()
        print("Added project_id to workflows table successfully.")
    except Exception as e:
        print(f"Error modifying table: {e}")
        conn.rollback()
    finally:
        if cursor:
            cursor.close()
        conn.close()

if __name__ == "__main__":
    migrate_workflows_add_project_id()
