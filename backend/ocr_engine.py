"""
OCR Engine - แปลง PDF เป็นข้อความภาษาไทยด้วย Tesseract OCR
"""
import os
import io
import cv2
import numpy as np
import logging
import threading
from PIL import Image, ImageEnhance
from pdf2image import convert_from_path, convert_from_bytes
from dotenv import load_dotenv
import re
# Tesseract removed to use PaddleOCR exclusively

# Stability Fixes for Windows/CPU (Paddle 3.x)
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
os.environ['FLAGS_enable_pir_api'] = '0'
os.environ['FLAGS_enable_onednn'] = '0'
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['PADDLE_DISABLE_PIR_API'] = '1'
os.environ['FLAGS_use_legacy_executor'] = '1'

# Global engine instance (lazy loaded)
VERSION = "1.0.1-PaddleOCR-Verified"
os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
_paddle_ocr_engine = None
_paddle_ocr_lock = threading.Lock()

def get_paddle_ocr():
    """
    Lazy-load PaddleOCR engine to avoid server startup crash.
    Uses local assets if configured, otherwise falls back to defaults (automatic download).
    """
    global _paddle_ocr_engine
    
    # 0. Resolve Local Paths from .env
    local_rec_dir = os.environ.get('PADDLEOCR_TH_REC_MODEL_DIR')
    local_det_dir = os.environ.get('PADDLEOCR_TH_DET_MODEL_DIR')
    local_dict_path = os.environ.get('PADDLEOCR_TH_DICT_PATH')
    
    with _paddle_ocr_lock:
        if _paddle_ocr_engine is None:
            try:
                from paddleocr import PaddleOCR
                
                # 1. Initialize Engine (PaddleOCR API)
                logger.info(f"Initializing PaddleOCR (CPU, lang='th')...")
                
                # Use local model paths if provided and exist
                rec_model_dir = local_rec_dir if local_rec_dir and os.path.exists(local_rec_dir) else None
                det_model_dir = local_det_dir if local_det_dir and os.path.exists(local_det_dir) else None
                rec_char_dict_path = local_dict_path if local_dict_path and os.path.exists(local_dict_path) else None
                
                if rec_model_dir:
                    logger.info(f"Using local Recognition model: {rec_model_dir}")
                if det_model_dir:
                    logger.info(f"Using local Detection model: {det_model_dir}")
                
                # 1. Initialize Engine (PaddleOCR API)
                logger.info(f"Initializing PaddleOCR (CPU, lang='th')...")
                
                # Use default initialization as it verified to work in diagnostic script
                _paddle_ocr_engine = PaddleOCR(
                    lang='th',
                    use_angle_cls=True,
                    drop_score=0.3,  # Adjusted for better sensitivity (was 0.7)
                    show_log=False
                )
                logger.info("PaddleOCR engine initialized successfully.")
                
            except Exception as e:
                msg = f"PaddleOCR Initialization Failed: {e}"
                logger.error(msg)
                _paddle_ocr_engine = f"ERROR: {msg}"
        
        if isinstance(_paddle_ocr_engine, str) and _paddle_ocr_engine.startswith("ERROR"):
            return None 
            
        return _paddle_ocr_engine

# Load .env locally to ensure variables are available
load_dotenv()

logger = logging.getLogger(__name__)

# Normalized path using os.path.normpath
POPPLER_PATH = os.path.normpath(os.environ.get(
    'POPPLER_PATH',
    r'C:\poppler\Library\bin'
).strip().strip('"'))

# Poppler configuration for PDF to Image conversion
logger.info(f"Using POPPLER_PATH: {POPPLER_PATH}")

if os.path.exists(POPPLER_PATH):
    logger.info(f"POPPLER_PATH exists: {POPPLER_PATH}")
    # Add to PATH for better reliability with pdf2image
    if POPPLER_PATH not in os.environ['PATH']:
        os.environ['PATH'] = POPPLER_PATH + os.pathsep + os.environ['PATH']
        logger.info("Added POPPLER_PATH to system PATH")
    
    # Verify pdfinfo can be found
    pdfinfo_path = os.path.join(POPPLER_PATH, "pdfinfo.exe").replace('\\', '/')
    if os.path.exists(pdfinfo_path):
        logger.info(f"Verified pdfinfo.exe at: {pdfinfo_path}")
    else:
        
        logger.warning(f"pdfinfo.exe NOT FOUND at: {pdfinfo_path}")
