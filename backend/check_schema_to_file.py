import psycopg2
import os
import sys

def main():
    try:
        conn = psycopg2.connect(
            host="localhost",
            port="5433",
            dbname="qa_agent_db",
            user="qa_admin",
            password="qa_password"
        )
        cur = conn.cursor()
        
        with open("db_schema_output.txt", "w", encoding="utf-8") as f:
            f.write("=== Projects table schema ===\n")
            cur.execute("""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'projects' 
                ORDER BY ordinal_position;
            """)
            for r in cur.fetchall():
                f.write(f"{r}\n")

            f.write("\n=== Table constraints ===\n")
            cur.execute("""
                SELECT conname, contype, pg_get_constraintdef(oid) 
                FROM pg_constraint 
                WHERE conrelid = 'projects'::regclass;
            """)
            for r in cur.fetchall():
                f.write(f"{r}\n")

            f.write("\n=== Existing projects ===\n")
            cur.execute("SELECT * FROM projects LIMIT 10;")
            for r in cur.fetchall():
                f.write(f"{r}\n")

        cur.close()
        conn.close()
        print("Done")
    except Exception as e:
        with open("db_schema_output.txt", "w", encoding="utf-8") as f:
            f.write(f"Error: {e}")

if __name__ == "__main__":
    main()
