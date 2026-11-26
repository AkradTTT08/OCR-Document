"""OCR processing, streaming, page reprocessing, spellcheck, custom dictionary, and OCR history endpoints."""
import json
import logging
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import requests
from flask import Blueprint, Response, jsonify, request, send_file, send_from_directory
from flask_cors import cross_origin
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)
bp = Blueprint('ocr_dictionary', __name__)

from core.config import ALLOWED_EXTENSIONS, BASE_DIR, CACHE_FOLDER, UPLOAD_FOLDER, allowed_file
from orchestrator.pipeline import run_document_pipeline
from format_checker import check_format_rules
from ocr_engine import VERSION, ocr_pdf_bytes, ocr_pdf_bytes_generator, ocr_pdf_file
from spell_checker import spellcheck_pages, spellcheck_text
from dictionary_manager import (
    add_custom_word,
    get_custom_words_list,
    get_dictionary_stats,
    load_dictionary,
    reload_dictionary,
    remove_custom_word,
)

def _thai_visual_char_len(s: str) -> int:
    if not s:
        return 0
    return sum(1 for ch in s if not ('\u0e31' == ch or '\u0e34' <= ch <= '\u0e3a' or '\u0e47' <= ch <= '\u0e4e'))


def enrich_errors_with_boxes(errors: List[Dict], words_map: List[Dict]) -> List[Dict]:
    """จับคู่กล่อง (Box) กับข้อผิดพลาดเพื่อให้ Frontend แสดง Highlight ได้แม่นยำ (รองรับทั้งคำเดี่ยว คำซ้อนในประโยคไทย และวลีหลายคำ)"""
    if not words_map or not errors:
        return errors

    for err in errors:
        token = (err.get("token") or "").strip()
        if not token:
            continue
            
        found_box = None
        found_box_norm = None
        
        # 1. Match exact token
        for w in words_map:
            if w.get('text', '') == token:
                found_box = w.get('box')
                found_box_norm = w.get('box_norm')
                break
                
        # 2. Try matching substring using Thai visual character width ratio (ignoring combining vowels/tone marks)
        if not found_box:
            for w in words_map:
                w_text = w.get('text', '')
                if token in w_text:
                    found_box = w.get('box')
                    found_box_norm = w.get('box_norm')
                    if found_box_norm and len(w_text) > len(token):
                        try:
                            start_idx = w_text.find(token)
                            if start_idx >= 0:
                                total_v = max(1, _thai_visual_char_len(w_text))
                                start_v = _thai_visual_char_len(w_text[:start_idx])
                                tok_v = max(1, _thai_visual_char_len(token))
                                ratio_start = max(0.0, min(0.95, start_v / total_v))
                                ratio_end = max(ratio_start + 0.05, min(1.0, (start_v + tok_v) / total_v))
                                line_x0 = found_box_norm[0][0]
                                line_x1 = found_box_norm[1][0]
                                new_x0 = line_x0 + (line_x1 - line_x0) * ratio_start
                                new_x1 = line_x0 + (line_x1 - line_x0) * ratio_end
                                found_box_norm = [
                                    [new_x0, found_box_norm[0][1]],
                                    [new_x1, found_box_norm[1][1]],
                                    [new_x1, found_box_norm[2][1]],
                                    [new_x0, found_box_norm[3][1]]
                                ]
                                if found_box:
                                    bx0, bx1 = found_box[0][0], found_box[1][0]
                                    nbx0 = bx0 + (bx1 - bx0) * ratio_start
                                    nbx1 = bx0 + (bx1 - bx0) * ratio_end
                                    found_box = [
                                        [nbx0, found_box[0][1]],
                                        [nbx1, found_box[1][1]],
                                        [nbx1, found_box[2][1]],
                                        [nbx0, found_box[3][1]]
                                    ]
                        except Exception as e:
                            logger.warning(f"Word box estimation failed: {e}")
                    break

        # 3. Multi-word phrase match (e.g., "ไม่ผูกเที่ยวบิน / Manifest", "การ์ดดัง Doing")
        if not found_box and ' ' in token:
            parts = [p for p in token.split() if p]
            if len(parts) >= 2:
                first_p, last_p = parts[0], parts[-1]
                n_w = len(words_map)
                for idx_w in range(n_w):
                    w0_txt = words_map[idx_w].get('text', '')
                    if first_p in w0_txt:
                        end_idx = None
                        for j in range(idx_w, min(n_w, idx_w + len(parts) + 3)):
                            if last_p in words_map[j].get('text', ''):
                                end_idx = j
                                break
                        if end_idx is not None:
                            b0_norm = words_map[idx_w].get('box_norm')
                            b1_norm = words_map[end_idx].get('box_norm')
                            b0_abs = words_map[idx_w].get('box')
                            b1_abs = words_map[end_idx].get('box')
                            if b0_norm and b1_norm:
                                x0_n = b0_norm[0][0]
                                if len(w0_txt) > len(first_p):
                                    s_i = w0_txt.find(first_p)
                                    if s_i > 0:
                                        r_s = _thai_visual_char_len(w0_txt[:s_i]) / max(1, _thai_visual_char_len(w0_txt))
                                        x0_n = b0_norm[0][0] + (b0_norm[1][0] - b0_norm[0][0]) * r_s
                                x1_n = b1_norm[1][0]
                                y0_n = min(b0_norm[0][1], b1_norm[0][1])
                                y1_n = max(b0_norm[2][1], b1_norm[2][1])
                                found_box_norm = [
                                    [x0_n, y0_n],
                                    [x1_n, y0_n],
                                    [x1_n, y1_n],
                                    [x0_n, y1_n]
                                ]
                                if b0_abs and b1_abs:
                                    found_box = [
                                        [b0_abs[0][0], b0_abs[0][1]],
                                        [b1_abs[1][0], b0_abs[1][1]],
                                        [b1_abs[2][0], b1_abs[2][1]],
                                        [b0_abs[3][0], b1_abs[3][1]]
                                    ]
                                break
                    
        if found_box:
            err['box'] = found_box
            if found_box_norm:
                err['box_norm'] = found_box_norm
                
    return errors