else:
    logger.warning(f"POPPLER_PATH does not exist: {POPPLER_PATH}")

# Tesseract configuration removed to use PaddleOCR exclusively


def preprocess_image(pil_image: Image.Image) -> Image.Image:
    """
    Preprocess รูปภาพเพื่อแก้อ่านฟอนต์ไทยแบบไม่มีหัว (Headless fonts เช่น Kanit)
    มี Safety Fallback: ถ้า Thresholding ทำให้หน้าว่างเปล่า จะคืนเป็น Grayscale ทันที
    """
    # 1. แปลงเป็น numpy array และ Grayscale
    img = np.array(pil_image)
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img.copy()

    # 2. ปรับ Contrast ให้ข้อความกับพื้นหลังแยกกันชัดเจน
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 3. ให้ภาพเบลอนิดหน่อย
    denoised = cv2.GaussianBlur(enhanced, (3, 3), 0)

    # 4. ใช้ Binarization แบบ Otsu (คำนวณอัตโนมัติตามความสว่างของหน้า)
    _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 5. ทำ Erosion เพื่อให้ตัวหนังสือ "หนาขึ้น" เล็กน้อย
    kernel = np.ones((2, 2), np.uint8)
    thick_text = cv2.erode(binary, kernel, iterations=1)

    # 6. Safety Fallback: ถ้าผลลัพธ์เกือบขาวทั้งหมด (>97%) แสดงว่า Threshold ทำลายข้อความ
    # ให้ fallback กลับเป็น Grayscale เรียบๆ เพื่อไม่ให้หน้าว่างเปล่า
    white_pct = np.sum(thick_text == 255) / thick_text.size
    if white_pct > 0.97:
        logger.warning(f"Preprocessing caused {white_pct:.1%} white pixels – falling back to grayscale")
        return Image.fromarray(gray)

    return Image.fromarray(thick_text)


def _ocr_quality_score(text: str) -> float:
    """
    คำนวณคะแนนคุณภาพ OCR สำหรับ PaddleOCR (มักจะสูงกว่า Tesseract)
    """
    if not text or len(text.strip()) == 0:
        return 0.0
    
    import re
    # 1. นับอักขระอ่านออกพื้นฐาน
    readable = re.compile(r'[\u0E00-\u0E7Fa-zA-Z0-9\s\.\,\;\:\(\)\[\]\-\_\/\+\=\!\?\@\#\%\'\"\<\>\&\*]')
    readable_count = sum(1 for c in text if readable.match(c))
    
    # 2. บทลงโทษสำหรับขยะ (ลดลงเพราะ PaddleOCR ไม่ค่อยสร้างขยะ 'เส อล ม')
    garbage_patterns = [
        r'[\|]{4,}',
        r'[เเ]{4,}',
    ]
    penalty = 0.0
    for pattern in garbage_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            penalty += len(match) * 0.5
            
    score = (readable_count - penalty) / len(text)
    return max(0.0, min(1.0, score))


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
        
    # ค้นหาคำที่อาจจะเพี้ยน (Simple mapping for now, can be upgraded to fuzzy)
    # เช่น 'A1' -> 'AI', 'C PU' -> 'CPU'
    modified_text = text
    for word in known_words:
        # ลองแทนที่แบบ Case-insensitive และลบ space ภายในคำที่อาจจะเกิดจาก OCR
        # เฉพาะคำภาษาอังกฤษสั้นๆ เช่น CPU, AI, API
        if word.isupper() and len(word) <= 5:
            # สร้าง pattern ที่ยอมรับ space ระหว่างตัวอักษร เช่น C P U
            pattern = ' '.join(list(word))
            modified_text = re.sub(r'\b' + re.escape(pattern) + r'\b', word, modified_text)
            
    return modified_text


