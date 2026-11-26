"""
OCR Engine - แปลง PDF เป็นข้อความภาษาไทยด้วย Google Gemini Vision API
ใช้ google-genai SDK (ตัวใหม่) แทน google-generativeai ที่ถูก deprecated แล้ว
"""
import os
import io
import time
import base64
import logging
import tempfile
import re
from PIL import Image
from pdf2image import convert_from_path, convert_from_bytes
from dotenv import load_dotenv

from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

logger = logging.getLogger(__name__)

# Global engine instance version
VERSION = "3.0.0-gemini"

# Load .env locally to ensure variables are available
load_dotenv()

def _resolve_poppler_path():
    raw = os.environ.get('POPPLER_PATH', '').strip().strip('"')
    if raw and os.path.exists(raw):
        if os.path.isdir(raw):
            return os.path.normpath(raw)
        elif os.path.isfile(raw):
            return os.path.normpath(os.path.dirname(raw))
    
    # Check recursively in C:\poppler if it exists
    if os.path.exists(r'C:\poppler'):
        for root, dirs, files in os.walk(r'C:\poppler'):
            if 'pdftoppm.exe' in files or 'pdftoppm' in files:
                return os.path.normpath(root)
                
    candidates = [
        r'C:\poppler\poppler-25.12.0\Library\bin',
        r'C:\poppler\Library\bin',
        r'C:\poppler\bin',
    ]
    for c in candidates:
        if os.path.exists(c):
            return os.path.normpath(c)
            
    return os.path.normpath(r'C:\poppler\Library\bin')

POPPLER_PATH = _resolve_poppler_path()

logger.info(f"Using POPPLER_PATH: {POPPLER_PATH}")

if os.path.exists(POPPLER_PATH):
    logger.info(f"POPPLER_PATH exists: {POPPLER_PATH}")
    if POPPLER_PATH not in os.environ['PATH']:
        os.environ['PATH'] = POPPLER_PATH + os.pathsep + os.environ['PATH']
        logger.info("Added POPPLER_PATH to system PATH")
else:
    logger.warning(f"POPPLER_PATH does not exist: {POPPLER_PATH}")


def _has_repetition_runaway(text: str) -> bool:
    """ตรวจจับกรณีโมเดล LLM ติดลูปพิมพ์จุด (......) หรือขีด (------) ยาวผิดปกติจนข้อความในหน้าถูกตัดจบ"""
    if not text:
        return False
    return bool(re.search(r"(\.|_|-|=|\s)\1{75,}", text))


def _sanitize_ocr_markdown(text: str) -> str:
    """
    ทำความสะอาดข้อความ Markdown ที่ได้จาก OCR:
    1) ย่อจุดไข่ปลา/เส้นประในหน้าสารบัญ (.....) ให้เหลือเพียง ' ... '
    2) ย่อเส้นขีดแบ่งตาราง Markdown (| :---------- |) ให้เป็น '| --- |' มาตรฐาน
    3) ย่อเส้นช่องว่างสำหรับกรอกข้อมูล (__________) ให้เหลือ '_____'
    """
    if not text:
        return ""
    cleaned_lines = []
    for line in text.split('\n'):
        stripped = line.strip()
        # กรณีเป็นแถวขีดคั่นหัวตาราง Markdown เช่น | :------- | :------- |
        if stripped.startswith('|') and re.match(r'^[|:\s-]+$', stripped) and '-' in stripped:
            cells = stripped.strip('|').split('|')
            norm_cells = []
            for c in cells:
                c_str = c.strip()
                if c_str.startswith(':') and c_str.endswith(':'):
                    norm_cells.append(':---:')
                elif c_str.startswith(':'):
                    norm_cells.append(':---')
                elif c_str.endswith(':'):
                    norm_cells.append('---:')
                else:
                    norm_cells.append('---')
            cleaned_lines.append('| ' + ' | '.join(norm_cells) + ' |')
            continue

        # กรณีเป็นเส้นคั่นแนวนอนล้วนๆ (Horizontal Rule)
        if re.match(r'^[-=_]{5,}$', stripped):
            cleaned_lines.append('---')
            continue

        # ย่อจุดนำสายตาในสารบัญ (Table of Contents dot leaders) เช่น '1. บทนำ ................... 6' -> '1. บทนำ ... 6'
        line = re.sub(r'(?:\.\s*){4,}\.', ' ... ', line)
        line = re.sub(r'…{3,}', ' ... ', line)
        # ย่อขีดกลางหรือขีดเส้นใต้ที่ซ้ำกันยาวเกินไปในบรรทัด
        line = re.sub(r'-{6,}', '---', line)
        line = re.sub(r'_{6,}', '_____', line)
        cleaned_lines.append(line)

    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{4,}', '\n\n\n', result)
    return result.strip()


def _apply_it_keyword_correction(text: str) -> str:
    """
    ใช้ไฟล์ data/user_words.txt เพื่อแก้ไขคำศัพท์ IT ที่อาจจะอ่านเพี้ยนเล็กน้อย
    """
    user_words_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'user_words.txt')
    if not os.path.exists(user_words_path):
        return text
        
    with open(user_words_path, 'r', encoding='utf-8') as f:
        known_words = [line.strip() for line in f if len(line.strip()) > 2]
    
    if not known_words:
        return text
        
    modified_text = text
    for word in known_words:
        if word.isupper() and len(word) <= 5:
            pattern = ' '.join(list(word))
            modified_text = re.sub(r'\b' + re.escape(pattern) + r'\b', word, modified_text)
            
    return modified_text