@bp.route('/api/ocr', methods=['POST'])
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
        pages = ocr_pdf_bytes(pdf_bytes, dpi=dpi, lang=lang, filename=secure_filename(file.filename))
        
        return jsonify({
            'success': True,
            'filename': secure_filename(file.filename),
            'pages': pages,
            'total_pages': len(pages)
        })
    except Exception as e:
        logger.error(f"OCR Error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/spellcheck', methods=['POST'])
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
    lang = data.get('lang', 'tha+eng')
    words_map = data.get('words', [])

    try:
        # Run Multi-Agent Document Pipeline
        pipeline_state = run_document_pipeline(text, lang=lang)
        
        # Combine errors without duplicating identical position+token
        seen_pos = {(e.get('position'), e.get('token')) for e in pipeline_state.spell_errors}
        dedup_format_errors = [
            fe for fe in pipeline_state.format_errors
            if (fe.get('position'), fe.get('token')) not in seen_pos
        ]
        errors = pipeline_state.spell_errors + dedup_format_errors
        if not include_suggestions:
            for e in errors:
                e['suggestions'] = []
            
        # จับคู่กล่องข้อความ (หากไม่มี words_map หรือเป็นพิกัดแบบเก่า ให้คำนวณใหม่จากภาพแคชของหน้านั้น)
        session_id = secure_filename(str(data.get('session_id') or ''))
        page_num = int(data.get('page_number') or 0)
        if session_id and page_num > 0:
            try:
                from PIL import Image
                import ocr_engine
                img_path = CACHE_FOLDER / session_id / f"page_{page_num}.jpg"
                if img_path.exists():
                    with Image.open(str(img_path)) as pil_img:
                        words_map = ocr_engine._generate_fallback_words(text, pil_img.width, pil_img.height, pil_image=pil_img)
            except Exception as box_err:
                logger.warning(f"Could not regenerate visual boxes on spellcheck: {box_err}")
        if not words_map:
            import ocr_engine
            words_map = ocr_engine._generate_fallback_words(text, 2481, 3508)
        enrich_errors_with_boxes(errors, words_map)
            
        # Reconstruct result format for frontend compatibility
        spell_result = {
            'tokens': pipeline_state.tokens,
            'errors': errors,
            'summary': pipeline_state.summary,
            'final_review': pipeline_state.final_review_summary
        }
        
        summary = spell_result.get('summary', {})
        if summary:
            format_count = len(dedup_format_errors)
            summary['format_errors'] = format_count
            summary['error_count'] = summary.get('error_count', 0) + format_count
            
        return jsonify({
            'success': True,
            'result': spell_result
        })
    except Exception as e:
        logger.error(f"Spell check error: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/view/<session_id>/<int:page_num>')
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


@bp.route('/api/ocr/reprocess_page', methods=['POST'])
def reprocess_single_page():
    """
    สแกน OCR ซ้ำเฉพาะหน้าที่ต้องการจากไฟล์ภาพแคช (uploads/cache/<session_id>/page_<N>.jpg)
    เพื่อแก้ไขหน้าที่ข้อความเพี้ยนโดยไม่ต้องอัปโหลด PDF ใหม่ทั้งไฟล์
    """
    data = request.get_json(silent=True) or {}
    session_id = secure_filename(str(data.get('session_id') or ''))
    page_num = int(data.get('page_number') or 0)
    lang = data.get('lang', 'tha+eng')
    run_spell = bool(data.get('auto_spellcheck', False))

    if not session_id or page_num <= 0:
        return jsonify({'error': 'กรุณาระบุ session_id และหมายเลขหน้า (page_number)'}), 400

    img_path = CACHE_FOLDER / session_id / f"page_{page_num}.jpg"
    if not img_path.exists():
        return jsonify({'error': f'ไม่พบไฟล์ภาพต้นฉบับของหน้าที่ {page_num} ในแคช กรุณาอัปโหลดไฟล์เพื่อสแกนใหม่'}), 404

    try:
        from PIL import Image
        import ocr_engine
        from spell_checker import _tokenize_thai_and_english_counts

        with Image.open(str(img_path)) as pil_img:
            img_copy = pil_img.convert('RGB')
        ocr_res = ocr_engine.ocr_image(img_copy, lang=lang, filename=f"reprocess_p{page_num}.jpg")
        if ocr_res.get('error'):
            return jsonify({'error': ocr_res.get('error')}), 502
        text = ocr_res.get('text', '')
        words = ocr_res.get('words', [])

        page_obj = {
            'page_number': page_num,
            'session_id': session_id,
            'image_url': f"page_{page_num}.jpg",
            'text': text,
            'words': words,
            'width': ocr_res.get('width', img_copy.width),
            'height': ocr_res.get('height', img_copy.height),
        }

        if run_spell and text.strip():
            spell_result = spellcheck_text(text, include_suggestions=True, lang=lang)
            errors = list(spell_result.get('errors', []))
            try:
                fmt_errors = check_format_rules(text)
                seen_pos = {(e.get('position'), e.get('token')) for e in errors}
                dedup_fmt = [fe for fe in fmt_errors if (fe.get('position'), fe.get('token')) not in seen_pos]
                errors.extend(dedup_fmt)
            except Exception:
                dedup_fmt = []
            enrich_errors_with_boxes(errors, words)
            spell_result['errors'] = errors
            summary = spell_result.get('summary', {})
            if summary:
                summary['format_errors'] = len(dedup_fmt)
                summary['error_count'] = summary.get('error_count', 0) + len(dedup_fmt)
            page_obj['spell_check'] = spell_result
        else:
            th_cnt, en_cnt, _ = _tokenize_thai_and_english_counts(text)
            page_obj['spell_check'] = None
            page_obj['token_counts'] = {'thai_tokens': th_cnt, 'english_tokens': en_cnt}

        return jsonify({'success': True, 'page': page_obj})
    except Exception as e:
        logger.error(f"Reprocess page {page_num} error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/process', methods=['POST'])
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
        project_id = str(project_id)


    try:
        pdf_bytes = file.read()
        filename = secure_filename(file.filename)

        # OCR แต่ละหน้า
        pages = ocr_pdf_bytes(pdf_bytes, dpi=dpi, lang=lang, filename=filename)

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


@bp.route('/api/process_stream', methods=['POST'])
def process_stream():
    """
    รวม OCR + Spell Check ในรูปแบบ Stream (SSE)
    เพื่อรายงานความคืบหน้าทีละหน้า
    """
    if 'file' not in request.files:
        return jsonify({'error': 'ไม่พบไฟล์ กรุณาเลือกไฟล์ PDF'}), 400

    file = request.files['file']
    if not file or not file.filename or not allowed_file(file.filename):
        return jsonify({'error': 'รองรับเฉพาะไฟล์นามสกุล .pdf เท่านั้น'}), 400

    lang = request.args.get('lang', 'tha+eng')
    if lang not in ('tha+eng', 'tha', 'eng'):
        lang = 'tha+eng'
    try:
        dpi = max(72, min(600, int(request.args.get('dpi', 300))))
    except Exception:
        dpi = 300
    auto_spellcheck = request.args.get('auto_spellcheck', 'false').lower() == 'true'
    include_suggestions = request.args.get('include_suggestions', 'true').lower() == 'true'
    start_page = int(request.args.get('start_page', 1) or 1)
    end_page_val = request.args.get('end_page')
    end_page = int(end_page_val) if (end_page_val and end_page_val.isdigit() and int(end_page_val) > 0) else None
    
    pdf_bytes = file.read()
    if not pdf_bytes or not pdf_bytes.lstrip().startswith(b'%PDF-'):
        return jsonify({'error': 'ไฟล์ที่อัปโหลดไม่ใช่โครงสร้าง PDF ที่ถูกต้อง (%PDF header missing)'}), 400

    filename = secure_filename(file.filename) or 'document.pdf'

    # Opportunistic cleanup of preview cache folders older than 24 hours
    try:
        import shutil
        cutoff = time.time() - 86400
        for old_dir in CACHE_FOLDER.iterdir():
            if old_dir.is_dir() and old_dir.stat().st_mtime < cutoff:
                shutil.rmtree(old_dir, ignore_errors=True)
    except Exception:
        pass

    def generate():
        import json
        import time
        import uuid
        from PIL import Image
        import ocr_engine
        
        session_id = str(uuid.uuid4())
        session_dir = CACHE_FOLDER / session_id
        session_dir.mkdir(exist_ok=True)
        
        try:
            start_time = time.time()
            
            # Start event
            yield f"data: {json.dumps({'type': 'start', 'session_id': session_id, 'filename': filename})}\n\n"

            # Get total pages instantly using pdfinfo_from_bytes
            total_pages = 1
            try:
                from pdf2image.pdf2image import pdfinfo_from_bytes
                poppler_path = ocr_engine.POPPLER_PATH if (ocr_engine.POPPLER_PATH and os.path.exists(ocr_engine.POPPLER_PATH)) else None
                info = pdfinfo_from_bytes(pdf_bytes, poppler_path=poppler_path)
                total_pages = int(info.get("Pages", 1))
                logger.info(f"Instantly detected PDF page count: {total_pages} (poppler_path: {poppler_path})")
            except Exception as info_err:
                logger.error(f"Failed to get PDF info: {info_err}")

            effective_first = max(1, start_page)
            effective_last = min(total_pages, end_page) if end_page else total_pages
            pages_to_process = max(1, effective_last - effective_first + 1)

            # แจ้งความคืบหน้าเรื่องการโหลด Engine
            yield f"data: {json.dumps({'type': 'progress', 'page': 0, 'total': pages_to_process, 'total_doc_pages': total_pages, 'status': 'loading_engine', 'elapsed': 0})}\n\n"

            pages = []
            page_count = 0
            # OCR และ Spell Check ทีละหน้า (Streaming)
            for page, img in ocr_engine.ocr_pdf_bytes_generator(pdf_bytes, dpi=dpi, lang=lang, filename=filename, start_page=effective_first, end_page=effective_last):
                page_num = page['page_number']
                page_count += 1
                
                # Emit progress right after a page is OCR-ed and we start processing/spellchecking
                elapsed = time.time() - start_time
                yield f"data: {json.dumps({'type': 'progress', 'page': page_count, 'total': pages_to_process, 'total_doc_pages': total_pages, 'status': f'processing_page_{page_num}', 'elapsed': elapsed})}\n\n"

                # 1. บันทึกรูปใน Session Dir (เพื่อทำ Preview)
                if img is not None:
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
                else:
                    page['session_id'] = session_id

                # 2. ตรวจคำผิดและจัดรูปแบบ (ถ้าเปิดโหมด Auto)
                if auto_spellcheck and page.get('text'):
                    try:
                        spell_result = spellcheck_text(
                            page.get('text', ''),
                            include_suggestions=include_suggestions,
                            lang=lang
                        )
                        errors = list(spell_result.get('errors', []))
                        
                        # ตรวจสอบรูปแบบ (Format Rules) โดยไม่ซ้ำกับตำแหน่งคำผิดเดิม
                        try:
                            format_errors = check_format_rules(page.get('text', ''))
                            seen_pos = {(e.get('position'), e.get('token')) for e in errors}
                            dedup_fmt = [fe for fe in format_errors if (fe.get('position'), fe.get('token')) not in seen_pos]
                            errors.extend(dedup_fmt)
                        except Exception as fmt_err:
                            dedup_fmt = []
                            logger.error(f"Format check error in stream on page {page_num}: {fmt_err}")
                            
                        # จับคู่กล่องข้อความ
                        words_map = page.get('words', [])
                        enrich_errors_with_boxes(errors, words_map)
                        
                        spell_result['errors'] = errors
                        summary = spell_result.get('summary', {})
                        if summary:
                            format_count = len(dedup_fmt)
                            summary['format_errors'] = format_count
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
                                'semantic_errors': 0, 'format_errors': 0, 'error_rate': 0
                            }
                        }
                else:
                    # ข้ามการตรวจคำผิดด้วย AI แต่นับจำนวนคำไทยและอังกฤษด้วย PyThaiNLP เพื่อให้แสดงสถิติจำนวนคำได้ถูกต้อง
                    page['spell_check'] = None
                    try:
                        from spell_checker import _tokenize_thai_and_english_counts
                        th_cnt, en_cnt, _ = _tokenize_thai_and_english_counts(page.get('text', ''))
                        page['token_counts'] = {'thai_tokens': th_cnt, 'english_tokens': en_cnt}
                    except Exception:
                        page['token_counts'] = {'thai_tokens': 0, 'english_tokens': 0}
                
                pages.append(page)
                yield f"data: {json.dumps({'type': 'page_result', 'page': page})}\n\n"

            # เรียงหน้าให้ถูกต้อง
            pages.sort(key=lambda p: p['page_number'])

            # สรุปผลตอนท้ายครบทั้งภาษาไทย อังกฤษ บริบท และฟอร์แมต
            total_thai_tokens = sum(
                (p.get('spell_check') or {}).get('summary', {}).get('thai_tokens')
                or (p.get('token_counts') or {}).get('thai_tokens', 0)
                for p in pages
            )
            total_eng_tokens = sum(
                (p.get('spell_check') or {}).get('summary', {}).get('english_tokens')
                or (p.get('token_counts') or {}).get('english_tokens', 0)
                for p in pages
            )
            total_tokens = total_thai_tokens + total_eng_tokens
            total_errors = sum((p.get('spell_check') or {}).get('summary', {}).get('error_count', 0) for p in pages)
            
            final_data = {
                'type': 'complete',
                'filename': filename,
                'session_id': session_id,
                'total_pages': len(pages),
                'total_doc_pages': total_pages,
                'start_page': effective_first,
                'end_page': effective_last,
                'summary': {
                    'total_pages': len(pages),
                    'total_doc_pages': total_pages,
                    'total_thai_tokens': total_thai_tokens,
                    'total_english_tokens': total_eng_tokens,
                    'total_tokens': total_tokens,
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
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })


@bp.route('/api/dictionary/stats', methods=['GET'])
def dictionary_stats():
    """ดูสถิติ dictionary"""
    try:
        stats = get_dictionary_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/api/debug_env', methods=['GET'])
def debug_env():
    import os
    return jsonify({
        'key_exists': 'GOOGLE_API_KEY' in os.environ,
        'key_length': len(os.environ.get('GOOGLE_API_KEY', '')),
        'cwd': os.getcwd(),
        '__file__': __file__
    })


@bp.route('/api/dictionary/add', methods=['POST'])
def add_word():
    """เพิ่มคำใหม่ใน custom dictionary"""
    data = request.get_json(silent=True)
    if not data or 'word' not in data:
        return jsonify({'error': 'กรุณาส่ง JSON { "word": "..." }'}), 400

    word = str(data['word'] or '').strip()
    if not word:
        return jsonify({'error': 'คำว่างไม่สามารถเพิ่มได้'}), 400
    if len(word) > 100 or '\n' in word or '\r' in word:
        return jsonify({'error': 'คำศัพท์ต้องเป็นบรรทัดเดียวและยาวไม่เกิน 100 ตัวอักษร'}), 400

    success = add_custom_word(word)
    if success:
        return jsonify({'success': True, 'message': f'เพิ่มคำ "{word}" สำเร็จ', 'words': get_custom_words_list()})
    else:
        return jsonify({'error': 'เพิ่มคำไม่สำเร็จ'}), 500


@bp.route('/api/dictionary/remove', methods=['POST', 'DELETE'])
def remove_word():
    """ลบคำออกจาก custom dictionary"""
    data = request.get_json(silent=True) or {}
    word = str(data.get('word') or request.args.get('word') or '').strip()
    if not word:
        return jsonify({'error': 'กรุณาระบุคำศัพท์ที่ต้องการลบ'}), 400

    removed = remove_custom_word(word)
    if removed:
        return jsonify({'success': True, 'message': f'ลบคำ "{word}" เรียบร้อยแล้ว', 'words': get_custom_words_list()})
    return jsonify({'error': f'ไม่พบคำว่า "{word}" ในพจนานุกรม'}), 404


@bp.route('/api/dictionary/reload', methods=['POST'])
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


@bp.route('/api/ocr_history', methods=['GET', 'POST'])
def handle_ocr_history():
    from db_ingestion import get_ocr_history, save_ocr_history
    if request.method == 'GET':
        rows = get_ocr_history()
        return jsonify(rows)
    elif request.method == 'POST':
        data = request.json
        filename = data.get('filename', 'Unknown Document')
        result_json = data.get('result_json', {})
        result = save_ocr_history(filename, result_json)
        if result:
            return jsonify(result)
        return jsonify({'error': 'Failed to save'}), 500


@bp.route('/api/ocr_history/<history_id>', methods=['GET', 'DELETE'])
def handle_ocr_history_item(history_id):
    if request.method == 'GET':
        from db_ingestion import get_ocr_history_by_id
        item = get_ocr_history_by_id(history_id)
        if item:
            return jsonify(item)
        return jsonify({'error': 'Not found'}), 404
    elif request.method == 'DELETE':
        from db_ingestion import delete_ocr_history
        success = delete_ocr_history(history_id)
        if success:
            return jsonify({'success': True})
        return jsonify({'error': 'Failed to delete'}), 500

