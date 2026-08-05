import sys

def main():
    path = r"d:\OCR-Github\OCR-Document\backend\db_ingestion.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # The file is currently messed up around line 390. Let's find def init_qa_transactions
    
    start_str = "def init_qa_transactions():"
    end_str = "def get_latest_qa_transaction"
    
    start_idx = content.find(start_str)
    end_idx = content.find(end_str)
    
    if start_idx == -1 or end_idx == -1:
        print("Could not find start or end bounds.")
        return

    new_content = """def init_qa_transactions():
    \"\"\"Initializes the qa_transactions table in the database.\"\"\"
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()
        
        cursor.execute(\"\"\"
            CREATE TABLE IF NOT EXISTS qa_transactions (
                transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                group_name VARCHAR(255),
                group_type VARCHAR(100),
                filename VARCHAR(255) NOT NULL,
                doc_type VARCHAR(255),
                extracted_text TEXT,
                qa_report TEXT,
                total_pages INTEGER,
                email VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        \"\"\")
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN group_name VARCHAR(255);")
        except Exception:
            pass # Column likely already exists
            
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN group_type VARCHAR(100);")
        except Exception:
            pass # Column likely already exists
            
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN total_pages INTEGER;")
        except Exception:
            pass
            
        try:
            cursor.execute("ALTER TABLE qa_transactions ADD COLUMN email VARCHAR(255);")
        except Exception:
            pass
            
        logger.info("Checked/Created qa_transactions table.")
    except Exception as e:
        logger.error(f"Error initializing qa_transactions table: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def save_qa_transaction(project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages=None, email=None):
    \"\"\"Saves a QA consult transaction to the database.\"\"\"
    conn = None
    cursor = None
    try:
        if not project_id:
            logger.warning("No project_id provided, skipping saving QA transaction.")
            return False
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(\"\"\"
            INSERT INTO qa_transactions (project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages, email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        \"\"\", (project_id, group_name, group_type, filename, doc_type, extracted_text, qa_report, total_pages, email))
        conn.commit()
        logger.info(f"Saved QA transaction for {filename} in project {project_id}.")
        return True
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error saving QA transaction: {e}", exc_info=True)
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

"""
    
    final_content = content[:start_idx] + new_content + content[end_idx:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(final_content)
    print("Fixed db_ingestion.py")

if __name__ == "__main__":
    main()
