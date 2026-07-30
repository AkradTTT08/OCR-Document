import re
import os

app_path = r"d:\OCR-Github\OCR-Document\backend\app.py"

with open(app_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add JWT code and login route
jwt_code = """
import hmac
import hashlib
import base64
import json
import time
from functools import wraps

JWT_SECRET = os.environ.get('JWT_SECRET', 'spectra-qa-super-secret-key-2024')
ADMIN_USER = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASS = os.environ.get('ADMIN_PASSWORD', 'admin123')

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
    
    if username == ADMIN_USER and password == ADMIN_PASS:
        # Token expires in 24 hours
        payload = {
            'user': username,
            'exp': int(time.time()) + (24 * 3600)
        }
        token = encode_jwt(payload)
        return jsonify({'success': True, 'token': token, 'user': username})
        
    return jsonify({'error': 'Invalid credentials'}), 401
"""

# Insert JWT code before API Routes
if "def token_required" not in content:
    content = content.replace("# ========================\n# API Routes\n# ========================", f"# ========================\n# Authentication\n# ========================\n{jwt_code}\n\n# ========================\n# API Routes\n# ========================")

# 2. Add @token_required to all routes EXCEPT /api/health and /api/login
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
    # Use regex to find the route and add @token_required if it's not there
    pattern = r"(" + re.escape(route) + r"[^)]*\))(\ndef )"
    replacement = r"\1\n@token_required\2"
    content = re.sub(pattern, replacement, content)

with open(app_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated app.py with authentication!")
