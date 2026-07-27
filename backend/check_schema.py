"""Debug script to check projects table schema and test insert"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import psycopg2
import traceback

def main():
    try:
        conn = psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=os.environ.get("DB_PORT", "5432"),
            dbname=os.environ.get("DB_NAME", "qa_agent_db"),
            user=os.environ.get("DB_USER", "qa_admin"),
            password=os.environ.get("DB_PASS", "qa_password")
        )
        print(f"[OK] Connected to DB at {os.environ.get('DB_HOST')}:{os.environ.get('DB_PORT')}")
    except Exception as e:
        print(f"[FAIL] Cannot connect to DB: {e}")
        return

    cur = conn.cursor()

    # 1. Check projects table exists
    print("\n=== Check tables ===")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {tables}")

    if 'projects' not in tables:
        print("[FAIL] 'projects' table does not exist!")
        # Try to show CREATE TABLE from docker init
        cur.close()
        conn.close()
        return

    # 2. Projects schema
    print("\n=== Projects table schema ===")
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'projects'
        ORDER BY ordinal_position;
    """)
    cols = cur.fetchall()
    for c in cols:
        print(f"  {c[0]:20s} | {c[1]:20s} | nullable={c[2]:3s} | default={c[3]} | maxlen={c[4]}")

    # 3. Constraints
    print("\n=== Constraints ===")
    cur.execute("""
        SELECT conname, contype, pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conrelid = 'projects'::regclass;
    """)
    for r in cur.fetchall():
        print(f"  {r[0]:30s} | type={r[1]} | {r[2]}")

    # 4. Existing data
    print("\n=== Existing projects ===")
    cur.execute("SELECT * FROM projects LIMIT 10;")
    col_names = [desc[0] for desc in cur.description]
    print(f"  Columns: {col_names}")
    for r in cur.fetchall():
        print(f"  {r}")

    # 5. Test INSERT
    print("\n=== Test INSERT ===")
    try:
        cur.execute(
            "INSERT INTO projects (project_code, project_name, description, status) VALUES (%s, %s, %s, %s) RETURNING project_id;",
            ('TEST-DBG-001', 'Debug Test Project', 'Test', 'Active')
        )
        pid = cur.fetchone()[0]
        print(f"[OK] Inserted project_id={pid}")
        # Rollback to not pollute data
        conn.rollback()
        print("[OK] Rolled back test insert")
    except Exception as e:
        conn.rollback()
        print(f"[FAIL] Insert failed: {e}")
        traceback.print_exc()

    # 6. Documents schema
    print("\n=== Documents table schema ===")
    if 'documents' in tables:
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'documents'
            ORDER BY ordinal_position;
        """)
        for c in cur.fetchall():
            print(f"  {c[0]:20s} | {c[1]:20s} | nullable={c[2]:3s} | default={c[3]}")
    else:
        print("  'documents' table does not exist!")

    # 7. document_chunks schema
    print("\n=== Document_chunks table schema ===")
    if 'document_chunks' in tables:
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'document_chunks'
            ORDER BY ordinal_position;
        """)
        for c in cur.fetchall():
            print(f"  {c[0]:20s} | {c[1]:20s} | nullable={c[2]:3s} | default={c[3]}")
    else:
        print("  'document_chunks' table does not exist!")

    cur.close()
    conn.close()
    print("\n[DONE]")

if __name__ == '__main__':
    main()
