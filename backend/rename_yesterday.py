import os
from db_ingestion import get_db_connection

def rename_yesterday_transaction():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update filename for records from yesterday (2026-08-12)
        # OR records before today, assuming all previous were yesterday
        new_name = "ERP_Super_SRS_Document.pdf"
        
        cursor.execute("""
            UPDATE api_usage_logs 
            SET filename = %s 
            WHERE created_at < CURRENT_DATE
            AND filename = '68L_REQ_SRS_V20 (Approved_Baselined).pdf';
        """, (new_name,))
        
        updated_count = cursor.rowcount
        conn.commit()
        print(f"Successfully updated {updated_count} records from yesterday to '{new_name}'.")
        
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == '__main__':
    rename_yesterday_transaction()
