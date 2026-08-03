import logging
from dotenv import load_dotenv

import os
# Initialize environment and logging first
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

import os
import sys
import tempfile
from typing import List, Dict, Any
from ocr_engine import VERSION
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# เพิ่ม backend dir ใน path
sys.path.insert(0, os.path.dirname(__file__))

from ocr_engine import ocr_pdf_bytes, ocr_pdf_file, ocr_pdf_bytes_generator
from spell_checker import spellcheck_text, spellcheck_pages
from dictionary_manager import (
    load_dictionary,
    reload_dictionary,
    add_custom_word,
    get_dictionary_stats
)
from format_checker import (
    load_format_rules,
    save_format_rules,
    check_format_rules
)
logger = logging.getLogger(__name__)

# สร้าง Flask app
app = Flask(__name__)
CORS(app)

# ตั้งค่า upload
BASE_DIR = Path(__file__).parent.parent
UPLOAD_FOLDER = BASE_DIR / 'uploads'
FRONTEND_FOLDER = BASE_DIR / 'frontend'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

UPLOAD_FOLDER.mkdir(exist_ok=True)
CACHE_FOLDER = BASE_DIR / 'uploads' / 'cache'
CACHE_FOLDER.mkdir(exist_ok=True, parents=True)
KB_IMAGES_FOLDER = BASE_DIR / 'uploads' / 'kb_images'
KB_IMAGES_FOLDER.mkdir(exist_ok=True, parents=True)


def enrich_errors_with_boxes(errors: List[Dict], words_map: List[Dict]) -> List[Dict]:
    """จับคู่กล่อง (Box) กับข้อผิดพลาดเพื่อให้ Frontend แสดง Highlight ได้แม่นยำ"""
    if not words_map or not errors:
        return errors

    for err in errors:
        token = err.get("token", "")
        if not token:
            continue
            
        found_box = None
        found_box_norm = None
        
        # Match exact token
        for w in words_map:
            if w.get('text', '') == token:
                found_box = w.get('box')
                found_box_norm = w.get('box_norm')
                break
                
        if not found_box:
            # Try matching substring
            for w in words_map:
                w_text = w.get('text', '')
                if token in w_text:
                    found_box = w.get('box')
                    found_box_norm = w.get('box_norm')
                    if found_box_norm and len(w_text) > len(token):
                        try:
                            start_idx = w_text.find(token)
                            if start_idx >= 0:
                                total_chars = len(w_text)
                                ratio_start = start_idx / total_chars
                                ratio_end = (start_idx + len(token)) / total_chars
                                line_x0 = found_box_norm[0][0]
                                line_x1 = found_box_norm[1][0]
                                new_x0 = line_x0 + (line_x1 - line_x0) * ratio_start
                                new_x1 = line_x0 + (line_x1 - line_x0) * ratio_end
                                word_box_norm = [
                                    [new_x0, found_box_norm[0][1]],
                                    [new_x1, found_box_norm[1][1]],
                                    [new_x1, found_box_norm[2][1]],
                                    [new_x0, found_box_norm[3][1]]
                                ]
                                found_box_norm = word_box_norm
                        except Exception as e:
                            logger.warning(f"Word box estimation failed: {e}")
                    break
                    
        if found_box:
            err['box'] = found_box
            if found_box_norm:
                err['box_norm'] = found_box_norm
                
    return errors


def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ========================
# Authentication (JWT)
# ========================
import hmac
import hashlib
import base64
import json
import time
from functools import wraps

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

@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
        
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
        
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ใช้ PostgreSQL crypt() ตรวจสอบ bcrypt password
        cursor.execute(
            "SELECT user_id, username, email, display_name, role, is_active "
            "FROM users WHERE username = %s AND password_hash = crypt(%s, password_hash);",
            (username, password)
        )
        user = cursor.fetchone()
        
        if user and user[5]:  # is_active = True
            user_id = str(user[0])
            
            # อัปเดต login_count และ last_login_at
            cursor.execute(
                "UPDATE users SET login_count = login_count + 1, last_login_at = NOW() WHERE user_id = %s;",
                (user[0],)
            )
            conn.commit()
            
            # Token expires in 24 hours
            payload = {
                'user_id': user_id,
                'user': user[1],
                'role': user[4],
                'exp': int(time.time()) + (24 * 3600)
            }
            token = encode_jwt(payload)
            
            cursor.close()
            conn.close()
            return jsonify({
                'success': True,
                'token': token,
                'user': user[1],
                'email': user[2],
                'display_name': user[3],
                'role': user[4]
            })
            
        cursor.close()
        conn.close()
        return jsonify({'error': 'Invalid credentials'}), 401
        
    except Exception as e:
        logger.error(f"Login DB error: {e}", exc_info=True)
        return jsonify({'error': 'Database connection error. Is the DB running?'}), 500



# ========================
# Serve Frontend
# ========================

@app.route('/')
def index():
    return send_from_directory(str(FRONTEND_FOLDER), 'index.html')


@app.route('/<path:filename>')
def frontend_files(filename):
    return send_from_directory(str(FRONTEND_FOLDER), filename)


# ========================
# API Routes
# ========================

@app.route('/api/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'message': 'Thai OCR Spell Check API is running'
    })

@app.route('/api/projects', methods=['GET'])
@token_required
def list_projects():
    """List all projects for document ingestion"""
    try:
        from db_ingestion import get_projects
        projects = get_projects()
        return jsonify({'success': True, 'projects': projects})
    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects', methods=['POST'])