def _clean_toc_noise(text: str) -> str:
    """
    ทำความสะอาด OCR artifacts บน TOC และหน้าทั่วไป:
    - ลบ leader dots ซ้ำ
    - ใช้ Table Cleaner กรอง garbage lines (เส อล ม) ออกด้วย
    """
    import re
    # 1. ลบ leader dots ซ้ำ
    text = re.sub(r'[\.]{4,}', ' ...', text)
    # 2. ลบ whitespace ซ้ำ
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # 3. เรียกใช้ table cleaner เพื่อกรอง 'เส อล ม' (ถ้าถูกนิยามไว้แล้ว)
    try:
        text = _clean_table_ocr_output(text)
    except NameError:
        pass
    return text


def _remove_table_lines(gray_img: np.ndarray) -> np.ndarray:
    """
    ลบเส้นตาราง (horizontal + vertical lines) ออกจากภาพด้วย Morphological Operations
    ใช้ dilation 7x7 เพื่อลบ corner joints และ pixel artifacts รอบเส้นให้หมด
    และลบ small blobs (noise) ที่เกิดจากเศษเส้น
    """
    _, binary = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # ── Horizontal lines ──────────────────────────────────────────────────
    h_size = max(20, gray_img.shape[1] // 40)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_size, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel, iterations=1)
    # dilate แนวสูง (3x1) เพื่อลบ artifact ด้านบน/ล่างของเส้น
    h_lines = cv2.dilate(h_lines, np.ones((3, 1), np.uint8), iterations=1)

    # ── Vertical lines ────────────────────────────────────────────────────
    v_size = max(20, gray_img.shape[0] // 40)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_size))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel, iterations=1)
    # dilate แนวกว้าง (1x3) เพื่อลบ artifact ซ้าย/ขวาของเส้น
    v_lines = cv2.dilate(v_lines, np.ones((1, 3), np.uint8), iterations=1)

    # รวม mask + expand 7x7 เพื่อลบ corner joints ถึงจุดตัดเส้นให้หมดจด
    table_mask = cv2.add(h_lines, v_lines)
    table_mask = cv2.dilate(table_mask, np.ones((7, 7), np.uint8), iterations=1)

    # ลบเส้นออก
    cleaned = gray_img.copy()
    cleaned[table_mask > 0] = 255

    # ── Small Blob Removal (Noise Filtering) ─────────────────────────────
    # binarize ภาพที่ลบเส้นแล้วเพื่อหา noise
    _, cleaned_bin = cv2.threshold(cleaned, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cleaned_bin, connectivity=8)
    
    # ลบ blob ที่มีขนาดเล็ก (< 25 pixels) ซึ่งมักเป็นเศษเส้นหรือ noise
    final_img = cleaned.copy()
    for i in range(1, n_labels):
        if stats[i, cv2.CC_STAT_AREA] < 25:
            final_img[labels == i] = 255
            
    return final_img


def _is_table_page(gray_np: np.ndarray) -> bool:
    """
    ตรวจสอบว่าหน้านี้มีตารางหรือไม่ — ใช้ภาพ full-resolution
    kernel เล็ก (1/40) เพื่อจับเส้นบางๆ (PDF table border lines)
    threshold ต่ำเพื่อไม่พลาดพลาดตารางแบบบาง
    """
    try:
        _, binary = cv2.threshold(gray_np, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # kernel เล็กลง (// 40) = จับเส้นที่สั้นกว่าได้
        h_size = max(20, gray_np.shape[1] // 40)
        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_size, 1))
        h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel)
        h_count = cv2.countNonZero(h_lines)

        v_size = max(20, gray_np.shape[0] // 40)
        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_size))
        v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel)
        v_count = cv2.countNonZero(v_lines)

        total_px = gray_np.size
        h_ratio = h_count / total_px
        v_ratio = v_count / total_px

        logger.info(f"Table detection: h_ratio={h_ratio:.5f} v_ratio={v_ratio:.5f} "
                    f"(img={gray_np.shape[1]}x{gray_np.shape[0]})")

        # threshold ต่ำลง: เส้นนอน > 0.1% AND เส้นตั้ง > 0.03%
        return h_ratio > 0.001 and v_ratio > 0.0003
    except Exception as e:
        logger.warning(f"Table detection failed: {e}")
        return False


