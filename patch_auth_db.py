import os
import re

BASE_DIR = r"d:\OCR-Github\OCR-Document"
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

# 1. สร้าง docker-compose.auth.yml
docker_compose_content = """version: '3.8'

services:
  auth_db:
    image: postgres:15-alpine
    container_name: spectra_auth_db
    environment:
      POSTGRES_USER: auth_admin
      POSTGRES_PASSWORD: auth_password
      POSTGRES_DB: auth_db
    ports:
      - "8124:5432"
    volumes:
      - auth_pgdata:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  auth_pgdata:
"""
with open(os.path.join(BASE_DIR, "docker-compose.auth.yml"), "w", encoding="utf-8") as f:
    f.write(docker_compose_content)

# 2. สร้าง setup_auth_db.py สำหรับสร้างตาราง users และเพิ่ม admin
setup_auth_db_content = """import psycopg2
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
"""
with open(os.path.join(BACKEND_DIR, "setup_auth_db.py"), "w", encoding="utf-8") as f:
    f.write(setup_auth_db_content)

# 3. Patch app.py to use the new Auth DB
app_py_path = os.path.join(BACKEND_DIR, "app.py")
with open(app_py_path, "r", encoding="utf-8") as f:
    app_content = f.read()

new_login_route = """@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
        
    try:
        import psycopg2
        import hashlib
        
        # Connect to Auth DB (Port 8124)
        conn = psycopg2.connect(
            host="127.0.0.1", port="8124", dbname="auth_db",
            user="auth_admin", password="auth_password"
        )
        cur = conn.cursor()
        
        # Hash password to check
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        
        cur.execute("SELECT id, username, role FROM users WHERE username = %s AND password_hash = %s", (username, pwd_hash))
        user = cur.fetchone()
        
        cur.close()
        conn.close()
        
        if user:
            # Token expires in 24 hours
            payload = {
                'user_id': user[0],
                'user': user[1],
                'role': user[2],
                'exp': int(time.time()) + (24 * 3600)
            }
            token = encode_jwt(payload)
            return jsonify({'success': True, 'token': token, 'user': user[1], 'role': user[2]})
            
        return jsonify({'error': 'Invalid credentials'}), 401
        
    except Exception as e:
        logger.error(f"Login DB error: {e}")
        return jsonify({'error': 'Database error during login'}), 500
"""

# ใช้ Regex เปลี่ยนฟังก์ชัน login() เดิมเป็นฟังก์ชันใหม่
pattern = re.compile(r"@app\.route\('/api/login',\s*methods=\['POST'\]\)\s*\ndef login\(\):.*?(?=\n@|\Z)", re.DOTALL)
if pattern.search(app_content):
    app_content = pattern.sub(new_login_route, app_content)
    with open(app_py_path, "w", encoding="utf-8") as f:
        f.write(app_content)
    print("✅ Patched app.py to use Auth DB!")
else:
    print("⚠️ Could not find login route to patch.")
