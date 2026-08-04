import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

def add_table():
    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=os.environ.get("DB_PORT", "5432"),
            dbname=os.environ.get("DB_NAME", "qa_agent_db"),
            user=os.environ.get("DB_USER", "qa_admin"),
            password=os.environ.get("DB_PASS", "qa_password")
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Adding qa_transactions table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS qa_transactions (
                transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                filename VARCHAR(255) NOT NULL,
                doc_type VARCHAR(255),
                extracted_text TEXT,
                qa_report TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Table qa_transactions added successfully.")
        
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    add_table()
