
import sys, os
from PIL import Image
from pdf2image import convert_from_path

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from ocr_engine import ocr_image

PDF_PATH = r"d:\OCRDocument\CodingStandard.pdf"
if not os.path.exists(PDF_PATH):
    # Try another common path or just use one of the files in uploads if any
    print(f"File {PDF_PATH} not found.")
    sys.exit(1)

images = convert_from_path(PDF_PATH, dpi=300, first_page=5, last_page=5)
if not images:
    print("Failed to convert PDF")
    sys.exit(1)

img = images[0]
print(f"Image size: {img.size}")
res = ocr_image(img)
print(f"OCR Reported size: {res['width']}x{res['height']}")

for i, word in enumerate(res['words'][:10]):
    box = word['box']
    print(f"Word: {word['text']}")
    print(f"  Box: {box}")
    # Calculate percentages as frontend does
    left = (box[0][0] / res['width']) * 100
    top = (box[0][1] / res['height']) * 100
    width = ((box[1][0] - box[0][0]) / res['width']) * 100
    print(f"  Frontend calc: left={left:.2f}%, top={top:.2f}%, width={width:.2f}%")
