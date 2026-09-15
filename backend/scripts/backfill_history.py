import sys
import psycopg2
import json
from dotenv import load_dotenv
import os

load_dotenv()

def backfill():
    print("Starting backfill for old QA history...")
    
    # Needs the backend path to import app and excel_report modules
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        from db_ingestion import get_db_connection, update_qa_transaction_results
        from excel_report import parse_qa_report_with_ai
        from app import evaluate_document_exit_criteria
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Select transactions where qa_findings is NULL or exit_criteria_eval is NULL
        cursor.execute("""
            SELECT transaction_id, filename, doc_type, project_id, extracted_text, qa_report
            FROM qa_transactions
            WHERE qa_findings IS NULL OR exit_criteria_eval IS NULL;
        """)
        
        rows = cursor.fetchall()
        if not rows:
            print("No old history items need updating! All clear.")
            return
            
        print(f"Found {len(rows)} old history items to update. This may take a few minutes as it uses AI...")
        
        for row in rows:
            t_id, filename, doc_type, project_id, doc_text, report = row
            print(f"Processing: {filename} (ID: {t_id})")
            
            try:
                # 1. Parse findings
                print("  - Parsing QA Findings...")
                qa_findings = parse_qa_report_with_ai(report, filename)
                
                # 2. Evaluate exit criteria
                print("  - Evaluating Exit Criteria...")
                # pass qa_findings for context
                exit_criteria = evaluate_document_exit_criteria(
                    doc_text=doc_text, 
                    doc_type=doc_type or 'ALL', 
                    project_id=project_id, 
                    qa_findings=qa_findings
                )
                
                # 3. Update DB
                update_qa_transaction_results(t_id, qa_findings, exit_criteria)
                print("  - Successfully updated!")
                
            except Exception as e:
                print(f"  - Error processing {filename}: {e}")
                
        print("Backfill complete!")
        
    except Exception as e:
        print(f"Failed to run backfill: {e}")
    finally:
        if 'cursor' in locals() and cursor: cursor.close()
        if 'conn' in locals() and conn: conn.close()

if __name__ == "__main__":
    backfill()
