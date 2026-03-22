"""
Direct Tesseract test using the exact same pipeline as the Flask backend
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv()

import pytesseract
from PIL import Image, ImageDraw
from ocr_engine import preprocess_image

TESSERACT_CMD = os.environ.get('TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe')
if os.path.exists(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    print(f"Tesseract found at: {TESSERACT_CMD}")
else:
    print(f"WARNING: Tesseract NOT found at: {TESSERACT_CMD}")

# Create a test image with Thai text
img = Image.new('RGB', (900, 300), color='white')
draw = ImageDraw.Draw(img)
draw.text((50, 50), 'Coding Standard v1.0', fill='black')
draw.text((50, 100), 'คู่มือมาตรฐานการเขียนโค้ด', fill='black')
draw.text((50, 150), 'สำหรับนักพัฒนา (สำหลับ)', fill='black')

print(f"Test image size: {img.size}")
processed = preprocess_image(img)
print(f"Preprocessed image size: {processed.size}")

# Test PSM 3
result_psm3 = pytesseract.image_to_string(processed, lang='tha', config='--oem 3 --psm 3 -c preserve_interword_spaces=1')
print(f"\nPSM 3 result ({len(result_psm3.strip())} chars):")
print(result_psm3)

# Test PSM 6 single uniform block
result_psm6 = pytesseract.image_to_string(processed, lang='tha', config='--oem 3 --psm 6 -c preserve_interword_spaces=1')
print(f"\nPSM 6 result ({len(result_psm6.strip())} chars):")
print(result_psm6)
