import os
from db_ingestion import get_db_connection

def dump_logs():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT log_id, created_at, endpoint_name, model_name, filename, total_tokens, estimated_cost_usd FROM api_usage_logs ORDER BY created_at ASC;")
        rows = cursor.fetchall()
        
        with open("logs_dump.txt", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(f"ID: {r[0]}, Date: {r[1]}, Endpoint: {r[2]}, Model: {r[3]}, File: {r[4]}, Tokens: {r[5]}, Cost: {r[6]}\n")
                
        print(f"Dumped {len(rows)} records to logs_dump.txt")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == '__main__':
    dump_logs()