def _generate_fallback_words(text: str, width: int, height: int) -> list:
    """
    สร้าง Bounding Box จำลองสำหรับแต่ละคำในกรณีที่ API ไม่ได้คืนค่า Box มาให้
    เพื่อให้ระบบ Highlight คำผิดในหน้า Frontend ยังพอทำงานได้คร่าวๆ
    """
    words = []
    lines = text.split('\n')
    num_lines = max(len(lines), 1)
    y_step = 1.0 / num_lines
    
    for idx, line in enumerate(lines):
        # ข้ามบรรทัดแบ่งหัวตาราง markdown เช่น |---|---|
        if re.match(r'^[|:\s-]+$', line.strip()):
            continue
        line_words = [w for w in line.split() if w not in ('|', '||')]
        if not line_words:
            continue
        num_words = len(line_words)
        x_step = 1.0 / num_words
        
        for w_idx, w in enumerate(line_words):
            # Normalize coordinates (0..1)
            nx0, ny0 = w_idx * x_step, idx * y_step
            nx1, ny1 = (w_idx + 1) * x_step, idx * y_step
            nx2, ny2 = (w_idx + 1) * x_step, (idx + 1) * y_step
            nx3, ny3 = w_idx * x_step, (idx + 1) * y_step
            
            # Absolute coordinates
            x0, y0 = nx0 * width, ny0 * height
            x1, y1 = nx1 * width, ny1 * height
            x2, y2 = nx2 * width, ny2 * height
            x3, y3 = nx3 * width, ny3 * height
            
            words.append({
                'text': w,
                'box': [[x0, y0], [x1, y1], [x2, y2], [x3, y3]],
                'box_norm': [[nx0, ny0], [nx1, ny1], [nx2, ny2], [nx3, ny3]]
            })
    return words


_env_mtime_snapshot = {}

def _refresh_api_keys_from_env_files() -> str:
    """
    ตรวจสอบทั้ง backend/.env และ root .env โดยเลือกใช้ค่าจากไฟล์ที่ถูกแก้ไขล่าสุด (latest mtime)
    เพื่อให้เมื่อผู้ใช้แก้ GOOGLE_API_KEY ในไฟล์ใดไฟล์หนึ่งแล้วกด Save ระบบนำคีย์ใหม่ไปใช้ได้ทันทีโดยไม่ต้อง Restart
    """
    global _env_mtime_snapshot
    from pathlib import Path
    backend_env = Path(__file__).resolve().parent / '.env'
    root_env = Path(__file__).resolve().parent.parent / '.env'
    candidates = [p for p in (backend_env, root_env) if p.exists()]
    if not candidates:
        return os.environ.get('GOOGLE_API_KEY', '') or os.environ.get('GOOGLE_API_KEYS', '')

    # Sort newest-modified .env first so whichever file the user just edited wins
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    changed = False
    for p in candidates:
        mt = p.stat().st_mtime
        if _env_mtime_snapshot.get(str(p)) != mt:
            _env_mtime_snapshot[str(p)] = mt
            changed = True

    for p in candidates:
        try:
            with open(p, 'r', encoding='utf-8') as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if line.startswith('GOOGLE_API_KEY=') or line.startswith('GOOGLE_API_KEYS=') or line.startswith('GEMINI_API_KEY='):
                        val = line.split('=', 1)[1].strip().strip('"').strip("'")
                        if val:
                            if changed:
                                os.environ['GOOGLE_API_KEY'] = val
                            return val
        except Exception:
            continue

    return os.environ.get('GOOGLE_API_KEY', '') or os.environ.get('GOOGLE_API_KEYS', '')


def get_all_api_keys() -> list[str]:
    """
    อ่าน API Keys ทั้งหมดจาก GOOGLE_API_KEY หรือ GOOGLE_API_KEYS (รองรับ Hot-Reload จาก .env ล่าสุด)
    สามารถใส่หลายคีย์คั่นด้วยเครื่องหมายจุลภาค (,) เช่น Key1,Key2
    """
    raw = _refresh_api_keys_from_env_files()
    keys = [k.strip().strip('"').strip("'") for k in raw.split(',') if k.strip()]
    return keys if keys else []


_gemini_clients_cache = {}

def _get_gemini_client(key_index: int = 0):
    """
    สร้าง Gemini client จาก google-genai SDK (ตัวใหม่) รองรับการเลือก Key Index
    และแคชตามค่า api_key จริง เพื่อให้เปลี่ยนคีย์ใน .env แล้วสลับ Client ใหม่ได้ทันที
    """
    global _gemini_clients_cache
    try:
        from google import genai
        keys = get_all_api_keys()
        if not keys:
            raise ValueError("ไม่พบ GOOGLE_API_KEY ใน environment variables กรุณาตั้งค่าใน .env")
        idx = key_index % len(keys)
        active_key = keys[idx]

        if active_key not in _gemini_clients_cache:
            _gemini_clients_cache[active_key] = genai.Client(api_key=active_key)

        return _gemini_clients_cache[active_key]
    except ImportError:
        raise ImportError(
            "ไม่พบ library 'google-genai' กรุณารัน: pip install google-genai"
        )


