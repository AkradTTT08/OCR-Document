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

# Normalized path using os.path.normpath
POPPLER_PATH = os.path.normpath(os.environ.get(
    'POPPLER_PATH',
    r'C:\poppler\Library\bin'
).strip().strip('"'))

logger.info(f"Using POPPLER_PATH: {POPPLER_PATH}")

if os.path.exists(POPPLER_PATH):
    logger.info(f"POPPLER_PATH exists: {POPPLER_PATH}")
    if POPPLER_PATH not in os.environ['PATH']:
        os.environ['PATH'] = POPPLER_PATH + os.pathsep + os.environ['PATH']
        logger.info("Added POPPLER_PATH to system PATH")
else:
    logger.warning(f"POPPLER_PATH does not exist: {POPPLER_PATH}")


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
        line_words = line.split()
        num_words = max(len(line_words), 1)
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


def get_all_api_keys() -> list[str]:
    """
    อ่าน API Keys ทั้งหมดจาก GOOGLE_API_KEY หรือ GOOGLE_API_KEYS ใน .env
    สามารถใส่หลายคีย์คั่นด้วยเครื่องหมายจุลภาค (,) เช่น Key1,Key2
    """
    raw = os.environ.get('GOOGLE_API_KEY', '') or os.environ.get('GOOGLE_API_KEYS', '')
    if not raw:
        from pathlib import Path
        env_file = Path(__file__).resolve().parent.parent / '.env'
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('GOOGLE_API_KEY=') or line.startswith('GOOGLE_API_KEYS='):
                        raw = line.split('=', 1)[1].strip()
                        break
    keys = [k.strip() for k in raw.split(',') if k.strip()]
    return keys if keys else []


_gemini_clients_cache = {}

def _get_gemini_client(key_index: int = 0):
    """
    สร้าง Gemini client จาก google-genai SDK (ตัวใหม่) รองรับการเลือก Key Index
    และถูกแคชไว้เพื่อป้องกันปัญหา Client ถูกปิด (Closed) ระหว่างทำ Streaming
    """
    global _gemini_clients_cache
    try:
        from google import genai
        keys = get_all_api_keys()
        if not keys:
            raise ValueError("ไม่พบ GOOGLE_API_KEY ใน environment variables กรุณาตั้งค่าใน .env")
        idx = key_index % len(keys)
        
        if idx not in _gemini_clients_cache:
            _gemini_clients_cache[idx] = genai.Client(api_key=keys[idx])
            
        return _gemini_clients_cache[idx]
    except ImportError:
        raise ImportError(
            "ไม่พบ library 'google-genai' กรุณารัน: pip install google-genai"
        )


