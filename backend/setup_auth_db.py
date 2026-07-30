import psycopg2
import hashlib
import time

DB_HOST = "127.0.0.1"
DB_PORT = "8124"
DB_NAME = "auth_db"
DB_USER = "auth_admin"
DB_PASSWORD = "auth_password"

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def setup_db():
    print("Waiting for database to be ready...")
    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                user=DB_USER, password=DB_PASSWORD
            )
            cur = conn.cursor()
            
            print("Creating users table...")
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(64) NOT NULL,
                    role VARCHAR(20) DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create default admin user
            admin_hash = hash_password('admin123')
            cur.execute('''
                INSERT INTO users (username, password_hash, role)
                VALUES (%s, %s, %s)
                ON CONFLICT (username) DO NOTHING
            ''', ('admin', admin_hash, 'admin'))
            
            conn.commit()
            cur.close()
            conn.close()
            print("✅ Auth Database setup complete! Default user: admin / admin123")
            break
        except Exception as e:
            print(f"Database not ready yet: {e}")
            retries -= 1
            time.sleep(2)

if __name__ == "__main__":
    setup_db()
