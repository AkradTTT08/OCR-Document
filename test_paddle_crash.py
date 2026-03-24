import sys
import os
import io
import numpy as np
from PIL import Image
import cv2

sys.path.append(os.path.join(os.getcwd(), 'backend'))
from ocr_engine import get_paddle_ocr, preprocess_image

def test_paddle_crash():
    ocr = get_paddle_ocr()
    img_path = r"d:\OCR-Github\OCR-Document\uploads\cache\6236aa0c-97bc-406c-b86b-23f4566c6661\page_5.jpg"
    print(f"Loading {img_path}...")
    pil_image = Image.open(img_path)
    
    # Run original code
    img_np_original = np.array(pil_image.convert('RGB'))
    print(f"Original shape: {img_np_original.shape}, dtype: {img_np_original.dtype}")
    
    # Run preprocess
    processed_pil = preprocess_image(pil_image)
    img_np_processed = np.array(processed_pil.convert('RGB'))
    print(f"Processed shape: {img_np_processed.shape}, dtype: {img_np_processed.dtype}, contiguous: {img_np_processed.flags.c_contiguous}")
    
    # Save to investigate visually
    cv2.imwrite("test_page_5_processed.jpg", cv2.cvtColor(img_np_processed, cv2.COLOR_RGB2BGR))
    
    print("Running OCR on Processed Image...")
    try:
        res = ocr.ocr(img_np_processed)
        print("Success on processed!")
    except Exception as e:
        print(f"Crash on processed: {e}")
        
    print("Running OCR on Original Image...")
    try:
        res2 = ocr.ocr(img_np_original)
        print("Success on original!")
    except Exception as e:
        print(f"Crash on original: {e}")

if __name__ == '__main__':
    test_paddle_crash()
