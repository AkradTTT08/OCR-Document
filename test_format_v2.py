import sys
import os
import io
import numpy as np
from PIL import Image

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from ocr_engine import ocr_image

def test_formatting():
    # Use the images from the cache
    cache_dir = r"d:\OCR-Github\OCR-Document\uploads\cache\6236aa0c-97bc-406c-b86b-23f4566c6661"
    if not os.path.exists(cache_dir):
        print("Cache directory not found.")
        return

    output_file = "test_format_output_v2.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        pages = [p for p in os.listdir(cache_dir) if p.startswith("page_") and p.endswith(".jpg")]
        for p in sorted(pages):
            img_path = os.path.join(cache_dir, p)
            print(f"Running OCR on {img_path}...")
            img = Image.open(img_path)
            res = ocr_image(img)
            
            f.write(f"\n--- {p} ---\n")
            f.write(res['text'])
            f.write("\n\n")
            f.flush()

    print(f"Formatting results saved to {output_file}")

if __name__ == "__main__":
    test_formatting()
