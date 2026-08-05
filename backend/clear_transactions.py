import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "8123")
DB_NAME = os.getenv("DB_NAME", "qa_agent_db")
DB_USER = os.getenv("DB_USER", "qa_admin")
DB_PASSWORD = os.getenv("DB_PASS", "qa_password")

def clear_data():
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cursor = conn.cursor()
        
        # Clear all transactions
        cursor.execute("TRUNCATE TABLE qa_transactions RESTART IDENTITY CASCADE;")
        conn.commit()
        
        print("✅ เคลียร์ข้อมูลประวัติการตรวจสอบ (qa_transactions) เรียบร้อยแล้ว!")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")

if __name__ == "__main__":
    clear_data()
