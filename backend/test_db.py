import sys
import logging
from db_ingestion import get_db_connection

logging.basicConfig(level=logging.DEBUG)

try:
    conn = get_db_connection()
    print("Connection successful!")
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = cursor.fetchall()
    print("Tables:", [t[0] for t in tables])
    conn.close()
except Exception as e:
    print(f"Error connecting: {e}")
