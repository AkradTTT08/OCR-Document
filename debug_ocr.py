import sys
import os
import io
import numpy as np
from PIL import Image

sys.path.append(os.path.join(os.getcwd(), 'backend'))
from ocr_engine import get_paddle_ocr, preprocess_image

def debug_ocr():
    ocr = get_paddle_ocr()
    img_path = r"d:\OCR-Github\OCR-Document\uploads\cache\6236aa0c-97bc-406c-b86b-23f4566c6661\page_5.jpg"
    print(f"Running raw OCR on {img_path}...")
    pil_image = Image.open(img_path)
    processed_pil = preprocess_image(pil_image)
    img_np = np.array(processed_pil.convert('RGB'))
    
    result = ocr.ocr(img_np)
    
    all_words = []
    if hasattr(result, '__iter__'):
        for page_res in result:
            res_dict = None
            if hasattr(page_res, 'json'):
                res_dict = page_res.json.get('res', {})
            elif isinstance(page_res, dict):
                res_dict = page_res.get('res', page_res)
            
            if res_dict:
                texts = res_dict.get('rec_texts', [])
                scores = res_dict.get('rec_scores', [])
                for i in range(len(texts)):
                    all_words.append({
                        'text': texts[i],
                        'score': scores[i]
                    })
    
    if not all_words and result and isinstance(result, list):
        lines_raw = result[0] if isinstance(result[0], list) else result
        for item in lines_raw:
            if isinstance(item, list) and len(item) == 2 and isinstance(item[1], (tuple, list)):
                all_words.append({
                    'text': item[1][0],
                    'score': item[1][1]
                })

    with open("debug_ocr_out.txt", "w", encoding="utf-8") as f:
        for w in all_words:
            f.write(f"[{w['score']:.3f}] {w['text']}\n")
        
if __name__ == '__main__':
    debug_ocr()
