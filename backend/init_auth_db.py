import os
import psycopg2
from dotenv import load_dotenv

# โหลด .env จากโฟลเดอร์ backend
load_dotenv()

def init_auth_db():
    print("Connecting to Auth DB...")
    try:
        conn = psycopg2.connect(
            host=os.environ.get("AUTH_DB_HOST", "localhost"),
            port=os.environ.get("AUTH_DB_PORT", "8124"),
            dbname=os.environ.get("AUTH_DB_NAME", "postgres"),
            user=os.environ.get("AUTH_DB_USER", "postgres"),
            password=os.environ.get("AUTH_DB_PASS", "postgres")
        )
        conn.autocommit = True
        cursor = conn.cursor()

        # สร้าง Extension สำหรับเข้ารหัสรหัสผ่าน (pgcrypto)
        print("Creating pgcrypto extension...")
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

        # สร้างตาราง users
        print("Creating users table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                display_name VARCHAR(100),
                avatar_path VARCHAR(255),
                role VARCHAR(20) DEFAULT 'user',
                is_active BOOLEAN DEFAULT true,
                login_count INTEGER DEFAULT 0,
                last_login_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # ตรวจสอบว่ามี Admin หรือยัง ถ้ายังให้สร้างเพิ่ม
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin@domain.com';")
        if cursor.fetchone()[0] == 0:
            print("Inserting default admin user...")
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, display_name, role)
                VALUES (
                    'admin@domain.com', 
                    'admin@domain.com', 
                    crypt('password123', gen_salt('bf')), 
                    'System Administrator', 
                    'admin'
                );
            """)
            print("Default admin created: admin@domain.com / password123")
        else:
            print("Admin user already exists.")

        # ตรวจสอบว่ามี Standard User หรือยัง ถ้ายังให้สร้างเพิ่ม
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'user@domain.com';")
        if cursor.fetchone()[0] == 0:
            print("Inserting default standard user...")
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, display_name, role)
                VALUES (
                    'user@domain.com', 
                    'user@domain.com', 
                    crypt('user123', gen_salt('bf')), 
                    'Standard User', 
                    'user'
                );
            """)
            print("Default user created: user@domain.com / user123")
        else:
            print("Standard user already exists.")

        cursor.close()
        conn.close()
        print("Auth DB Initialization Completed Successfully!")

    except Exception as e:
        print(f"Error initializing Auth DB: {e}")

if __name__ == "__main__":
    init_auth_db()
