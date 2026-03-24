import sys
import os
import io
import numpy as np
from PIL import Image

sys.path.append(os.path.join(os.getcwd(), 'backend'))
from ocr_engine import get_paddle_ocr, preprocess_image, _reconstruct_paddle_text

def debug_pipeline():
    ocr = get_paddle_ocr()
    img_path = r"d:\OCR-Github\OCR-Document\uploads\cache\6236aa0c-97bc-406c-b86b-23f4566c6661\page_5.jpg"
    print(f"Running full pipeline OCR on {img_path}...")
    pil_image = Image.open(img_path)
    
    # Exactly what ocr_image does
    w, h = pil_image.size
    processed_pil = preprocess_image(pil_image)
    img_np = np.array(processed_pil.convert('RGB'))
    
    result = ocr.ocr(img_np)
    
    text, words = _reconstruct_paddle_text(result)
    with open("debug_pipeline_results.txt", "w", encoding="utf-8") as f:
        f.write("----- RECONSTRUCTED TEXT -----\n")
        f.write(text + "\n")
        
        f.write("\n----- WORDS -----\n")
        for w in words:
            if 'box' in w:
                f.write(f"[{w.get('confidence', 1.0):.3f}] {w['text']}\n")
        
if __name__ == '__main__':
    debug_pipeline()
