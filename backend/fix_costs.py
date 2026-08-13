import os
from db_ingestion import get_db_connection

def recalculate_costs():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Select all logs for gemini-2.5-flash
        cursor.execute("SELECT log_id, prompt_tokens, completion_tokens FROM api_usage_logs WHERE model_name ILIKE '%2.5-flash%' AND model_name NOT ILIKE '%lite%';")
        rows = cursor.fetchall()
        
        updated_count = 0
        for row in rows:
            log_id = row[0]
            prompt_tokens = row[1]
            completion_tokens = row[2]
            
            # Recalculate using PRO rate
            new_cost = (prompt_tokens / 1_000_000 * 1.25) + (completion_tokens / 1_000_000 * 3.75)
            
            cursor.execute("UPDATE api_usage_logs SET estimated_cost_usd = %s WHERE log_id = %s;", (new_cost, log_id))
            updated_count += 1
            
        conn.commit()
        print(f"Successfully recalculated cost for {updated_count} records.")
        
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == '__main__':
    recalculate_costs()