def ocr_image(pil_image: Image.Image, lang: str = 'tha+eng', filename: str = None) -> dict:
    """
    สกัดข้อความจากรูปภาพโดยใช้ Google Gemini Vision API (google-genai SDK)
    คืนค่าเป็น Dict: { 'text': str, 'words': list }
    """
    model_name = os.environ.get('GEMINI_MODEL', 'gemini-3.1-flash')
    w, h = pil_image.size

    # ลดขนาด Prompt ลงเพื่อประหยัด Token และให้กระชับที่สุด แต่เพิ่มเงื่อนไข Mermaid
    system_prompt = (
        "Extract text from image exactly as is. DO NOT fix typos or grammar. "
        "Return raw text only without markdown. Stop generating when text ends. "
        "CRITICAL INSTRUCTION FOR FLOWCHARTS: If the image contains a flowchart or process diagram, "
        "you MUST convert it into a Mermaid.js graph. Embed the Mermaid code within the text using ```mermaid ... ``` block. "
        "Preserve the semantic meaning, steps, and conditions accurately."
    )
    user_prompt = "Transcribe exactly. Preserve typos. Convert flowcharts to Mermaid.js code if present."


    try:
        from google.genai import types

        keys = get_all_api_keys()
        clients = [_get_gemini_client(i) for i in range(len(keys))] if keys else [_get_gemini_client()]
        logger.info(f"Calling Gemini API ({model_name}) with {len(clients)} available API keys...")

        # --- Image Optimization to Save Tokens ---
        img_to_send = pil_image
        max_dim = 1600
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            new_w, new_h = int(w * ratio), int(h * ratio)
            img_to_send = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            logger.info(f"Resized image from {w}x{h} to {new_w}x{new_h} to save tokens.")

        # แปลง PIL Image เป็น bytes
        img_buffer = io.BytesIO()
        img_to_send.save(img_buffer, format='JPEG', quality=85)
        img_bytes = img_buffer.getvalue()
        # -----------------------------------------

        max_retries = 2
        raw_fallback_models = [model_name, 'gemini-3.1-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
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
                                max_output_tokens=2048,
                            )
                        )
                        success = True
                        break  # Success, break retry loop
                    except Exception as e:
                        last_error = e
                        error_msg = str(e)
                        if '404' in error_msg or 'NOT_FOUND' in error_msg or 'not found' in error_msg.lower():
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
                            max_output_tokens=2048,
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
                used_model = getattr(response, 'model_version', None) or 'gemini-3.1-flash'
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

        # อนุญาตให้มี Markdown code block (เช่น ```mermaid) เพื่อเก็บโครงสร้าง Flowchart
        # หากมี ``` ครอบข้อความธรรมดามา ก็ปล่อยไว้เพราะระบบเก็บเป็น Markdown อยู่แล้ว
        text = text.strip()

        # Post-processing
        text = _apply_it_keyword_correction(text)

        # Generate fallback bounding boxes
        words = _generate_fallback_words(text, w, h)

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


def ocr_pdf_bytes(pdf_bytes: bytes, dpi: int = 150, lang: str = 'tha+eng', progress_callback=None, filename: str = None) -> list[dict]:
    """
    สกัดข้อความจาก PDF bytes
    """
    start_time = time.time()
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
        
        if progress_callback:
            progress_callback(page_num, total_pages, "extracting", time.time() - start_time)

        try:
            text_result = ocr_image(image, lang=lang, filename=filename)
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

    return results


def ocr_pdf_bytes_generator(pdf_bytes: bytes, dpi: int = 150, lang: str = 'tha+eng', filename: str = None):
    """
    สกัดข้อความจาก PDF bytes แบบ Generator ทำงานแบบ Sequential
    (Gemini API มี Rate Limit จึงใช้ Sequential แทน Multi-thread)
    คืนค่าเป็น Generator yielding (page_data_dict, pil_image)
    """
    start_time = time.time()
    poppler_path = POPPLER_PATH if os.path.exists(POPPLER_PATH) else None
    
    try:
        from pdf2image.pdf2image import pdfinfo_from_bytes
        info = pdfinfo_from_bytes(pdf_bytes, poppler_path=poppler_path)
        total_pages = int(info.get("Pages", 1))
    except Exception as e:
        total_pages = 1

    # ใช้ Sequential เพื่อป้องกัน Rate Limit ของ Gemini Free Tier (15 RPM)
    for page_num in range(1, total_pages + 1):
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
            raise RuntimeError(f"ไม่สามารถแปลง PDF หน้าที่ {page_num} ได้: {str(e)}")
            
        try:
            text_result = ocr_image(image, lang=lang, filename=filename)
            page_data = {
                'page_number': page_num,
                'total_pages': total_pages,
                'time_taken': round(time.time() - page_start, 2)
            }
            res = {**text_result, **page_data}
        except Exception as e:
            res = {
                'page_number': page_num,
                'text': '',
                'words': [],
                'error': str(e),
                'total_pages': total_pages,
                'time_taken': round(time.time() - page_start, 2)
            }
        yield res, image
        
        # หน่วงเวลา 4 วินาทีระหว่างหน้า เพื่อป้องกัน Rate Limit (15 RPM)
        if page_num < total_pages:
            time.sleep(4)