def ocr_image(pil_image: Image.Image, lang: str = 'tha+eng', filename: str = None) -> dict:
    """
    สกัดข้อความจากรูปภาพโดยใช้ Google Gemini Vision API (google-genai SDK)
    คืนค่าเป็น Dict: { 'text': str, 'words': list }
    """
    model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
    if '3.1' in model_name:
        model_name = 'gemini-2.5-flash'
    w, h = pil_image.size

    lang_hint = {
        'tha': "Focus primarily on Thai script (ภาษาไทย) and numbers/symbols, ensuring exact Thai vowel and tone-mark ordering.",
        'eng': "Focus primarily on English text, technical identifiers, and numbers/symbols.",
    }.get(lang, "Focus on both Thai (ภาษาไทย) and English text, ensuring exact Thai vowel/tone-mark ordering and accurate English transcription.")

    # ปรับปรุง System Prompt ให้เก็บเนื้อหาครบถ้วน รองรับตารางแบบ Markdown และป้องกันอาการติดลูปจุดสารบัญ/เส้นตาราง
    system_prompt = (
        "You are an expert OCR transcription assistant specializing in Thai and English documents, forms, technical cards, diagrams, and spreadsheets.\n"
        f"{lang_hint}\n"
        "Transcribe ALL content from the image accurately, completely, and faithfully without omitting any rows, columns, or text blocks.\n"
        "- CRITICAL ANTI-LOOP RULE: NEVER output long runs of repeated characters such as dots (......), hyphens (------), underscores (______), or spaces.\n"
        "- For Table of Contents (สารบัญ), index entries, or leader lines with dots (.....), ALWAYS replace the entire dotted leader between the heading and the page number with a single ' ... ' (maximum 3 dots, e.g., '1. บทนำ ... 6').\n"
        "- For signature lines or fill-in form blanks, use at most 5 underscores ('_____').\n"
        "- If the image contains a table or spreadsheet, transcribe it strictly as a standard Markdown table (| Col 1 | Col 2 | ...) with a COMPACT header separator row using exactly 3 hyphens per column (| --- | --- |). NEVER pad table cells or separator rows with long hyphen strings.\n"
        "- If the image contains a flowchart or process diagram, transcribe or convert it into a Mermaid.js diagram inside a ```mermaid ... ``` code block, preserving steps and conditions accurately.\n"
        "- Preserve original typos, grammar, dates, numbers, IDs, URLs, and punctuation exactly as shown so downstream proofreading can audit them.\n"
        "- Do NOT truncate, summarize, or skip content. Transcribe all rows from top to bottom completely.\n"
        "- Do NOT hallucinate or loop repeating phrases."
    )
    user_prompt = (
        "Transcribe all text from this image completely and accurately from top to bottom. "
        "If this is a Table of Contents (สารบัญ), use ' ... ' (only 3 dots) before each page number instead of long dotted lines. "
        "If there are tables, use compact '| --- | --- |' Markdown table separators."
    )

    try:
        from google.genai import types

        keys = get_all_api_keys()
        clients = [_get_gemini_client(i) for i in range(len(keys))] if keys else [_get_gemini_client()]
        logger.info(f"Calling Gemini API ({model_name}) with {len(clients)} available API keys...")

        # --- Image Optimization ---
        # รองรับเอกสารขนาดใหญ่ (เช่น A3, Spreadsheets ตารางกว้าง, ภาพความละเอียดสูง)
        # โดยไม่บีบอัดลงมาจนตัวหนังสือเล็กๆ เบลอ (ค่าเดิม 1600 บีบจนตัวหนังสือไทยขนาดเล็กอ่านไม่ออก)
        img_to_send = pil_image
        max_dim = int(os.environ.get('OCR_MAX_DIM', 3200))
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            new_w, new_h = int(w * ratio), int(h * ratio)
            img_to_send = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            logger.info(f"Resized image from {w}x{h} to {new_w}x{new_h} (max_dim={max_dim}).")

        # แปลง PIL Image เป็น bytes คุณภาพสูง
        img_buffer = io.BytesIO()
        img_to_send.save(img_buffer, format='JPEG', quality=90)
        img_bytes = img_buffer.getvalue()
        # -----------------------------------------

        max_retries = 2
        raw_fallback_models = [model_name, 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
        # Remove duplicate models while preserving order
        seen = set()
        fallback_models = [m for m in raw_fallback_models if not (m in seen or seen.add(m))]
        
        success = False
        last_error = None
        response = None

        for client_idx, client in enumerate(clients):
            for current_model in fallback_models:
                for attempt in range(max_retries):
                    try:
                        logger.info(f"Calling Gemini API [Key #{client_idx+1}/{len(clients)}] model: {current_model} (Attempt {attempt+1})")
                        response = client.models.generate_content(
                            model=current_model,
                            contents=[
                                types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'),
                                user_prompt,
                            ],
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                temperature=0.1,
                                max_output_tokens=8192,
                            )
                        )
                        success = True
                        break  # Success, break retry loop
                    except Exception as e:
                        last_error = e
                        error_msg = str(e)
                        if 'developer instruction is not enabled' in error_msg.lower():
                            logger.warning(f"API rejected system_instruction for {current_model}; retrying with inline prompt.")
                            try:
                                response = client.models.generate_content(
                                    model=current_model,
                                    contents=[
                                        types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'),
                                        f"{system_prompt}\n\n{user_prompt}",
                                    ],
                                    config=types.GenerateContentConfig(
                                        temperature=0.1,
                                        max_output_tokens=8192,
                                    )
                                )
                                success = True
                                break
                            except Exception as inline_err:
                                last_error = inline_err
                                logger.error(f"Inline prompt retry failed for {current_model}: {inline_err}")
                                break
                        elif '404' in error_msg or 'NOT_FOUND' in error_msg or 'not found' in error_msg.lower():
                            logger.warning(f"Model {current_model} is not supported or not found (404). Switching to fallback model.")
                            break # Break retry loop, go to next model in fallback_models
                        elif '503' in error_msg or 'UNAVAILABLE' in error_msg:
                            logger.warning(f"Model {current_model} is overloaded (503). Switching to fallback model.")
                            break # Break retry loop, go to next model in fallback_models
                        elif '429' in error_msg or 'Quota' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                            if attempt < max_retries - 1:
                                delay = (attempt + 1) * 2
                                logger.warning(f"Rate limit exceeded (429) for Key #{client_idx+1} {current_model}. Retrying in {delay}s...")
                                time.sleep(delay)
                                continue
                            else:
                                logger.warning(f"Rate limit exhausted for Key #{client_idx+1} {current_model}. Switching model/key.")
                                break
                        else:
                            # For other errors, log and try next model
                            logger.error(f"Error with Key #{client_idx+1} {current_model}: {error_msg}")
                            break
                
                if success:
                    break # Success, break model fallback loop
            if success:
                break # Success, break API key loop

        if not success and last_error:
            error_msg = str(last_error)
            if '429' in error_msg or 'Quota' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                primary_model = fallback_models[0]
                logger.warning(f"All fallback models hit 429 rate limit. Waiting 6s for API quota window to reset, then final retry with {primary_model}...")
                time.sleep(6)
                try:
                    response = client.models.generate_content(
                        model=primary_model,
                        contents=[
                            types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'),
                            user_prompt,
                        ],
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.1,
                            max_output_tokens=8192,
                        )
                    )
                    success = True
                except Exception as final_e:
                    last_error = final_e

        if not success and last_error:
            raise last_error

        logger.info("Gemini API call successful.")
        
        # Log API usage
        if response and hasattr(response, 'usage_metadata'):
            try:
                from db_ingestion import log_api_usage
                used_model = getattr(response, 'model_version', None) or current_model or 'gemini-2.5-flash'
                log_api_usage("OCR_Scan", used_model, response.usage_metadata, filename=filename)
            except Exception as usage_err:
                logger.error(f"Failed to log API usage: {usage_err}")

        # ดึงข้อความจาก response
        text = ""
        if response.text:
            text = response.text
        else:
            finish = response.candidates[0].finish_reason if response.candidates else 'unknown'
            logger.warning(f"Gemini returned no text. Finish reason: {finish}")
            text = ""

        # ตรวจสอบว่าโมเดลติดลูปพิมพ์จุด (......) หรือขีด (------) จนข้อความในหน้าถูกตัดจบหรือไม่
        if _has_repetition_runaway(text):
            logger.warning("Detected character repetition runaway in OCR output! Retrying page with strict anti-loop recovery prompt...")
            recovery_prompt = (
                f"{system_prompt}\n\n"
                "STRICT OVERRIDE: Your previous attempt got stuck in a character repetition loop (repeating '.' or '-').\n"
                "1. NEVER repeat '.' more than 3 times (' ... '). In a Table of Contents (สารบัญ), write each line simply as: 'Heading ... PageNumber'.\n"
                "2. NEVER repeat '-' more than 3 times ('---') in Markdown table separator rows ('| --- | --- |').\n"
                "3. Transcribe EVERY line and row on this page completely from top to bottom."
            )
            try:
                retry_resp = clients[0].models.generate_content(
                    model=fallback_models[0],
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type='image/jpeg'),
                        recovery_prompt,
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.35,
                        max_output_tokens=8192,
                    )
                )
                if retry_resp and retry_resp.text:
                    text = retry_resp.text
                    logger.info("Anti-loop OCR retry succeeded.")
            except Exception as retry_err:
                logger.warning(f"Anti-loop OCR retry failed ({retry_err}); sanitizing initial output.")

        # อนุญาตให้มี Markdown code block (เช่น ```mermaid) เพื่อเก็บโครงสร้าง Flowchart
        text = _sanitize_ocr_markdown(_normalize_thai_pdf_text(text.strip()))

        # Post-processing
        text = _apply_it_keyword_correction(text)

        # Generate visual bounding boxes aligned to actual ink bands on the page image
        words = _generate_fallback_words(text, w, h, pil_image=pil_image)

        return {
            'text': text,
            'words': words,
            'width': w,
            'height': h
        }

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"OCR Error: {e}\n{tb}")
        err_msg = str(e)
        if '429' in err_msg or 'RESOURCE_EXHAUSTED' in err_msg:
            err_msg = "ข้อผิดพลาด 429: โควต้า API ของ Gemini สำหรับ Free Tier เต็ม หรือส่งคำขอถี่เกินไป กรุณารอสักครู่ (ประมาณ 1 นาที) แล้วกดแสกนใหม่อีกครั้ง"
        return {'text': f"❌ {err_msg}", 'words': [], 'error': err_msg}