def preprocess_table_image(pil_image: Image.Image) -> Image.Image:
    """
    Preprocess รูปภาพสำหรับหน้าตารางโดยเฉพาะ:
    1. แปลงเป็น Grayscale
    2. ลบเส้นตาราง (horizontal + vertical lines)
    3. CLAHE เพิ่ม contrast
    4. Binarize แบบ Otsu
    ผลคือภาพที่มีแต่ข้อความใน cell ไม่มีเส้นตาราง
    """
    img_np = np.array(pil_image)
    if len(img_np.shape) == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np.copy()

    # ลบเส้นตาราง
    cleaned = _remove_table_lines(gray)

    # Gaussian blur เพื่อซ่อน pixel remnants รอบขอบเส้นที่เหลือ (เพิ่มเป็น 5x5 เพื่อความนวล)
    blurred = cv2.GaussianBlur(cleaned, (5, 5), 0)

    # เพิ่ม contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(blurred)

    # Binarize
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Safety check
    white_pct = np.sum(binary == 255) / binary.size
    if white_pct > 0.998:
        logger.warning("Table preprocess: few text pixels, using cleaned grayscale")
        return Image.fromarray(cleaned)

    return Image.fromarray(binary)


def _clean_table_ocr_output(text: str) -> str:
    """
    Post-process OCR output สำหรับหน้าตาราง:
    - ลบบรรทัดที่เป็น garbage จากเส้นตาราง (เช่น 'เส อล ม', 'เ ส อ')
    - เพิ่มความเข้มงวดในการกรองบรรทัดที่มีแต่เศษตัวอักษร
    """
    import re
    lines = text.splitlines()
    good_lines = []
    
    # regex สำหรับขยะที่เกิดจากเส้นตาราง (เส อล ม และความผันแปรอื่นๆ)
    # ครอบคลุมอักขระที่ Tesseract มักอ่านผิดจากเส้น: ส, อ, ล, ม, เ, |, 1 (เศษเส้น)
    garbage_re = re.compile(r'^[เสอลมเอเเ|||_ \-\.1\(\)\[\]\(\)\|]+$')
    
    # นิยาม garbage_chars เพิ่มเติมสำหรับความปลอดภัย
    garbage_chars = set("เสอลมเเ|||_-. ")
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        # 1. เช็กด้วย Regex (แม่นยำกว่า subset)
        if garbage_re.match(stripped) and len(stripped) < 20:
            # ถ้าทั้งบรรทัดมีแต่อักขระขยะ และไม่ยาวมากพอจะเป็นประโยคจริง
            continue
            
        # 2. เช็กว่าเป็นบรรทัด 'เส อล ม' หรือไม่ (มีแต่ garbage_chars)
        char_set = set(stripped)
        if char_set.issubset(garbage_chars) and len(stripped) < 15:
            continue
            
        # 3. นับตัวอักษรจริง (ไทย + ASCII ตัวอักษรและตัวเลข)
        real_chars = re.sub(r'[^\u0E00-\u0E7Fa-zA-Z0-9]', '', stripped)
        
        # 4. นับสัดส่วนตัวอักษรจริงต่อความยาวทั้งหมด
        noise_chars = re.sub(r'[\u0E00-\u0E7Fa-zA-Z0-9\s]', '', stripped)
        
        # 5. นับคำ
        words = stripped.split()
        
        # เงื่อนไขการเก็บ:
        # - มีตัวอักษรจริงอย่างน้อย 4 ตัว
        # - OR มีคำที่เป็นที่รู้จัก
        if len(real_chars) >= 4 or (len(words) >= 2 and len(real_chars) >= 2):
            # ตัวอักษรจริงต้องมีความสำคัญ (เข้มงวดขึ้น)
            if len(noise_chars) < len(real_chars) * 1.5: 
                good_lines.append(stripped)

    return '\n'.join(good_lines)