@token_required
def create_project():
    """Create a new project"""
    data = request.get_json()
    logger.info(f"Create project request: {data}")
    if not data or ('name' not in data and 'project_name' not in data):
        return jsonify({'error': 'กรุณาระบุชื่อโครงการ (name หรือ project_name)'}), 400
        
    try:
        from db_ingestion import add_project
        p_name = data.get('project_name') or data.get('name')
        p_code = data.get('project_code')
        desc = data.get('description', '')
        status = data.get('status', 'Active')
        
        # ถ้า project_code เป็น string ว่าง ให้ใช้ None แทน (auto-generate)
        if p_code is not None and not p_code.strip():
            p_code = None
        
        project = add_project(
            name=p_name,
            project_name=p_name,
            project_code=p_code,
            description=desc,
            status=status
        )
        return jsonify({'success': True, 'project': project})
    except Exception as e:
        logger.error(f"Error creating project: {e}", exc_info=True)
        return jsonify({'error': f'สร้างโครงการไม่สำเร็จ: {str(e)}'}), 500

@app.route('/api/projects/<string:project_id>', methods=['DELETE'])
def delete_project_api(project_id):
    """Delete a project"""
    try:
        from db_ingestion import delete_project
        success = delete_project(project_id)
        return jsonify({'success': True, 'message': 'ลบโครงการเรียบร้อยแล้ว'})
    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/ocr', methods=['POST'])
