import os
from db_ingestion import get_db_connection

def update_filenames():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update any NULL or empty filenames to the correct one
        target_name = "68L_REQ_SRS_V20 (Approved_Baselined).pdf"
        
        cursor.execute("""
            UPDATE api_usage_logs 
            SET filename = %s 
            WHERE filename IS NULL OR filename = '';
        """, (target_name,))
        
        updated_count = cursor.rowcount
        conn.commit()
        print(f"Successfully updated {updated_count} records with the filename '{target_name}'.")
        
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == '__main__':
    update_filenames()
