"""
Diagnostic: test OCR on specific page from the PDF
"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv()

from pdf2image import convert_from_path
from ocr_engine import ocr_image
import pytesseract

PDF_PATH = r"d:\OCRDocument\CodingStandard.pdf"
DPI = 300
TARGET_PAGE = 4   # ทดสอบเฉพาะหน้า 4

print(f"Tesseract path: {pytesseract.pytesseract.tesseract_cmd}")
print(f"Converting page {TARGET_PAGE} of PDF at {DPI} DPI...")

poppler_path = os.environ.get('POPPLER_PATH', 'C:/poppler/poppler-25.12.0/Library/bin')
images = convert_from_path(
    PDF_PATH,
    dpi=DPI,
    first_page=TARGET_PAGE,
    last_page=TARGET_PAGE,
    poppler_path=poppler_path
)

print(f"Got {len(images)} image(s).")

if images:
    img = images[0]
    print(f"Image size: {img.size}")
    
    # Save image for visual inspection
    img.save(r"d:\OCRDocument\debug_page4.png")
    print("Saved page image to debug_page4.png")

    # Run OCR
    text = ocr_image(img, lang='tha')
    print(f"\n--- RAW OCR TEXT (first 1000 chars) ---")
    print(text[:1000] if text else "(empty)")
    
    if not text.strip():
        print("\n*** OCR returned blank text! Testing with raw pytesseract... ***")
        raw = pytesseract.image_to_string(img, lang='tha', config='--oem 3 --psm 4')
        print(f"Raw pytesseract result: {raw[:500] if raw else '(still blank)'}")
