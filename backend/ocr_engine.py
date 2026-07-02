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


def _get_gemini_client():
    """
    สร้าง Gemini client จาก google-genai SDK (ตัวใหม่)
    """
    try:
        from google import genai
        api_key = os.environ.get('GOOGLE_API_KEY', '')
        if not api_key:
            raise ValueError("ไม่พบ GOOGLE_API_KEY ใน environment variables กรุณาตั้งค่าใน .env")
        client = genai.Client(api_key=api_key)
        return client
    except ImportError:
        raise ImportError(
            "ไม่พบ library 'google-genai' กรุณารัน: pip install google-genai"
        )


def ocr_image(pil_image: Image.Image, lang: str = 'tha+eng') -> dict:
    """
    สกัดข้อความจากรูปภาพโดยใช้ Google Gemini Vision API (google-genai SDK)
    คืนค่าเป็น Dict: { 'text': str, 'words': list }
    """
    model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash-lite')
    w, h = pil_image.size

    # ลดขนาด Prompt ลงเพื่อประหยัด Token และให้กระชับที่สุด
    system_prompt = (
        "Extract text from image exactly as is. DO NOT fix typos or grammar. "
        "Return raw text only without markdown. Stop generating when text ends."
    )
    user_prompt = "Transcribe exactly. Preserve all intentional typos."


    try:
        from google.genai import types

        client = _get_gemini_client()
        logger.info(f"Calling Gemini API ({model_name})...")

        # --- Image Optimization to Save Tokens ---
        # Gemini คำนวณ Token ของภาพจากความละเอียด (Resolution) ยิ่งภาพใหญ่ยิ่งกิน Token เยอะ
        # หากภาพมีขนาดเกิน 1600px จะทำการย่อส่วนลง (ยังเพียงพอสำหรับ OCR) และส่งเป็น JPEG
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

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type='image/png'),
                        user_prompt,
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.1,  # Set slightly above 0.0 to prevent infinite degenerate loops
                        max_output_tokens=2048, # Lower from 8192 to prevent massive walls of text
                    )
                )
                break  # Success
            except Exception as e:
                error_msg = str(e)
                if '429' in error_msg or 'Quota' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                    if attempt < max_retries - 1:
                        logger.warning(f"Rate limit exceeded (429). Retrying in 50 seconds... (Attempt {attempt + 1}/{max_retries})")
                        time.sleep(50)
                        continue
                raise  # Re-raise if not a rate limit error or out of retries

        logger.info("Gemini API call successful.")

        # ดึงข้อความจาก response
        text = ""
        if response.text:
            text = response.text
        else:
            finish = response.candidates[0].finish_reason if response.candidates else 'unknown'
            logger.warning(f"Gemini returned no text. Finish reason: {finish}")
            text = ""

        # ลบ Markdown code block ถ้ามี (```...```)
        text = re.sub(r'```[^\n]*\n?', '', text)
        text = re.sub(r'```', '', text)
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
        return {'text': f"Error: {e}", 'words': [], 'error': str(e)}


def ocr_pdf_file(pdf_path: str, dpi: int = 150, lang: str = 'tha+eng', progress_callback=None) -> list[dict]:
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
            text_result = ocr_image(image, lang=lang)
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


def ocr_pdf_bytes(pdf_bytes: bytes, dpi: int = 150, lang: str = 'tha+eng', progress_callback=None) -> list[dict]:
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
            text_result = ocr_image(image, lang=lang)
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


def ocr_pdf_bytes_generator(pdf_bytes: bytes, dpi: int = 150, lang: str = 'tha+eng'):
    """
    สกัดข้อความจาก PDF bytes แบบ Generator ทำงานแบบ Sequential
    (Gemini API มี Rate Limit จึงใช้ Sequential แทน Multi-thread)
    คืนค่าเป็น Generator yielding (page_data_dict, pil_image)
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

    # ใช้ Sequential เพื่อป้องกัน Rate Limit ของ Gemini Free Tier (15 RPM)
    for i, image in enumerate(images):
        page_num = i + 1
        page_start = time.time()
        try:
            res = ocr_image(image, lang=lang)
            res.update({
                'page_number': page_num,
                'total_pages': total_pages,
                'time_taken': round(time.time() - page_start, 2)
            })
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
