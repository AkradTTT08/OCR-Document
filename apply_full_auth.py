import os
import re

BASE_DIR = r"d:\OCR-Github\OCR-Document"
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

# 1. Update requirements.txt to include SQLAlchemy
req_path = os.path.join(BASE_DIR, "requirements.txt")
with open(req_path, "r", encoding="utf-8") as f:
    reqs = f.read()
if "SQLAlchemy" not in reqs:
    with open(req_path, "a", encoding="utf-8") as f:
        f.write("\nSQLAlchemy>=2.0.0\n")

# 2. Create auth_db.py (SQLAlchemy Session config)
auth_db_content = """from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Connect to the Auth Database running on port 8124
DATABASE_URL = "postgresql://auth_admin:auth_password@127.0.0.1:8124/auth_db"

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""
with open(os.path.join(BACKEND_DIR, "auth_db.py"), "w", encoding="utf-8") as f:
    f.write(auth_db_content)

# 3. Create auth_models.py (Database Schema)
auth_models_content = """from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from auth_db import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(64), nullable=False)
    role = Column(String(20), default="user")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
"""
with open(os.path.join(BACKEND_DIR, "auth_models.py"), "w", encoding="utf-8") as f:
    f.write(auth_models_content)

# 4. Create setup_auth.py (Script to create tables and admin user)
setup_auth_content = """import hashlib
import time
from auth_db import engine, Base, SessionLocal
from auth_models import User

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    print("Waiting for database connection...")
    retries = 5
    while retries > 0:
        try:
            # Create all tables defined in Base
            Base.metadata.create_all(bind=engine)
            
            db = SessionLocal()
            
            # Check if admin exists
            admin_user = db.query(User).filter(User.username == "admin").first()
            if not admin_user:
                print("Creating default admin user...")
                new_admin = User(
                    username="admin",
                    password_hash=hash_password("admin123"),
                    role="admin"
                )
                db.add(new_admin)
                db.commit()
                
            db.close()
            print("✅ Auth DB initialized with SQLAlchemy ORM!")
            break
        except Exception as e:
            print(f"Database not ready yet... {e}")
            retries -= 1
            time.sleep(2)

if __name__ == "__main__":
    init_db()
"""
with open(os.path.join(BACKEND_DIR, "setup_auth.py"), "w", encoding="utf-8") as f:
    f.write(setup_auth_content)

# 5. Patch app.py to include Native JWT, Login Route, and Protect Endpoints
app_py_path = os.path.join(BACKEND_DIR, "app.py")
with open(app_py_path, "r", encoding="utf-8") as f:
    app_content = f.read()

# JWT and Login Logic using ORM
jwt_and_login = """# ========================
# Authentication (JWT + ORM)
# ========================
import hmac
import hashlib
import base64
import json
import time
from functools import wraps
from flask import request, jsonify
from auth_db import SessionLocal
from auth_models import User

JWT_SECRET = os.environ.get('JWT_SECRET', 'spectra-qa-super-secret-key-2024')

def encode_jwt(payload):
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    signature = base64.urlsafe_b64encode(
        hmac.new(JWT_SECRET.encode(), f"{header}.{payload_b64}".encode(), hashlib.sha256).digest()
    ).decode().rstrip('=')
    return f"{header}.{payload_b64}.{signature}"

def decode_jwt(token):
    try:
        parts = token.split('.')
        if len(parts) != 3: return None
        signature = base64.urlsafe_b64encode(
            hmac.new(JWT_SECRET.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256).digest()
        ).decode().rstrip('=')
        if not hmac.compare_digest(parts[2], signature): return None
        
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '==').decode())
        if payload.get('exp', 0) < time.time(): return None
        return payload
    except Exception:
        return None

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == 'OPTIONS':
            return f(*args, **kwargs)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Unauthorized, please login'}), 401
        
        token = auth_header.split(' ')[1]
        payload = decode_jwt(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401
            
        return f(*args, **kwargs)
    return decorated

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
        
    try:
        db = SessionLocal()
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        
        user = db.query(User).filter(User.username == username, User.password_hash == pwd_hash).first()
        
        if user:
            # Token expires in 24 hours
            payload = {
                'user_id': user.id,
                'user': user.username,
                'role': user.role,
                'exp': int(time.time()) + (24 * 3600)
            }
            token = encode_jwt(payload)
            db.close()
            return jsonify({'success': True, 'token': token, 'user': user.username, 'role': user.role})
            
        db.close()
        return jsonify({'error': 'Invalid credentials'}), 401
        
    except Exception as e:
        logger.error(f"Login DB error: {e}")
        return jsonify({'error': 'Database connection error. Is the Auth DB running?'}), 500

"""

# Insert JWT code before "# ========================\n# Serve Frontend" if not already there
if "def token_required" not in app_content:
    app_content = app_content.replace(
        "# ========================\n# Serve Frontend", 
        f"{jwt_and_login}\n# ========================\n# Serve Frontend"
    )

# Add @token_required to all routes EXCEPT /api/health and /api/login
routes_to_protect = [
    "@app.route('/api/projects'",
    "@app.route('/api/projects/<string:project_id>'",
    "@app.route('/api/ocr'",
    "@app.route('/api/spellcheck'",
    "@app.route('/api/process'",
    "@app.route('/api/process_stream'",
    "@app.route('/api/dictionary/stats'",
    "@app.route('/api/dictionary/add'",
    "@app.route('/api/dictionary/reload'",
    "@app.route('/api/kb/stats'",
    "@app.route('/api/kb/documents'",
    "@app.route('/api/kb/documents/<string:doc_id>'",
    "@app.route('/api/kb/search'"
]

for route in routes_to_protect:
    pattern = r"(" + re.escape(route) + r"[^)]*\))(\ndef )"
    # Ensure we don't add it multiple times
    if f"@token_required\ndef" not in app_content:
        replacement = r"\1\n@token_required\2"
        app_content = re.sub(pattern, replacement, app_content)

with open(app_py_path, "w", encoding="utf-8") as f:
    f.write(app_content)

print("✅ Patched app.py with SQLAlchemy ORM and Auth Logic!")