def ocr():
    """
    OCR PDF ไฟล์
    Body: multipart/form-data with 'file' = PDF
    Query params:
        - lang: ภาษา (default: tha+eng)
        - dpi: ความละเอียด (default: 300)
    """
    if 'file' not in request.files:
        return jsonify({'error': 'ไม่พบไฟล์ กรุณาแนบ PDF'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'ไม่ได้เลือกไฟล์'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': 'รองรับเฉพาะไฟล์ PDF เท่านั้น'}), 400

    lang = request.args.get('lang', 'tha+eng')
    dpi = int(request.args.get('dpi', 300))

    try:
        pdf_bytes = file.read()
        pages = ocr_pdf_bytes(pdf_bytes, dpi=dpi, lang=lang)
        
        return jsonify({
            'success': True,
            'filename': secure_filename(file.filename),
            'pages': pages,
            'total_pages': len(pages)
        })
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/spellcheck', methods=['POST'])
def spellcheck():
    """
    ตรวจสอบ spell check ของข้อความ
    Body JSON: { text: "..." }
    """
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': 'กรุณาส่ง JSON { "text": "..." }'}), 400

    text = data['text']
    include_suggestions = data.get('include_suggestions', True)
    words_map = data.get('words', [])

    try:
        spell_result = spellcheck_text(text, include_suggestions=include_suggestions)
        errors = spell_result.get('errors', [])
        
        # ตรวจสอบรูปแบบ (Format Rules) และเพิ่มเข้าลิสต์ข้อผิดพลาด
        try:
            format_errors = check_format_rules(text)
            errors.extend(format_errors)
        except Exception as fmt_err:
            logger.error(f"Format check error in api/spellcheck: {fmt_err}")
            
        # จับคู่กล่องข้อความ
        if words_map:
            enrich_errors_with_boxes(errors, words_map)
            
        # อัปเดตข้อมูลสรุป
        spell_result['errors'] = errors
        summary = spell_result.get('summary', {})
        if summary:
            format_count = sum(1 for e in errors if e.get('error_type') == 'format')
            summary['error_count'] = summary.get('error_count', 0) + format_count
            
        return jsonify({
            'success': True,
            'result': spell_result
        })
    except Exception as e:
        logger.error(f"Spell check error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/view/<session_id>/<int:page_num>')
def view_page(session_id, page_num):
    """Serve cached page image"""
    session_id = secure_filename(session_id)
    directory = CACHE_FOLDER / session_id
    filename = f"page_{page_num}.jpg"
    full_path = directory / filename
    
    logger.info(f"Serving image request: {full_path} (exists: {full_path.exists()})")
    
    if not full_path.exists():
        logger.warning(f"Image 404: {full_path}")
        return "Image not found", 404
        
    return send_from_directory(str(directory), filename)


@app.route('/api/process', methods=['POST'])
def process():
    """
    รวม OCR + Spell Check แบบ sync (return JSON ปกติ)
    Body: multipart/form-data with 'file' = PDF
    Query params: lang, dpi, include_suggestions
    """
    if 'file' not in request.files:
        return jsonify({'error': 'ไม่พบไฟล์'}), 400

    file = request.files['file']
    if not allowed_file(file.filename):
        return jsonify({'error': 'รองรับเฉพาะไฟล์ PDF เท่านั้น'}), 400

    lang = request.args.get('lang', 'tha+eng')
    dpi = int(request.args.get('dpi', 300))
    include_suggestions = request.args.get('include_suggestions', 'true').lower() == 'true'
    project_id = request.form.get('project_id')
    if project_id:
        try:
            project_id = int(project_id)
        except ValueError:
            project_id = None


    try:
        pdf_bytes = file.read()
        filename = secure_filename(file.filename)

        # OCR แต่ละหน้า
        pages = ocr_pdf_bytes(pdf_bytes, dpi=dpi, lang=lang)

        # Spell check แต่ละหน้า
        for page in pages:
            try:
                page['spell_check'] = spellcheck_text(
                    page.get('text', ''),
                    include_suggestions=include_suggestions
                )
                
                # ตรวจสอบรูปแบบ (Format Rules)
                try:
                    format_errors = check_format_rules(page.get('text', ''))
                    errors = page['spell_check'].get('errors', [])
                    errors.extend(format_errors)
                    
                    # จับคู่กล่องข้อความ
                    enrich_errors_with_boxes(errors, page.get('words', []))
                    
                    summary = page['spell_check'].get('summary', {})
                    if summary:
                        summary['error_count'] = summary.get('error_count', 0) + len(format_errors)
                except Exception as fmt_err:
                    logger.error(f"Format check error in api/process on page {page.get('page_number')}: {fmt_err}")
                    
            except Exception as spell_err:
                logger.error(f"Spell check error on page {page.get('page_number')}: {spell_err}")
                page['spell_check'] = {
                    'tokens': [], 'errors': [],
                    'summary': {
                        'thai_tokens': 0, 'english_tokens': 0,
                        'total_tokens': 0, 'error_count': 0,
                        'thai_errors': 0, 'english_errors': 0,
                        'semantic_errors': 0, 'error_rate': 0
                    }
                }

        # สรุปผลรวมทุกหน้า
        total_thai = sum((p.get('spell_check') or {}).get('summary', {}).get('thai_tokens', 0) for p in pages)
        total_eng  = sum((p.get('spell_check') or {}).get('summary', {}).get('english_tokens', 0) for p in pages)
        total_err  = sum((p.get('spell_check') or {}).get('summary', {}).get('error_count', 0) for p in pages)
        total_tok  = total_thai + total_eng
        
        # --- Data Ingestion Pipeline ---
        try:
            full_markdown = "\n\n".join([page.get('text', '') for page in pages])
            if full_markdown.strip():
                from db_ingestion import ingest_markdown_document
                logger.info(f"Triggering data ingestion pipeline for {filename} (Project: {project_id})...")
                ingest_markdown_document(filename, full_markdown.strip(), project_id=project_id)
        except Exception as ingest_error:
            logger.error(f"Failed to ingest document to database: {ingest_error}")
        # -------------------------------


        return jsonify({
            'success': True,
            'filename': filename,
            'pages': pages,
            'total_pages': len(pages),
            'summary': {
                'total_pages': len(pages),
                'total_thai_tokens': total_thai,
                'total_english_tokens': total_eng,
                'total_errors': total_err,
                'error_rate': round(total_err / total_tok * 100, 2) if total_tok > 0 else 0,
            }
        })

    except Exception as e:
        logger.error(f"Process error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/process_stream', methods=['POST'])
def process_stream():
    """
    รวม OCR + Spell Check ในรูปแบบ Stream (SSE)
    เพื่อรายงานความคืบหน้าทีละหน้า
    """
    if 'file' not in request.files:
        return jsonify({'error': 'ไม่พบไฟล์'}), 400

    file = request.files['file']
    lang = request.args.get('lang', 'tha+eng')
    dpi = int(request.args.get('dpi', 300))
    auto_spellcheck = request.args.get('auto_spellcheck', 'false').lower() == 'true'
    include_suggestions = request.args.get('include_suggestions', 'true').lower() == 'true'
    
    pdf_bytes = file.read()
    filename = secure_filename(file.filename)

    def generate():
        import json
        import time
        import uuid
        from PIL import Image
        
        session_id = str(uuid.uuid4())
        session_dir = CACHE_FOLDER / session_id
        session_dir.mkdir(exist_ok=True)
        
        try:
            start_time = time.time()
            
            # Start event
            yield f"data: {json.dumps({'type': 'start', 'session_id': session_id})}\n\n"

            # Callback สำหรับส่งความคืบหน้า
            def progress_cb(page, total, status, elapsed):
                data = json.dumps({
                    'type': 'progress',
                    'page': page,
                    'total': total,
                    'status': status,
                    'elapsed': round(elapsed, 2)
                })
                #yield f"data: {data}\n\n"
                # Flask generator requires actual yield from here or passing it up
                # So we'll collect events in a queue or just return the generator
                pass
            
            # เนื่องจาก Flask generator ต้อง yield ค่าออกไป
            # เราจะแก้โครงสร้างให้ ocr_pdf_bytes รับ yield หรือใช้ wrapper
            # Get total pages instantly using pdfinfo_from_bytes
            total_pages = 1
            try:
                from pdf2image.pdf2image import pdfinfo_from_bytes
                from ocr_engine import POPPLER_PATH
                poppler_path = POPPLER_PATH if os.path.exists(POPPLER_PATH) else None
                info = pdfinfo_from_bytes(pdf_bytes, poppler_path=poppler_path)
                total_pages = int(info.get("Pages", 1))
                logger.info(f"Instantly detected PDF page count: {total_pages}")
            except Exception as info_err:
                logger.error(f"Failed to get PDF info: {info_err}")

            # ส่ง event เริ่มต้น
            yield f"data: {json.dumps({'type': 'start', 'filename': filename})}\n\n"
            
            # แจ้งความคืบหน้าเรื่องการโหลด Engine
            yield f"data: {json.dumps({'type': 'progress', 'page': 0, 'total': total_pages, 'status': 'loading_engine', 'elapsed': 0})}\n\n"

            pages = []
            page_count = 0
            # OCR และ Spell Check ทีละหน้า (Streaming)
            for page, img in ocr_pdf_bytes_generator(pdf_bytes, dpi=dpi, lang=lang):
                page_num = page['page_number']
                total_pages = page.get('total_pages', total_pages)
                page_count += 1
                
                # Emit progress right after a page is OCR-ed and we start processing/spellchecking
                elapsed = time.time() - start_time
                yield f"data: {json.dumps({'type': 'progress', 'page': page_count, 'total': total_pages, 'status': f'processing_page_{page_num}', 'elapsed': elapsed})}\n\n"

                # 1. บันทึกรูปใน Session Dir (เพื่อทำ Preview)
                img_name = f"page_{page_num}.jpg"
                img_path = session_dir / img_name
                
                try:
                    # แปลงและบันทึกเป็น JPEG
                    img.convert('RGB').save(str(img_path), "JPEG", quality=85)
                    page['session_id'] = session_id
                    page['image_url'] = img_name
                    logger.info(f"Saved preview image for page {page_num}: {img_path}")
                except Exception as save_err:
                    logger.error(f"Failed to save preview image: {save_err}")

                # 2. ตรวจคำผิดและจัดรูปแบบ (ถ้าเปิดโหมด Auto)
                if auto_spellcheck:
                    try:
                        spell_result = spellcheck_text(
                            page.get('text', ''),
                            include_suggestions=include_suggestions
                        )
                        errors = spell_result.get('errors', [])
                        
                        # ตรวจสอบรูปแบบ (Format Rules)
                        try:
                            format_errors = check_format_rules(page.get('text', ''))
                            errors.extend(format_errors)
                        except Exception as fmt_err:
                            logger.error(f"Format check error in stream on page {page_num}: {fmt_err}")
                            
                        # จับคู่กล่องข้อความ
                        words_map = page.get('words', [])
                        enrich_errors_with_boxes(errors, words_map)
                        
                        spell_result['errors'] = errors
                        summary = spell_result.get('summary', {})
                        if summary:
                            format_count = sum(1 for e in errors if e.get('error_type') == 'format')
                            summary['error_count'] = summary.get('error_count', 0) + format_count
                            
                        page['spell_check'] = spell_result
                    except Exception as spell_err:
                        logger.error(f"Spell check error on page {page_num}: {spell_err}", exc_info=True)
                        page['spell_check'] = {
                            'tokens': [], 'errors': [],
                            'summary': {
                                'thai_tokens': 0, 'english_tokens': 0,
                                'total_tokens': 0, 'error_count': 0,
                                'thai_errors': 0, 'english_errors': 0,
                                'semantic_errors': 0, 'error_rate': 0
                            }
                        }
                else:
                    # ข้ามการตรวจคำผิด
                    page['spell_check'] = None
                
                pages.append(page)
                yield f"data: {json.dumps({'type': 'page_result', 'page': page})}\n\n"

            # เรียงหน้าให้ถูกต้องเนื่องจาก ThreadPool อาจส่งผลลัพธ์กลับมาสลับลำดับ
            pages.sort(key=lambda p: p['page_number'])

            # สรุปผลตอนท้าย
            total_errors = sum((p.get('spell_check') or {}).get('summary', {}).get('error_count', 0) for p in pages)
            total_tokens = sum((p.get('spell_check') or {}).get('summary', {}).get('thai_tokens', 0) for p in pages)
            
            final_data = {
                'type': 'complete',
                'summary': {
                    'total_pages': len(pages),
                    'total_thai_tokens': total_tokens,
                    'total_errors': total_errors,
                    'error_rate': round(total_errors / total_tokens * 100, 2) if total_tokens > 0 else 0,
                    'total_time': round(time.time() - start_time, 2)
                }
            }
            yield f"data: {json.dumps(final_data)}\n\n"

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(f"Stream error: {e}", exc_info=True)
            with open(os.path.join(BASE_DIR, 'backend', 'stream_error.txt'), 'w', encoding='utf-8') as f:
                f.write(f"Error: {e}\nTraceback:\n{tb}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    from flask import Response
    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/dictionary/stats', methods=['GET'])
def dictionary_stats():
    """ดูสถิติ dictionary"""
    try:
        stats = get_dictionary_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug_env', methods=['GET'])
def debug_env():
    import os
    return jsonify({
        'key_exists': 'GOOGLE_API_KEY' in os.environ,
        'key_length': len(os.environ.get('GOOGLE_API_KEY', '')),
        'cwd': os.getcwd(),
        '__file__': __file__
    })


@app.route('/api/dictionary/add', methods=['POST'])
def add_word():
    """เพิ่มคำใหม่ใน custom dictionary"""
    data = request.get_json()
    if not data or 'word' not in data:
        return jsonify({'error': 'กรุณาส่ง JSON { "word": "..." }'}), 400

    word = data['word'].strip()
    if not word:
        return jsonify({'error': 'คำว่างไม่สามารถเพิ่มได้'}), 400

    success = add_custom_word(word)
    if success:
        return jsonify({'success': True, 'message': f'เพิ่มคำ "{word}" สำเร็จ'})
    else:
        return jsonify({'error': 'เพิ่มคำไม่สำเร็จ'}), 500


@app.route('/api/dictionary/reload', methods=['POST'])
def reload_dict():
    """โหลด dictionary ใหม่"""
    try:
        dictionary = reload_dictionary()
        return jsonify({
            'success': True,
            'message': f'โหลด dictionary ใหม่สำเร็จ ({len(dictionary):,} คำ)'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# ========================
# Knowledge Base API Routes
# ========================
# Schema Reference:
#   projects(project_id, project_code, project_name, description, status, created_at)
#   documents(doc_id, project_id, doc_category, doc_type, original_filename,
#             full_markdown_content, is_golden_data, file_hash, version, status, created_at)
#   document_chunks(chunk_id, doc_id, chunk_text, embedding vector(384), created_at)

@app.route('/api/kb/stats', methods=['GET'])
def kb_stats():
    """ดูสถิติรวมของ Knowledge Base"""
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM projects;")
        project_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM documents;")
        doc_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM document_chunks;")
        chunk_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'stats': {
                'projects': project_count,
                'documents': doc_count,
                'chunks': chunk_count
            }
        })
    except Exception as e:
        logger.error(f"KB stats error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/kb/documents', methods=['GET'])
def kb_documents():
    """
    ดูเอกสารทั้งหมดใน DB (optionally filtered by project_id)
    Query: ?project_id=<id>&limit=50&offset=0
    """
    project_id = request.args.get('project_id')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)

    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        if project_id:
            cursor.execute(
                "SELECT doc_id, original_filename, project_id, doc_category, doc_type, status, created_at, is_golden_data "
                "FROM documents WHERE project_id = %s ORDER BY doc_id DESC LIMIT %s OFFSET %s;",
                (project_id, limit, offset)
            )
        else:
            cursor.execute(
                "SELECT doc_id, original_filename, project_id, doc_category, doc_type, status, created_at, is_golden_data "
                "FROM documents ORDER BY doc_id DESC LIMIT %s OFFSET %s;",
                (limit, offset)
            )

        rows = cursor.fetchall()
        documents = []
        for row in rows:
            doc_id_val = row[0]
            cursor.execute("SELECT COUNT(*) FROM document_chunks WHERE doc_id = %s;", (doc_id_val,))
            chunk_count = cursor.fetchone()[0]

            documents.append({
                'id': doc_id_val,
                'name': row[1] or 'ไม่ระบุชื่อ',
                'project_id': row[2],
                'doc_category': row[3],
                'doc_type': row[4],
                'status': row[5],
                'created_at': row[6].isoformat() if row[6] else None,
                'is_golden_data': row[7] if len(row) > 7 else False,
                'chunk_count': chunk_count
            })

        if project_id:
            cursor.execute("SELECT COUNT(*) FROM documents WHERE project_id = %s;", (project_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM documents;")
        total = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'documents': documents, 'total': total})
    except Exception as e:
        logger.error(f"KB documents error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/kb/documents/<string:doc_id>', methods=['GET'])
def kb_document_detail(doc_id):
    """ดูรายละเอียดเอกสาร รวมถึง content และ chunks"""
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT d.doc_id, d.project_id, d.doc_category, d.doc_type, d.original_filename,
                   d.full_markdown_content, d.is_golden_data, d.file_hash, d.version, d.status, d.created_at,
                   p.project_name
            FROM documents d
            LEFT JOIN projects p ON d.project_id = p.project_id
            WHERE d.doc_id = %s;
            """,
            (doc_id,)
        )
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return jsonify({'error': 'ไม่พบเอกสาร'}), 404

        doc = {
            'id': str(row[0]) if row[0] else None,
            'project_id': str(row[1]) if row[1] else None,
            'doc_category': row[2],
            'doc_type': row[3],
            'filename': row[4],
            'content': row[5],
            'is_golden_data': row[6],
            'file_hash': row[7],
            'version': row[8],
            'status': row[9],
            'created_at': row[10].isoformat() if row[10] else None,
            'project_name': row[11]
        }

        # Check total pages in kb_images directory
        total_pages = 0
        img_dir = KB_IMAGES_FOLDER / doc['id']
        if img_dir.exists():
            import glob
            total_pages = len(glob.glob(str(img_dir / 'page_*.jpg')))
        doc['total_pages'] = total_pages

        # Fetch chunks
        cursor.execute(
            "SELECT chunk_id, chunk_text FROM document_chunks WHERE doc_id = %s ORDER BY chunk_id ASC;",
            (doc_id,)
        )
        chunks = [{'id': r[0], 'text': r[1]} for r in cursor.fetchall()]

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'document': doc, 'chunks': chunks})
    except Exception as e:
        logger.error(f"KB document detail error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/kb/search', methods=['GET'])
def kb_search():
    """
    ค้นหาเอกสารด้วย Vector Similarity
    Query: ?q=<text>&project_id=<id>&top_k=5
    """
    query_text = request.args.get('q', '').strip()
    project_id = request.args.get('project_id')
    top_k = request.args.get('top_k', 5, type=int)

    if not query_text:
        return jsonify({'error': 'กรุณาระบุคำค้นหา (q)'}), 400

    try:
        from db_ingestion import get_model, get_db_connection
        embedder = get_model()
        query_vec = embedder.encode([query_text])[0].tolist()

        conn = get_db_connection()
        cursor = conn.cursor()

        if project_id:
            cursor.execute("""
                SELECT dc.chunk_id, dc.doc_id, dc.chunk_text,
                       dc.embedding <=> %s::vector AS distance,
                       d.original_filename AS doc_name
                FROM document_chunks dc
                JOIN documents d ON d.doc_id = dc.doc_id
                WHERE d.project_id = %s AND (dc.embedding <=> %s::vector) < 0.65
                ORDER BY distance ASC
                LIMIT %s;
            """, (query_vec, project_id, query_vec, top_k))
        else:
            cursor.execute("""
                SELECT dc.chunk_id, dc.doc_id, dc.chunk_text,
                       dc.embedding <=> %s::vector AS distance,
                       d.original_filename AS doc_name
                FROM document_chunks dc
                JOIN documents d ON d.doc_id = dc.doc_id
                WHERE (dc.embedding <=> %s::vector) < 0.65
                ORDER BY distance ASC
                LIMIT %s;
            """, (query_vec, query_vec, top_k))

        rows = cursor.fetchall()
        results = [
            {
                'chunk_id': r[0],
                'document_id': r[1],
                'chunk_text': r[2],
                'similarity': round(1 - float(r[3]), 4),
                'doc_name': r[4] or 'ไม่ระบุชื่อ'
            }
            for r in rows
        ]

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'results': results, 'query': query_text})
    except Exception as e:
        logger.error(f"KB search error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/format_rules', methods=['GET'])
def get_format_rules_route():
    """ดึงกฎการจัดรูปแบบทั้งหมด"""
    try:
        rules = load_format_rules()
        return jsonify({'success': True, 'rules': rules})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/format_rules', methods=['POST'])
def save_format_rules_route():
    """บันทึกกฎการจัดรูปแบบทั้งหมด"""
    try:
        data = request.get_json()
        if not data or 'rules' not in data:
            return jsonify({'error': 'กรุณาส่ง JSON { "rules": [...] }'}), 400
        
        success = save_format_rules(data['rules'])
        if success:
            return jsonify({'success': True, 'message': 'บันทึกกฎการจัดรูปแบบสำเร็จ'})
        else:
            return jsonify({'error': 'ไม่สามารถบันทึกกฎได้'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/kb/ingest', methods=['POST'])
def kb_ingest():
    """บันทึกเอกสารเข้า Project (Knowledge Base) ด้วยตัวเอง"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    filename = data.get('filename')
    markdown_text = data.get('markdown_text')
    project_id = data.get('project_id')
    doc_category = data.get('doc_category', 'Reference')
    doc_type = data.get('doc_type', 'PDF')
    is_golden_data = data.get('is_golden_data', False)

    session_id = data.get('session_id')

    if not filename or not markdown_text or not project_id:
        return jsonify({'error': 'กรุณาระบุ filename, markdown_text, และ project_id'}), 400

    try:
        from db_ingestion import ingest_markdown_document
        import shutil
        
        logger.info(f"Manual DB ingestion for {filename} (Project ID: {project_id})...")
        success, msg_or_err = ingest_markdown_document(
            filename=filename,
            markdown_text=markdown_text.strip(),
            project_id=project_id,
            doc_category=doc_category,
            doc_type=doc_type,
            is_golden_data=is_golden_data
        )
        if success:
            doc_id = msg_or_err
            
            # If session_id provided, copy images to permanent storage
            if session_id:
                src_dir = CACHE_FOLDER / session_id
                if src_dir.exists():
                    dest_dir = KB_IMAGES_FOLDER / doc_id
                    dest_dir.mkdir(exist_ok=True, parents=True)
                    for item in src_dir.glob("page_*.jpg"):
                        shutil.copy2(item, dest_dir / item.name)
                        
            return jsonify({'success': True, 'message': 'บันทึกเอกสารเข้าโครงการสำเร็จ', 'doc_id': doc_id})
        else:
            return jsonify({'error': f'การบันทึกเอกสารไม่สำเร็จ: {msg_or_err}'}), 500
    except Exception as e:
        logger.error(f"KB ingest error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/kb/documents/<string:doc_id>', methods=['PUT'])
def kb_update_document(doc_id):
    """แก้ไขเนื้อหาเอกสาร (Markdown) และทำการ Chunk/Embed ใหม่"""
    try:
        data = request.get_json()
        new_markdown = data.get('markdown_text', '')
        
        if not new_markdown.strip():
            return jsonify({'error': 'เนื้อหาเอกสารว่างเปล่า'}), 400

        from db_ingestion import update_markdown_document
        success, msg = update_markdown_document(doc_id, new_markdown)
        if success:
            return jsonify({'success': True, 'message': 'อัปเดตเอกสารและ Chunks สำเร็จ'})
        else:
            return jsonify({'error': f'การอัปเดตไม่สำเร็จ: {msg}'}), 500
    except Exception as e:
        logger.error(f"Error updating doc {doc_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/kb/view/<string:doc_id>/<int:page_num>')
def kb_view_page(doc_id, page_num):
    """Serve permanent page image from Knowledge Base"""
    from werkzeug.utils import secure_filename
    doc_id = secure_filename(doc_id)
    directory = KB_IMAGES_FOLDER / doc_id
    filename = f"page_{page_num}.jpg"
    full_path = directory / filename
    
    if not full_path.exists():
        return "Image not found", 404
        
    return send_from_directory(str(directory), filename)


@app.route('/api/kb/documents/<string:doc_id>', methods=['DELETE'])
def kb_delete_document(doc_id):
    """ลบเอกสารออกจาก Knowledge Base"""
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if doc exists
        cursor.execute("SELECT doc_id FROM documents WHERE doc_id = %s;", (doc_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'ไม่พบเอกสารที่ต้องการลบ'}), 404
            
        # Delete document (CASCADE will delete chunks)
        cursor.execute("DELETE FROM documents WHERE doc_id = %s;", (doc_id,))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'ลบเอกสารเรียบร้อยแล้ว'})
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"KB delete document error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


# ===================================================================
# AI Agent Skills Endpoints (agent_skills)
# ===================================================================

def ensure_skills_table():
    """Ensure agent_skills table exists in PostgreSQL."""
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_skills (
                skill_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                skill_name VARCHAR(100) NOT NULL,
                skill_description TEXT,
                markdown_instructions TEXT NOT NULL,
                target_doc_type VARCHAR(50),
                version INT DEFAULT 1,
                is_active BOOLEAN DEFAULT TRUE,
                created_by VARCHAR(50),
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        conn.commit()
        cursor.close()
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error ensuring agent_skills table: {e}", exc_info=True)
    finally:
        if conn: conn.close()


@app.route('/api/skills', methods=['GET'])
def get_skills():
    """ดึงรายการ AI Skills ทั้งหมด"""
    ensure_skills_table()
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        search = request.args.get('search', '').strip()
        target_type = request.args.get('target_doc_type', '').strip()

        query = """
            SELECT skill_id, skill_name, skill_description, markdown_instructions,
                   target_doc_type, version, is_active, created_by, created_at
            FROM agent_skills
            WHERE 1=1
        """
        params = []

        if search:
            query += " AND (skill_name ILIKE %s OR skill_description ILIKE %s OR markdown_instructions ILIKE %s)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])

        if target_type:
            query += " AND target_doc_type = %s"
            params.append(target_type)

        query += " ORDER BY created_at DESC;"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        skills = []
        for r in rows:
            skills.append({
                'skill_id': str(r[0]),
                'skill_name': r[1],
                'skill_description': r[2],
                'markdown_instructions': r[3],
                'target_doc_type': r[4],
                'version': r[5],
                'is_active': r[6],
                'created_by': r[7],
                'created_at': r[8].isoformat() if r[8] else None
            })

        return jsonify({'success': True, 'skills': skills, 'total': len(skills)})
    except Exception as e:
        logger.error(f"Get skills error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/skills/<string:skill_id>', methods=['GET'])
def get_skill_detail(skill_id):
    """ดูรายละเอียด AI Skill รายรายการ"""
    ensure_skills_table()
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT skill_id, skill_name, skill_description, markdown_instructions,
                   target_doc_type, version, is_active, created_by, created_at
            FROM agent_skills
            WHERE skill_id = %s;
        """, (skill_id,))
        r = cursor.fetchone()
        if not r:
            return jsonify({'error': 'ไม่พบ Skill ที่ต้องการ'}), 404

        skill = {
            'skill_id': str(r[0]),
            'skill_name': r[1],
            'skill_description': r[2],
            'markdown_instructions': r[3],
            'target_doc_type': r[4],
            'version': r[5],
            'is_active': r[6],
            'created_by': r[7],
            'created_at': r[8].isoformat() if r[8] else None
        }

        return jsonify({'success': True, 'skill': skill})
    except Exception as e:
        logger.error(f"Get skill detail error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/skills', methods=['POST'])
def create_skill():
    """สร้าง AI Skill ใหม่"""
    ensure_skills_table()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No payload provided'}), 400

    skill_name = data.get('skill_name')
    markdown_instructions = data.get('markdown_instructions')

    if not skill_name or not markdown_instructions:
        return jsonify({'error': 'กรุณาระบุ skill_name และ markdown_instructions'}), 400

    skill_description = data.get('skill_description', '')
    target_doc_type = data.get('target_doc_type', 'General')
    version = data.get('version', 1)
    is_active = data.get('is_active', True)
    created_by = data.get('created_by', 'Admin')

    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO agent_skills (skill_name, skill_description, markdown_instructions, target_doc_type, version, is_active, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING skill_id;
        """, (skill_name, skill_description, markdown_instructions, target_doc_type, version, is_active, created_by))

        new_id = cursor.fetchone()[0]
        conn.commit()

        return jsonify({'success': True, 'message': 'สร้าง AI Skill สำเร็จ', 'skill_id': str(new_id)})
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Create skill error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/skills/<string:skill_id>', methods=['PUT'])
def update_skill(skill_id):
    """แก้ไข AI Skill"""
    ensure_skills_table()
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No payload provided'}), 400

    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check existing
        cursor.execute("SELECT skill_id FROM agent_skills WHERE skill_id = %s;", (skill_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'ไม่พบ Skill ที่ต้องการแก้ไข'}), 404

        skill_name = data.get('skill_name')
        skill_description = data.get('skill_description')
        markdown_instructions = data.get('markdown_instructions')
        target_doc_type = data.get('target_doc_type')
        version = data.get('version')
        is_active = data.get('is_active')
        created_by = data.get('created_by')

        cursor.execute("""
            UPDATE agent_skills
            SET skill_name = COALESCE(%s, skill_name),
                skill_description = COALESCE(%s, skill_description),
                markdown_instructions = COALESCE(%s, markdown_instructions),
                target_doc_type = COALESCE(%s, target_doc_type),
                version = COALESCE(%s, version),
                is_active = COALESCE(%s, is_active),
                created_by = COALESCE(%s, created_by)
            WHERE skill_id = %s;
        """, (skill_name, skill_description, markdown_instructions, target_doc_type, version, is_active, created_by, skill_id))

        conn.commit()
        return jsonify({'success': True, 'message': 'อัปเดต AI Skill สำเร็จ'})
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Update skill error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/skills/<string:skill_id>', methods=['DELETE'])
def delete_skill(skill_id):
    """ลบ AI Skill"""
    ensure_skills_table()
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT skill_id FROM agent_skills WHERE skill_id = %s;", (skill_id,))
        if not cursor.fetchone():
            return jsonify({'error': 'ไม่พบ Skill ที่ต้องการลบ'}), 404

        cursor.execute("DELETE FROM agent_skills WHERE skill_id = %s;", (skill_id,))
        conn.commit()

        return jsonify({'success': True, 'message': 'ลบ AI Skill เรียบร้อยแล้ว'})
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Delete skill error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()


@app.route('/api/skills/<string:skill_id>/export', methods=['GET'])
def export_skill_md(skill_id):
    """Export AI Skill เป็นไฟล์ SKILL.md"""
    ensure_skills_table()
    conn = None
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT skill_name, skill_description, markdown_instructions, target_doc_type, version, created_by
            FROM agent_skills
            WHERE skill_id = %s;
        """, (skill_id,))
        r = cursor.fetchone()
        if not r:
            return jsonify({'error': 'ไม่พบ Skill'}), 404

        name, desc, instructions, target_type, version, created_by = r

        md_content = f"""---
name: "{name}"
description: "{desc or ''}"
target_doc_type: "{target_type or 'General'}"
version: {version or 1}
created_by: "{created_by or 'Admin'}"
---

# {name}

{desc or ''}

## Skill Instructions (Skill.md)

{instructions}
"""
        from flask import Response
        filename = f"{name.lower().replace(' ', '_')}_SKILL.md"
        return Response(
            md_content,
            mimetype="text/markdown",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Export skill error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
    finally:
        if conn: conn.close()

from db_ingestion import search_knowledge_base
from email_service import send_qa_report

@app.route('/api/qa_consult', methods=['POST', 'OPTIONS'])
def qa_consult_api():
    if request.method == 'OPTIONS':
        return '', 200
        
    try:
        file = request.files.get('file')
        doc_type = request.form.get('doc_type', 'Requirement')
        email = request.form.get('email', '')
        
        if not file or not email:
            return jsonify({'type': 'error', 'message': 'Missing file or email'}), 400

        def generate():
            try:
                yield f"data: {json.dumps({'type': 'progress', 'pct': 10, 'message': 'กำลังวิเคราะห์ข้อความจากเอกสาร PDF...' })}\n\n"
                
                # 1. OCR
                pdf_bytes = file.read()
                from ocr_engine import ocr_pdf_bytes
                
                ocr_results = ocr_pdf_bytes(pdf_bytes)
                extracted_text = ''
                total_pages = len(ocr_results)
                
                for page in ocr_results:
                    if 'error' not in page or not page['error']:
                        extracted_text += page.get('text', '') + '\n\n'
                
                if not extracted_text.strip():
                    yield f"data: {json.dumps({'type': 'error', 'message': 'ไม่พบข้อความในเอกสาร' })}\n\n"
                    return

                yield f"data: {json.dumps({'type': 'progress', 'pct': 40, 'message': 'กำลังสืบค้นฐานข้อมูล Knowledge Base (Vector Search)...' })}\n\n"
                
                # 2. Vector Search
                kb_results = search_knowledge_base(extracted_text[:2000], doc_type=doc_type, top_k=5)
                
                kb_context = ''
                for res in kb_results:
                    kb_context += f"[Source: {res['filename']}]\n{res['chunk_text']}\n\n"
                
                yield f"data: {json.dumps({'type': 'progress', 'pct': 70, 'message': 'กำลังใช้ AI วิเคราะห์และเปรียบเทียบข้อมูล...' })}\n\n"
                
                # 3. Analyze with Gemini
                from ocr_engine import _get_gemini_client
                client = _get_gemini_client()
                
                prompt = f"""คุณคือผู้เชี่ยวชาญด้าน QA ของระบบ
หน้าที่ของคุณคือเปรียบเทียบเอกสารที่อัปโหลดมา กับมาตรฐานในฐานข้อมูล (Knowledge Base)
ประเภทเอกสาร: {doc_type}

--- ข้อมูลอ้างอิงจาก Knowledge Base ---
{kb_context if kb_context else 'ไม่พบข้อมูลอ้างอิงเฉพาะเจาะจงในระบบ'}

--- เอกสารที่ต้องการตรวจสอบ ---
{extracted_text[:8000]}

กรุณาสรุป:
1. ความสอดคล้องกับมาตรฐาน
2. สิ่งที่ขาดหายไปหรือจุดที่พบข้อผิดพลาด
3. ข้อเสนอแนะ
"""
                
                gemini_res = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                )
                
                report = gemini_res.text
                
                yield f"data: {json.dumps({'type': 'progress', 'pct': 90, 'message': 'กำลังเตรียมส่งรายงานไปยังอีเมล...' })}\n\n"
                
                # 4. Send Email
                email_sent = send_qa_report(email, doc_type, file.filename, report)
                
                if email_sent:
                    yield f"data: {json.dumps({'type': 'complete', 'result': {'total_pages': total_pages, 'status': 'success'} })}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'วิเคราะห์สำเร็จ แต่ไม่สามารถส่งอีเมลได้ (ตรวจสอบ .env GMAIL_APP_PASSWORD)' })}\n\n"
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': str(e) })}\n\n"

        return Response(generate(), mimetype='text/event-stream')

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'type': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info(f"Thai OCR Spell Check System (v{VERSION})")
    logger.info("=" * 50)
    
    # โหลด dictionary ตอนเริ่ม
    logger.info("กำลังโหลด dictionary...")
    stats = get_dictionary_stats()
    logger.info(f"Dictionary พร้อมใช้งาน: {stats['total_words']:,} คำ")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False
    )