def ocr_pdf_file(pdf_path: str, dpi: int = 150, lang: str = 'tha+eng', progress_callback=None, filename: str = None) -> list[dict]:
    """
    สกัดข้อความจาก PDF file
    """
    start_time = time.time()
    try:
        poppler_path = POPPLER_PATH if os.path.exists(POPPLER_PATH) else None
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            poppler_path=poppler_path
        )
    except Exception as e:
        raise RuntimeError(f"ไม่สามารถแปลง PDF ได้: {str(e)}")

    total_pages = len(images)
    results = []
    
    for i, image in enumerate(images):
        page_num = i + 1
        page_start = time.time()
        
        if progress_callback:
            progress_callback(page_num, total_pages, "extracting", time.time() - start_time)

        try:
            text_result = ocr_image(image, lang=lang, filename=filename or os.path.basename(pdf_path))
            results.append({
                'page_number': page_num,
                'text': text_result.get('text', ''),
                'words': text_result.get('words', []),
                'total_pages': total_pages,
                'time_taken': round(time.time() - page_start, 2)
            })
        except Exception as e:
            results.append({
                'page_number': page_num,
                'text': '',
                'error': str(e),
                'total_pages': total_pages,
                'time_taken': round(time.time() - page_start, 2)
            })

        # หน่วงเวลา 4 วินาทีระหว่างหน้า เพื่อป้องกัน Rate Limit (15 RPM) สำหรับ Free Tier API
        if i < total_pages - 1:
            time.sleep(4)

    return results


