import os
import sys
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def add_columns():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            port=os.getenv('DB_PORT', '8123'),
            database=os.getenv('DB_NAME', 'qa_agent_db'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'postgres')
        )
        cursor = conn.cursor()
        
        # Add qa_findings (JSON)
        cursor.execute("ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS qa_findings JSONB;")
        
        # Add exit_criteria_eval (JSON)
        cursor.execute("ALTER TABLE qa_transactions ADD COLUMN IF NOT EXISTS exit_criteria_eval JSONB;")
        
        conn.commit()
        print("Columns added successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    add_columns()
