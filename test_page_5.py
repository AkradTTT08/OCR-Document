import sys
import os
import io
import numpy as np
from PIL import Image

sys.path.append(os.path.join(os.getcwd(), 'backend'))
from ocr_engine import ocr_image

def test_page_5():
    img_path = r"d:\OCR-Github\OCR-Document\uploads\cache\6236aa0c-97bc-406c-b86b-23f4566c6661\page_5.jpg"
    print(f"Running OCR on {img_path}...")
    img = Image.open(img_path)
    res = ocr_image(img)
    
    with open("test_format_page5.txt", "w", encoding="utf-8") as f:
        f.write(res['text'])
    print("Done")

if __name__ == '__main__':
    test_page_5()