def _normalize_thai_pdf_text(text: str) -> str:
    """แปลงสระอำแบบแยก (นิคหิต + สระอา) เป็นสระอำมาตรฐาน"""
    if not text:
        return ""
    return text.replace("\u0e4d\u0e32", "\u0e33")


def _count_thai_pdf_glitches(text: str) -> int:
    """
    ตรวจจับอาการสระ/วรรณยุกต์ภาษาไทยสลับตำแหน่งหรือแตกเว้นวรรคจากการดึง text ตรงของ PDF
    (เช่น 'รห ัส', 'ข ้อมูล', 'สนิ คา้', 'เวอร์ช นั 1.1', 'ผรุ้ับ', 'ใ นไฟล์')
    """
    if not text:
        return 0
    glitches = 0
    # 1) เว้นวรรคนำหน้าสระบน/ล่าง หรือวรรณยุกต์ (ในภาษาไทยไม่มีทางเกิด)
    glitches += len(re.findall(r"[ \t]+[\u0e31\u0e34-\u0e3a\u0e47-\u0e4e]", text))
    # 2) วรรณยุกต์ไปเกาะหลังสระอา เช่น 'คา้', 'หนา้'
    glitches += len(re.findall(r"\u0e32[\u0e48-\u0e4c]", text))
    # 3) สระบน/ล่าง + วรรณยุกต์ + สระบน/ล่าง ซ้อนกัน เช่น 'ผรุ้ับ'
    glitches += len(re.findall(r"[\u0e31\u0e34-\u0e3a][\u0e48-\u0e4c][\u0e31\u0e34-\u0e3a]", text))
    # 4) ไม้หันอากาศ (ั) อยู่ท้ายคำติดเว้นวรรค/ตัวเลข/เครื่องหมาย เช่น 'เวอร์ช นั 1.1'
    glitches += len(re.findall(r"\u0e31(?:\s|$|[0-9.,;:!?()\[\]/])", text))
    # 5) สระหน้า (เ แ โ ใ ไ) ตามด้วยเว้นวรรคแล้วค่อยตามด้วยพยัญชนะ เช่น 'ใ นไฟล์'
    glitches += len(re.findall(r"[\u0e40-\u0e44][ \t]+[\u0e01-\u0e2e]", text))
    return glitches


def _is_native_pdf_text_usable(text: str) -> bool:
    """
    ตรวจสอบว่าข้อความที่ดึงตรงจาก PDF (Embedded Text) อ่านรู้เรื่องและสระภาษาไทยเรียงถูกต้องหรือไม่
    หากเป็นหน้าสแกน ฟอนต์เพี้ยน หรือสระภาษาไทยสลับตำแหน่ง จะคืน False เพื่อส่งทำ Gemini Vision OCR
    """
    if not text:
        return False
    norm = _normalize_thai_pdf_text(text)
    compact = "".join(norm.split())
    if len(compact) < 60:
        return False
    garbled = sum(1 for ch in compact if ch == "\ufffd" or ("\ue000" <= ch <= "\uf8ff"))
    if (garbled / len(compact)) > 0.05:
        return False
    if _count_thai_pdf_glitches(norm) >= 2:
        return False
    readable = sum(
        1 for ch in compact
        if ("\u0e00" <= ch <= "\u0e7f") or ch.isalnum()
    )
    return (readable / len(compact)) >= 0.45


