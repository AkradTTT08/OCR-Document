import sys
import os
import io
import numpy as np
import logging
from PIL import Image

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from ocr_engine import get_paddle_ocr, _reconstruct_paddle_text

def analyze_layout(image_path):
    print(f"Analyzing layout for {image_path}...")
    img = Image.open(image_path)
    ocr = get_paddle_ocr()
    
    # Run OCR
    img_np = np.array(img.convert('RGB'))
    result = ocr.ocr(img_np)
    
    # We want the words before they are grouped into lines
    # _reconstruct_paddle_text returns (text, words)
    _, words = _reconstruct_paddle_text(result)
    
    # Group by lines ourselves to see the structure
    words.sort(key=lambda x: x['box'][0][1]) # Sort by Y
    
    lines = []
    if words:
        current_line = [words[0]]
        for i in range(1, len(words)):
            prev = words[i-1]
            curr = words[i]
            h = prev['box'][3][1] - prev['box'][0][1]
            if h <= 0: h = 15
            if abs(curr['box'][0][1] - prev['box'][0][1]) < h * 0.6:
                current_line.append(curr)
            else:
                lines.append(sorted(current_line, key=lambda x: x['box'][0][0]))
                current_line = [curr]
        lines.append(sorted(current_line, key=lambda x: x['box'][0][0]))

    print("\n--- LINE ANALYSIS ---")
    all_starts = []
    for i, line in enumerate(lines):
        line_str = " | ".join([f"{w['text']} (X:{int(w['box'][0][0])})" for w in line])
        print(f"L{i:2d}: {line_str}")
        for w in line:
            all_starts.append(int(w['box'][0][0]))

    print("\n--- X-START HISTOGRAM ---")
    hist, bin_edges = np.histogram(all_starts, bins=range(0, 2500, 20))
    for h, edge in zip(hist, bin_edges):
        if h > 1: # Significant clusters
            print(f"X range {edge}-{edge+20}: {h} words")

if __name__ == "__main__":
    # Use the images from the cache if available
    cache_dir = r"d:\OCR-Github\OCR-Document\uploads\cache\6236aa0c-97bc-406c-b86b-23f4566c6661"
    if os.path.exists(cache_dir):
        pages = [f for f in os.listdir(cache_dir) if f.startswith("page_") and f.endswith(".jpg")]
        for p in sorted(pages):
            analyze_layout(os.path.join(cache_dir, p))
    else:
        print("Cache directory not found. Please provide an image path.")
