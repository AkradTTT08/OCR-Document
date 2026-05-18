"""
OCR Engine - แปลง PDF เป็นข้อความภาษาไทยด้วย qwen2.5vl:3b ผ่าน Ollama
"""
import os
import io
import time
import base64
import logging
import requests
import re
from PIL import Image
from pdf2image import convert_from_path, convert_from_bytes
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Global engine instance version
VERSION = "2.1.0-qwen2-vl"

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


# Maximum dimension to send to the vision model. Smaller = faster on CPU.
MAX_OCR_DIM = int(os.environ.get('OLLAMA_MAX_DIM', 2048))


def _resize_for_ocr(image: Image.Image) -> Image.Image:
    """
    ย่อรูปให้ด้านที่ยาวที่สุดไม่เกิน MAX_OCR_DIM เพื่อลดเวลา inference บน CPU
    """
    w, h = image.size
    max_dim = max(w, h)
    if max_dim <= MAX_OCR_DIM:
        return image
    scale = MAX_OCR_DIM / max_dim
    new_w = max(28, int(w * scale))
    new_h = max(28, int(h * scale))
    logger.info(f"Resizing image from {w}x{h} to {new_w}x{new_h} for Ollama inference")
    return image.resize((new_w, new_h), Image.LANCZOS)


def ocr_image(pil_image: Image.Image, lang: str = 'tha+eng') -> dict:
    """
    สกัดข้อความจากรูปภาพโดยใช้ Qwen2-VL ผ่าน Ollama
    คืนค่าเป็น Dict: { 'text': str, 'words': list }
    """
    ollama_url = os.environ.get('OLLAMA_API_URL', 'http://127.0.0.1:11434/api/chat')
    model_name = os.environ.get('OLLAMA_MODEL', 'qwen2.5vl:3b')

    w, h = pil_image.size

    # 1. Resize image to reduce inference time (especially on CPU)
    resized = _resize_for_ocr(pil_image)

    # 2. Convert image to base64
    buffered = io.BytesIO()
    resized.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

    prompt = (
        "You are a strict Thai-English OCR software. Your only task is to extract text character-by-character.\n"
        "Rules:\n"
        "1. Transcribe the Thai text EXACTLY as it is written in the image. DO NOT predict the next word, DO NOT fix grammar, and DO NOT autocomplete or change any Thai sentences.\n"
        "2. If you see 'วัตถุประสงค์', write 'วัตถุประสงค์'. Never guess or substitute other words.\n"
        "3. For grids and rows, just output each cell's text separated by a space on a new line.\n"
        "4. Output only raw parsed text content directly without any explanations."
    )
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [img_str]
            }
        ],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": 8192,
            "num_batch": 8,
            "num_predict": 4096
        }
    }

    try:
        logger.info(f"Calling Ollama API ({model_name})...")
        response = requests.post(ollama_url, json=payload, timeout=600)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            error_body = response.text
            raise RuntimeError(f"Ollama HTTP Error {response.status_code}: {error_body}") from e
        result = response.json()
        logger.info("Ollama API call successful.")
        
        # 2. Parse result
        text = ""
        if 'message' in result and 'content' in result['message']:
            text = result['message']['content']
        else:
            text = str(result)
            
        # Clean up any <think> blocks if present
        import re
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

        # 3. Post-processing (Text only)
        text = _apply_it_keyword_correction(text)
        
        # 4. Generate fallback bounding boxes since API might not return them per word
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
        return { 'text': f"Error: {e}", 'words': [], 'error': str(e) }


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
    สกัดข้อความจาก PDF bytes แบบ Generator ทำงานแบบ Multi-thread (จำกัด 2 Threads สำหรับ API Request)
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
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def process_page(i, image):
        page_num = i + 1
        page_start = time.time()
        try:
            res = ocr_image(image, lang=lang)
            res.update({
                'page_number': page_num,
                'total_pages': total_pages,
                'time_taken': round(time.time() - page_start, 2)
            })
            return res
        except Exception as e:
            err_msg = str(e)
            return {
                'page_number': page_num,
                'text': '',
                'words': [],
                'error': err_msg,
                'total_pages': total_pages,
                'time_taken': round(time.time() - page_start, 2)
            }

    # Set to 1 worker because running multiple vision model inferences locally on Ollama will likely cause OOM on standard GPUs
    max_workers = 1
        
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_page, i, img): i for i, img in enumerate(images)}
        for future in as_completed(futures):
            page_data = future.result()
            idx = page_data['page_number'] - 1
            yield page_data, images[idx]