def _extract_pages_with_pdftotext(pdf_bytes: bytes) -> list[str] | None:
    """ลองใช้ Poppler pdftotext ดึงข้อความแยกหน้าด้วย form-feed (\f) เผื่อบางไฟล์เรียงสระไทยดีกว่า PDFium"""
    import shutil
    import subprocess
    import tempfile

    pdftotext_bin = shutil.which("pdftotext")
    if not pdftotext_bin and os.path.exists(POPPLER_PATH):
        cand = os.path.join(POPPLER_PATH, "pdftotext.exe")
        if os.path.exists(cand):
            pdftotext_bin = cand
    if not pdftotext_bin:
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tf:
            tf.write(pdf_bytes)
            tmp_path = tf.name
        proc = subprocess.run(
            [pdftotext_bin, "-enc", "UTF-8", tmp_path, "-"],
            capture_output=True,
            timeout=25
        )
        if proc.returncode != 0:
            return None
        raw = proc.stdout.decode("utf-8", errors="replace")
        pages = raw.split("\f")
        if pages and not pages[-1].strip():
            pages = pages[:-1]
        return pages
    except Exception as e:
        logger.debug(f"pdftotext extraction skipped: {e}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def ocr_images_batch(batch_items: list[tuple[int, Image.Image]], lang: str = 'tha+eng', filename: str = None) -> dict[int, str]:
    """
    ส่งรูปภาพหลายหน้า (เช่น 3-4 หน้า) ใน 1 Gemini Vision API request เพื่อความเร็วสูงและลดจำนวน API call
    คืนค่า dict[page_number -> extracted_text]
    """
    if not batch_items:
        return {}
    if len(batch_items) == 1:
        p_num, p_img = batch_items[0]
        res = ocr_image(p_img, lang=lang, filename=filename)
        return {p_num: res.get('text', '')}

    from google.genai import types

    model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
    max_dim = int(os.environ.get('OCR_BATCH_MAX_DIM', 2000))
    page_nums = [p_num for p_num, _ in batch_items]

    contents = []
    for p_num, pil_img in batch_items:
        img_to_send = pil_img.convert("RGB")
        w, h = img_to_send.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            img_to_send = img_to_send.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img_to_send.save(buf, format='JPEG', quality=86)
        contents.append(f"Image for PAGE {p_num}:")
        contents.append(types.Part.from_bytes(data=buf.getvalue(), mime_type='image/jpeg'))

    markers_hint = ", ".join([f"=== [PAGE {p}] ===" for p in page_nums])
    prompt = (
        "You are an expert Thai & English OCR transcription assistant.\n"
        f"Transcribe ALL text from each of the {len(batch_items)} document page images above accurately, completely, and with PERFECT Thai vowel and tone-mark ordering.\n"
        f"You MUST separate each page strictly using these exact headers on their own lines: {markers_hint}\n"
        "- CRITICAL ANTI-LOOP RULE: NEVER output long runs of repeated dots (......) or hyphens (------).\n"
        "- For Table of Contents (สารบัญ) or dotted leader lines, replace the dots with a single ' ... ' (3 dots max, e.g., '1. บทนำ ... 6').\n"
        "- Preserve tables as standard Markdown tables with compact '| --- | --- |' separator rows.\n"
        "- Preserve original dates, numbers, IDs, and spelling faithfully. Do NOT summarize or omit any page.\n"
        "- Output ONLY the page headers and transcribed content."
    )
    contents.append(prompt)

    keys = get_all_api_keys()
    clients = [_get_gemini_client(i) for i in range(len(keys))] if keys else [_get_gemini_client()]
    raw_fallback_models = [model_name, 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
    seen = set()
    fallback_models = [m for m in raw_fallback_models if not (m in seen or seen.add(m))]

    response = None
    last_error = None
    for client in clients:
        for current_model in fallback_models:
            try:
                response = client.models.generate_content(
                    model=current_model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=16384,
                    )
                )
                break
            except Exception as e:
                last_error = e
                if '429' in str(e) or 'RESOURCE_EXHAUSTED' in str(e):
                    time.sleep(2)
                continue
        if response is not None:
            break

    if response is None or not getattr(response, 'text', None):
        logger.warning(f"Batch Vision OCR failed for pages {page_nums} ({last_error}); falling back to single-page OCR.")
        fallback_out = {}
        for p_num, p_img in batch_items:
            res = ocr_image(p_img, lang=lang, filename=filename)
            fallback_out[p_num] = res.get('text', '')
        return fallback_out

    try:
        if hasattr(response, 'usage_metadata'):
            from db_ingestion import log_api_usage
            used_model = getattr(response, 'model_version', None) or model_name
            log_api_usage("OCR_Scan_Batch", used_model, response.usage_metadata, filename=filename)
    except Exception:
        pass

    raw_text = response.text.strip()
    parsed = {}
    matches = list(re.finditer(r"===\s*\[PAGE\s+(\d+)\]\s*===", raw_text, flags=re.IGNORECASE))
    for idx_m, m in enumerate(matches):
        p_num = int(m.group(1))
        start_pos = m.end()
        end_pos = matches[idx_m + 1].start() if idx_m + 1 < len(matches) else len(raw_text)
        raw_page_slice = raw_text[start_pos:end_pos].strip()
        if _has_repetition_runaway(raw_page_slice):
            logger.warning(f"Batch page {p_num} had repetition runaway; will re-run single-page OCR.")
            continue
        page_txt = _apply_it_keyword_correction(_sanitize_ocr_markdown(_normalize_thai_pdf_text(raw_page_slice)))
        parsed[p_num] = page_txt

    # หากหน้าใดไม่ถูกแยกออกมาครบ ให้ fallback ยิงเดี่ยวเฉพาะหน้านั้น
    for p_num, p_img in batch_items:
        if p_num not in parsed or not parsed[p_num].strip():
            res = ocr_image(p_img, lang=lang, filename=filename)
            parsed[p_num] = res.get('text', '')

    return parsed


def ocr_pdf_bytes(
    pdf_bytes: bytes,
    dpi: int = 150,
    lang: str = 'tha+eng',
    progress_callback=None,
    filename: str = None,
    save_images_dir: str = None,
    prefer_native_text: bool = False,
    max_workers: int = 3
) -> list[dict]:
    """
    สกัดข้อความจาก PDF bytes
    - หากระบุ save_images_dir จะบันทึกภาพหน้าเอกสาร (page_N.jpg) ไว้สำหรับแสดงใน Document Inspector
    - หาก prefer_native_text=True จะดึง Embedded Text ด้วย pypdfium2 ก่อน (เร็วกว่า ~50x สำหรับ PDF ดิจิทัล)
      และส่งเฉพาะหน้าสแกน/หน้ารูปภาพไปทำ Gemini Vision OCR แบบขนาน (ThreadPoolExecutor)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    start_time = time.time()
    if save_images_dir:
        try:
            os.makedirs(save_images_dir, exist_ok=True)
        except Exception as dir_err:
            logger.warning(f"Could not create save_images_dir {save_images_dir}: {dir_err}")
            save_images_dir = None

    def _save_preview(pil_img: Image.Image, page_num: int) -> bool:
        if not save_images_dir or pil_img is None:
            return False
        try:
            preview_img = pil_img.convert("RGB")
            if preview_img.width > 1400:
                ratio = 1400 / float(preview_img.width)
                preview_img = preview_img.resize((1400, int(preview_img.height * ratio)), Image.Resampling.LANCZOS)
            preview_img.save(os.path.join(save_images_dir, f"page_{page_num}.jpg"), "JPEG", quality=82)
            return True
        except Exception as save_err:
            logger.warning(f"Could not save preview image for page {page_num}: {save_err}")
            return False

    # ── Fast Hybrid Path via pypdfium2 (Native Text + On-demand Vision OCR) ──
    if prefer_native_text:
        try:
            import pypdfium2 as pdfium

            pdf_doc = pdfium.PdfDocument(pdf_bytes)
            total_pages = len(pdf_doc)
            pdftotext_pages = _extract_pages_with_pdftotext(pdf_bytes)
            results_by_page = {}
            vision_queue = []  # (page_num, pil_image, saved_image)
            completed_count = 0
            render_scale = max(1.0, float(dpi) / 72.0)

            for i in range(total_pages):
                page_num = i + 1
                page_start = time.time()
                page = pdf_doc[i]
                native_text = ""
                # ลองใช้ pdftotext ก่อนถ้ามีและจำนวนหน้าตรงกัน (บางไฟล์เรียงสระไทยดีกว่า PDFium)
                if pdftotext_pages and len(pdftotext_pages) == total_pages:
                    cand_pt = _normalize_thai_pdf_text((pdftotext_pages[i] or "").strip())
                    if _is_native_pdf_text_usable(cand_pt):
                        native_text = cand_pt
                if not native_text:
                    try:
                        textpage = page.get_textpage()
                        try:
                            native_text = _normalize_thai_pdf_text((textpage.get_text_range() or "").strip())
                        finally:
                            textpage.close()
                    except Exception as tp_err:
                        logger.debug(f"pypdfium2 text extract failed on page {page_num}: {tp_err}")

                usable_native = _is_native_pdf_text_usable(native_text)
                pil_img = None
                saved_image = False
                if save_images_dir or not usable_native:
                    try:
                        # สำหรับหน้าที่มี native text ใช้ scale 1.5 เพื่อสร้าง preview เร็ว; หน้าสแกนใช้ render_scale เต็ม
                        scale_to_use = min(render_scale, 1.5) if usable_native else render_scale
                        bitmap = page.render(scale=scale_to_use)
                        pil_img = bitmap.to_pil()
                        saved_image = _save_preview(pil_img, page_num)
                    except Exception as ren_err:
                        logger.warning(f"pypdfium2 render failed on page {page_num}: {ren_err}")
                page.close()

                if usable_native:
                    cleaned_text = _apply_it_keyword_correction(native_text)
                    results_by_page[page_num] = {
                        'page_number': page_num,
                        'text': cleaned_text,
                        'words': [],
                        'total_pages': total_pages,
                        'has_image': saved_image,
                        'extraction_mode': 'native_pdf',
                        'time_taken': round(time.time() - page_start, 2)
                    }
                    completed_count += 1
                    if progress_callback:
                        progress_callback(completed_count, total_pages, "extracting_native", time.time() - start_time)
                else:
                    vision_queue.append((page_num, pil_img, saved_image))

            pdf_doc.close()

            if vision_queue:
                batch_size = int(os.environ.get('OCR_VISION_BATCH_SIZE', 4))
                batches = [vision_queue[idx:idx + batch_size] for idx in range(0, len(vision_queue), batch_size)]
                worker_count = max(1, min(int(max_workers or 3), len(batches)))
                logger.info(
                    f"Hybrid PDF extraction: {len(results_by_page)}/{total_pages} pages extracted natively; "
                    f"running Batch Vision OCR on {len(vision_queue)} scanned/broken-Thai pages "
                    f"({len(batches)} batches of {batch_size}, workers={worker_count})."
                )

                def _run_vision_batch(batch_chunk):
                    b_start = time.time()
                    valid_imgs = [(p_num, p_img) for p_num, p_img, _ in batch_chunk if p_img is not None]
                    saved_map = {p_num: p_saved for p_num, _, p_saved in batch_chunk}
                    batch_texts = {}
                    batch_err = None
                    try:
                        if valid_imgs:
                            batch_texts = ocr_images_batch(valid_imgs, lang=lang, filename=filename)
                    except Exception as e:
                        batch_err = str(e)
                    elapsed_each = round((time.time() - b_start) / max(len(batch_chunk), 1), 2)
                    out_items = []
                    for p_num, p_img, p_saved in batch_chunk:
                        if p_img is None:
                            out_items.append((p_num, {
                                'page_number': p_num,
                                'text': '',
                                'error': 'ไม่สามารถเรนเดอร์ภาพหน้าเอกสารได้',
                                'total_pages': total_pages,
                                'has_image': p_saved,
                                'extraction_mode': 'vision_ocr_batch',
                                'time_taken': elapsed_each
                            }))
                        elif batch_err:
                            out_items.append((p_num, {
                                'page_number': p_num,
                                'text': '',
                                'error': batch_err,
                                'total_pages': total_pages,
                                'has_image': saved_map.get(p_num, False),
                                'extraction_mode': 'vision_ocr_batch',
                                'time_taken': elapsed_each
                            }))
                        else:
                            out_items.append((p_num, {
                                'page_number': p_num,
                                'text': batch_texts.get(p_num, ''),
                                'words': [],
                                'total_pages': total_pages,
                                'has_image': saved_map.get(p_num, False),
                                'extraction_mode': 'vision_ocr_batch',
                                'time_taken': elapsed_each
                            }))
                    return out_items

                with ThreadPoolExecutor(max_workers=worker_count) as executor:
                    futures = [executor.submit(_run_vision_batch, b) for b in batches]
                    for fut in as_completed(futures):
                        for p_num, p_res in fut.result():
                            results_by_page[p_num] = p_res
                            completed_count += 1
                            if progress_callback:
                                progress_callback(completed_count, total_pages, "extracting_vision", time.time() - start_time)
            else:
                logger.info(
                    f"Hybrid PDF extraction: all {total_pages} pages extracted natively in {round(time.time() - start_time, 2)}s."
                )

            return [results_by_page[p] for p in range(1, total_pages + 1) if p in results_by_page]
        except Exception as hybrid_err:
            logger.warning(f"Hybrid pypdfium2 extraction failed ({hybrid_err}); falling back to Poppler + Vision OCR.")

    # ── Standard Poppler + Vision OCR Path ──
    try:
        poppler_path = POPPLER_PATH if os.path.exists(POPPLER_PATH) else None
        images = convert_from_bytes(
            pdf_bytes,
            dpi=dpi,
            poppler_path=poppler_path
        )
    except Exception as e:
        raise RuntimeError(f"ไม่สามารถแปลง PDF ได้: {str(e)}")

    total_pages = len(images)
    results = []
    
    for i, image in enumerate(images):
        page_num = i + 1
        page_start = time.time()
        saved_image = _save_preview(image, page_num)
        
        if progress_callback:
            progress_callback(page_num, total_pages, "extracting", time.time() - start_time)

        try:
            text_result = ocr_image(image, lang=lang, filename=filename)
            results.append({
                'page_number': page_num,
                'text': text_result.get('text', ''),
                'words': text_result.get('words', []),
                'total_pages': total_pages,
                'has_image': saved_image,
                'time_taken': round(time.time() - page_start, 2)
            })
        except Exception as e:
            results.append({
                'page_number': page_num,
                'text': '',
                'error': str(e),
                'total_pages': total_pages,
                'has_image': saved_image,
                'time_taken': round(time.time() - page_start, 2)
            })

    return results


def ocr_pdf_bytes_generator(pdf_bytes: bytes, dpi: int = 150, lang: str = 'tha+eng', filename: str = None, start_page: int = 1, end_page: int = None):
    """
    สกัดข้อความจาก PDF bytes แบบ Generator ทำงานแบบ Sequential
    (Gemini API มี Rate Limit จึงใช้ Sequential แทน Multi-thread)
    คืนค่าเป็น Generator yielding (page_data_dict, pil_image)
    รองรับ start_page และ end_page เพื่อให้แบ่งประมวลผลเอกสารขนาดใหญ่ได้
    """
    start_time = time.time()
    poppler_path = POPPLER_PATH if os.path.exists(POPPLER_PATH) else None
    
    try:
        from pdf2image.pdf2image import pdfinfo_from_bytes
        info = pdfinfo_from_bytes(pdf_bytes, poppler_path=poppler_path)
        total_pages = int(info.get("Pages", 1))
    except Exception as e:
        total_pages = 1

    first = max(1, start_page if start_page is not None else 1)
    last = min(total_pages, end_page) if (end_page is not None and end_page > 0) else total_pages
    if first > last:
        first = 1
        last = total_pages

    # เตรียมดึง Native Text จาก PDF เผื่อเป็น Fallback หรือกัน LLM Repetition Runaway / API Quota (402/429)
    native_pages_map = {}
    try:
        native_list = _extract_native_pdf_pages(pdf_bytes)
        if native_list:
            for idx, n_txt in enumerate(native_list, start=1):
                if n_txt and len(n_txt.strip()) >= 15:
                    native_pages_map[idx] = _sanitize_ocr_markdown(n_txt)
    except Exception:
        native_pages_map = {}

    # ใช้ Sequential เพื่อป้องกัน Rate Limit ของ Gemini Free Tier (15 RPM)
    for page_num in range(first, last + 1):
        page_start = time.time()
        
        try:
            images = convert_from_bytes(
                pdf_bytes,
                dpi=dpi,
                poppler_path=poppler_path,
                first_page=page_num,
                last_page=page_num
            )
            if not images:
                continue
            image = images[0]
        except Exception as e:
            res = {
                'page_number': page_num,
                'text': native_pages_map.get(page_num, ''),
                'words': [],
                'error': f"ไม่สามารถแปลง PDF หน้าที่ {page_num} ได้: {str(e)}",
                'total_pages': total_pages,
                'target_total': (last - first + 1),
                'time_taken': round(time.time() - page_start, 2)
            }
            yield res, None
            continue
            
        try:
            text_result = ocr_image(image, lang=lang, filename=filename)
            ocr_txt = text_result.get('text', '') or ''
            native_fallback = native_pages_map.get(page_num, '')
            # หาก Vision API เกิด Error (เช่น 402/429) หรือข้อความที่ได้สั้นผิดปกติหลังจากตัด repetition loop ให้ใช้ Native PDF Text แทน
            if native_fallback and (
                text_result.get('error')
                or ocr_txt.startswith('❌')
                or (len(ocr_txt.strip()) < max(40, int(len(native_fallback) * 0.35)))
            ):
                logger.info(f"Using native PDF text fallback on page {page_num} ({len(native_fallback)} chars vs OCR {len(ocr_txt)} chars)")
                text_result['text'] = native_fallback
                text_result.pop('error', None)
            page_data = {
                'page_number': page_num,
                'total_pages': total_pages,
                'target_total': (last - first + 1),
                'time_taken': round(time.time() - page_start, 2)
            }
            res = {**text_result, **page_data}
        except Exception as e:
            native_fallback = native_pages_map.get(page_num, '')
            res = {
                'page_number': page_num,
                'text': native_fallback,
                'words': [],
                'error': None if native_fallback else str(e),
                'total_pages': total_pages,
                'target_total': (last - first + 1),
                'time_taken': round(time.time() - page_start, 2)
            }
        yield res, image
        
        # หน่วงเวลาแบบ Adaptive ตามจำนวน API Keys เพื่อสมดุลความเร็วและ Rate Limit
        if page_num < last:
            key_count = max(1, len(get_all_api_keys()))
            delay_sec = 0.6 if key_count > 1 else 1.5
            time.sleep(delay_sec)

