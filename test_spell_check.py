import sys
import os
import io

# Force UTF-8 for output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from spell_checker import tokenize_text, spellcheck_text
from ocr_engine import preprocess_image, ocr_image
from PIL import Image
import numpy as np
import pytesseract

print("Testing PyThaiNLP tokenization...")
try:
    text = "โฟลเดอร์สำหรับเก็บ สำหลับ"
    tokens = tokenize_text(text)
    print(f"Tokens: {tokens}")
    res = spellcheck_text(text)
    print(f"Total Errors: {res['summary']['error_count']}")
    for err in res['errors']:
        print(f"Error: {err['token']} -> Suggestions: {err['suggestions']}")
except Exception as e:
    import traceback
    traceback.print_exc()

print("\nTesting Thai Dictionary content...")
try:
    from dictionary_manager import load_thai_dictionary
    td = load_thai_dictionary()
    print(f"Is 'สำหลับ' in dictionary? {'สำหลับ' in td}")
    print(f"Is 'สำหรับ' in dictionary? {'สำหรับ' in td}")
except Exception as e:
    import traceback
    traceback.print_exc()
