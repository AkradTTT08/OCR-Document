import logging
from dotenv import load_dotenv

# Initialize environment and logging first
load_dotenv()
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
CACHE_FOLDER.mkdir(exist_ok=True)


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
            logger.error(f"Stream error: {e}", exc_info=True)
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