def _is_toc_page(pil_image: Image.Image, lang: str = 'tha+eng') -> bool:
    """
    ตรวจสอบว่าหน้านี้เป็นหน้าสารบัญ (Table of Contents) หรือไม่
    ใช้ 2 วิธี:
      1) Quick OCR keyword scan (สารบัญ / CONTENTS / DOCUMENT HISTORY)
      2) Leader-dot pattern scan โดยใช้ morphological horizontal run detection
    """
    import re
    try:
        # ── Method 1: Quick keyword OCR ───────────────────────────────────
        small = pil_image.copy()
        small.thumbnail((800, 1100), Image.LANCZOS)
        gray_np = np.array(small.convert('L'))
        _, binary_small = cv2.threshold(gray_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        small_pil = Image.fromarray(binary_small)

        cfg = '--oem 3 --psm 6 -c preserve_interword_spaces=1'
        raw = pytesseract.image_to_string(small_pil, lang=lang, config=cfg)

        toc_keywords = [
            'สารบัญ', 'CONTENTS', 'TABLE OF CONTENTS',
            'DOCUMENT HISTORY', 'INDEX'
        ]
        raw_upper = raw.upper()
        for kw in toc_keywords:
            if kw.upper() in raw_upper:
                logger.info(f"TOC page detected via keyword: '{kw}'")
                return True

        # ── Method 2: Leader-dot horizontal pattern detection ─────────────
        # Leader dots = small dark blobs repeated horizontally in a row
        # ใช้ Connected Component Analysis บน downscaled image
        _, binary_inv = cv2.threshold(gray_np, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_inv, connectivity=8)

        # นับจำนวน small-square components (dots) แต่ละ row band
        page_h = gray_np.shape[0]
        row_band_h = max(1, page_h // 40)   # แบ่งเป็น ~40 bands
        band_dot_count = {}

        for i in range(1, n_labels):
            area = stats[i, cv2.CC_STAT_AREA]
            w    = stats[i, cv2.CC_STAT_WIDTH]
            h    = stats[i, cv2.CC_STAT_HEIGHT]
            cy   = stats[i, cv2.CC_STAT_TOP]  + h // 2
            # dot = เล็ก เกือบสี่เหลี่ยม
            if area < 50 and w <= 12 and h <= 12 and w > 0 and h > 0:
                band = cy // row_band_h
                band_dot_count[band] = band_dot_count.get(band, 0) + 1

        # นับ bands ที่มี > 5 dots (น่าจะเป็น leader-dot line)
        dot_line_count = sum(1 for cnt in band_dot_count.values() if cnt >= 5)
        logger.info(f"TOC dot-pattern: {dot_line_count} dot-lines detected")

        if dot_line_count >= 4:   # มีอย่างน้อย 4 บรรทัดที่มี leader dots
            logger.info(f"TOC page detected via leader-dot pattern ({dot_line_count} lines)")
            return True

        return False
    except Exception as e:
        logger.warning(f"TOC detection failed: {e}")
        return False


def _remove_leader_dots(gray_img: np.ndarray) -> np.ndarray:
    """
    ลบจุดนำ (leader dots ......) ออกจากภาพก่อน OCR
    ใช้ Connected Component Analysis:
      - จุดนำ = component ขนาดเล็ก (area < 40px) ที่อยู่รวมกันเป็นแถว
      - ตัวอักษรไทย/อังกฤษ = component ขนาดใหญ่กว่า
    Return: grayscale image (white background) พร้อม OCR
    """
    _, binary = cv2.threshold(gray_img, 0, 255,
                              cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        binary, connectivity=8
    )

    # ระบุ component ที่น่าจะเป็น dot (เล็กและเกือบสี่เหลี่ยมจัตุรัส)
    dot_mask = np.zeros_like(binary, dtype=np.uint8)
    for i in range(1, n_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        w    = stats[i, cv2.CC_STAT_WIDTH]
        h    = stats[i, cv2.CC_STAT_HEIGHT]
        if area < 40 and w <= 10 and h <= 10:
            dot_mask[labels == i] = 255

    # ลบเฉพาะ row ที่มีความหนาแน่น dot สูง (> 3% ของความกว้าง)
    # เพื่อไม่ให้ลบวรรคตอนทั่วไปเช่น จุด จุลภาค
    cleaned = gray_img.copy()
    page_width = gray_img.shape[1]
    for row in range(gray_img.shape[0]):
        dot_count = int(np.sum(dot_mask[row, :]) / 255)
        if dot_count / page_width > 0.03:   # มีจุด > 3% ของแถว
            cleaned[row, dot_mask[row, :] > 0] = 255   # เปลี่ยนเป็นสีขาว

    return cleaned



def preprocess_toc_image(pil_image: Image.Image) -> Image.Image:
    """
    Preprocess รูปภาพสำหรับหน้าสารบัญโดยเฉพาะ:
    1. แปลงเป็น Grayscale
    2. ลบ leader dots ออกด้วย Connected Component Analysis
    3. ใช้ CLAHE เพิ่ม contrast
    4. Binarize แบบ Otsu
    ผลคือภาพที่มีแต่ข้อความ ไม่มีจุดนำ
    """
    img_np = np.array(pil_image)
    if len(img_np.shape) == 3:
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
        gray = img_np.copy()

    # ลบ leader dots ก่อนเลย
    cleaned = _remove_leader_dots(gray)

    # เพิ่ม contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(cleaned)

    # Binarize
    _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Safety check
    white_pct = np.sum(binary == 255) / binary.size
    if white_pct > 0.99:
        logger.warning("TOC preprocess made image too white, falling back to grayscale")
        return Image.fromarray(cleaned)

    return Image.fromarray(binary)


def _reconstruct_paddle_text(result):
    """
    เรียงลำดับกล่องข้อความจาก PaddleOCR ให้เป็นบรรทัดตามพิกัด Y และ X
    จัดเรียงข้อความจาก PaddleOCR ให้เป็นบรรทัดที่อ่านง่าย
    คืนค่าเป็น Tuple (ข้อความทั้งหมด, รายชื่อคำพร้อมพิกัด)
    """
    if result is None or len(result) == 0:
        return "", []

    all_words = []
    
    # 0. ตรวจสอบ Format (Paddle 3.x อาจคืนค่าเป็น dict)
    if isinstance(result, dict) or (isinstance(result, list) and len(result) > 0 and isinstance(result[0], dict)):
        res_dict = result if isinstance(result, dict) else result[0]
        texts = res_dict.get('rec_texts', [])
        scores = res_dict.get('rec_scores', [])
        polys = res_dict.get('rec_polys', res_dict.get('dt_polys', []))
        
        for i in range(len(texts)):
            poly = polys[i]
            if not isinstance(poly, list):
                poly = poly.tolist()
            # ยุบ [x1,y1,x2,y2,x3,y3,x4,y4] -> [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            if len(poly) == 8:
                box = [[poly[0], poly[1]], [poly[2], poly[3]], [poly[4], poly[5]], [poly[6], poly[7]]]
            else:
                box = poly
            
            all_words.append({
                'text': texts[i],
                'box': box,
                'confidence': float(scores[i]) if i < len(scores) else 1.0
            })
    else:
        # Legacy 2.x format: [[[box], (text, score)], ...]
        lines_raw = result[0] if result and isinstance(result[0], list) else []
        for item in lines_raw:
            if len(item) == 2:
                all_words.append({
                    'text': item[1][0],
                    'box': item[0],
                    'confidence': float(item[1][1])
                })

    # Filter out garbage words/lines before processing
    # Regex for garbage that often appears from lines/tables
    garbage_re = re.compile(r'^[เสอลมเอเเ|||_ \-\.1\(\)\[\]\(\)\|]+$')
    garbage_chars = set("เสอลมเเ|||_-. ")
    
    def is_junk(w_obj):
        s = w_obj['text'].strip()
        if not s: return True
        
        # 1. Basic garbage regex (mostly special chars/marks)
        if len(s) < 20 and garbage_re.match(s): return True
        if len(s) < 15 and set(s).issubset(garbage_chars): return True
        
        # 2. Heuristic for "Line-Noise" (All-Cap strings with low vowel ratio)
        if s.isupper() and len(s) > 4:
            vowels = set("AEIOUY")
            vowel_count = sum(1 for c in s if c in vowels)
            vowel_ratio = vowel_count / len(s)
            common_abbrs = {"SQL", "PR", "ID", "CM", "KG", "MM", "TV", "PC", "WS", "DPI", "OCR"}
            if vowel_ratio < 0.2 and s not in common_abbrs:
                return True
                
        # 3. Repeated characters (lines/dots)
        if len(s) > 3:
            from collections import Counter
            counts = Counter(s)
            most_common, count = counts.most_common(1)[0]
            if count / len(s) > 0.7: return True

        # 4. Physical Size Filter (Suppress small artifacts)
        if 'box_norm' in w_obj:
            bn = w_obj['box_norm']
            w_box = bn[1][0] - bn[0][0]
            h_box = bn[2][1] - bn[0][1]
            # Lowered from 0.005 to 0.002 for better sensitivity
            if w_box < 0.002 and h_box < 0.002:
                return True

        # 5. Thai Mark-Only Filter (Standalone symbols like ะ, ่, ิ)
        # If it's a very short Thai string with no base consonant AND low confidence, it's garbage
        # Thai vowels/marks: \u0E30-\u0E3A (vowels), \u0E47-\u0E4E (tone marks)
        thai_marks_only = re.match(r'^[\u0E30-\u0E3A\u0E47-\u0E4E]+$', s)
        if thai_marks_only:
             # Only filter if it's really sketchy (low confidence)
             if w_obj.get('confidence', 1.0) < 0.4:
                 return True

        # 6. High density of special characters
        real_chars = re.sub(r'[^\u0E00-\u0E7Fa-zA-Z0-9]', '', s)
        if len(s) > 3:
            ratio = len(real_chars) / len(s)
            if ratio < 0.3: return True
            
        # 7. Too few real characters in a long-ish string
        if len(real_chars) < 2 and len(s) > 5: return True
        
        return False

    all_words = [w for w in all_words if not is_junk(w)]

    if not all_words:
        return "", []

    # 1. เรียงตาม Y (บนลงล่าง) เพื่อแยกบรรทัด
    all_words.sort(key=lambda x: x['box'][0][1])
    
    reconstructed_lines = []
    if all_words:
        current_line = [all_words[0]]
        def join_line_with_gaps(line_words):
            if not line_words: return ""
            line_words.sort(key=lambda x: x['box'][0][0])
            
            res_parts = [line_words[0]['text']]
            for i in range(1, len(line_words)):
                prev = line_words[i-1]
                curr = line_words[i]
                
                # คำนวณช่องว่างระหว่างคำ (Gap)
                # x2 ของคำก่อนหน้า เทียบกับ x1 ของคำปัจจุบัน
                gap = curr['box'][0][0] - prev['box'][1][0]
                
                # กะความกว้างตัวอักษรเฉลี่ย
                prev_text_len = max(len(prev['text']), 1)
                char_w = (prev['box'][1][0] - prev['box'][0][0]) / prev_text_len
                
                if gap > char_w * 3:
                     # ถ้าช่องว่างกว้างกว่า 3 ตัวอักษร ให้ใส่จุดไข่ปลา
                     num_dots = min(int(gap / (char_w * 1.5 + 1)), 30)
                     if num_dots > 2:
                         res_parts.append(" " + "." * num_dots + " ")
                     else:
                         res_parts.append("   ")
                else:
                    res_parts.append(" ")
                
                res_parts.append(curr['text'])
            return "".join(res_parts)

        for i in range(1, len(all_words)):
            prev = all_words[i-1]
            curr = all_words[i]
            
            h = prev['box'][3][1] - prev['box'][0][1]
            if h <= 0: h = 15
            
            if abs(curr['box'][0][1] - prev['box'][0][1]) < h * 0.6:
                current_line.append(curr)
            else:
                reconstructed_lines.append(join_line_with_gaps(current_line))
                current_line = [curr]
        
        reconstructed_lines.append(join_line_with_gaps(current_line))

    full_text = "\n".join(reconstructed_lines)
    return full_text, all_words


def _clean_common_misreads(text: str) -> str:
    """
    ล้างคำที่มักแสกนผิด เช่น 9 ที่ท้ายประโยค (มาจาก - หรือจุด)
    """
    if not text: return ""
    # 1. ลบ 9 หรือ - หรือ . ที่อยู่ลอยๆ ท้ายบรรทัด (มักมาจาก bullet)
    text = re.sub(r'\s+[9\-\.]$', '', text)
    # 2. ลบตัวอักษรขยะตัวเดียวที่ต้นบรรทัด
    text = re.sub(r'^[9\-\.]\s+', '', text)
    return text

def ocr_image(pil_image: Image.Image, lang: str = 'tha+eng') -> dict:
    """
    สกัดข้อความจากรูปภาพพร้อมพิกัด (Bounding Boxes)
    คืนค่าเป็น Dict: { 'text': str, 'words': list }
    """
    ocr = get_paddle_ocr()
    if ocr is None:
        return { 'text': '', 'words': [], 'error': 'PaddleOCR init failed' }

    try:
        # 1. เตรียมภาพ
        w, h = pil_image.size
        img_np = np.array(pil_image.convert('RGB'))
        
        # 2. Run OCR
        with _paddle_ocr_lock:
            logger.info("Starting PaddleOCR.ocr() call...")
            result = ocr.ocr(img_np)
            logger.info("PaddleOCR.ocr() call successful.")

        # 3. จัดระเบียบผลลัพธ์
        text, words = _reconstruct_paddle_text(result)
        
        # 4. Normalize coordinates (0..1) for frontend reliability
        for w_obj in words:
            if 'box' in w_obj:
                raw_box = w_obj['box']
                # raw_box is [[x0,y0], [x1,y1], [x2,y2], [x3,y3]]
                norm_box = []
                for pt in raw_box:
                    norm_box.append([
                        round(pt[0] / w, 6) if w > 0 else 0,
                        round(pt[1] / h, 6) if h > 0 else 0
                    ])
                w_obj['box_norm'] = norm_box

        # 5. Post-processing (Text only)
        text = _clean_table_ocr_output(text)
        text = _clean_common_misreads(text)
        text = _apply_it_keyword_correction(text)
        
        # 6. Final cleaning for each line in reconstructed text
        clean_lines = [_clean_common_misreads(line) for line in text.split('\n')]
        text = "\n".join(clean_lines)

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




import time

def ocr_pdf_file(pdf_path: str, dpi: int = 300, lang: str = 'tha+eng', progress_callback=None) -> list[dict]:
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
            text = ocr_image(image, lang=lang)
            results.append({
                'page_number': page_num,
                'text': text,
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


def ocr_pdf_bytes(pdf_bytes: bytes, dpi: int = 300, lang: str = 'tha+eng', progress_callback=None) -> list[dict]:
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
            text = ocr_image(image, lang=lang)
            results.append({
                'page_number': page_num,
                'text': text,
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


def ocr_pdf_bytes_generator(pdf_bytes: bytes, dpi: int = 300, lang: str = 'tha+eng'):
    """
    สกัดข้อความจาก PDF bytes แบบ Generator ทำงานแบบ Multi-thread
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

    # PaddleOCR is heavy on CPU, limited to 1 concurrent page for stability on CPU
    max_workers = 1
        
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_page, i, img): i for i, img in enumerate(images)}
        for future in as_completed(futures):
            page_data = future.result()
            idx = page_data['page_number'] - 1
            yield page_data, images[idx]
