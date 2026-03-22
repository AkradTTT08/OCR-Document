import os
import sys
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    from ocr_engine import get_paddle_ocr
    print("Attempting to get PaddleOCR engine...")
    ocr = get_paddle_ocr()
    if ocr:
        print("Success! PaddleOCR initialized.")
    else:
        print("Failed to initialize PaddleOCR (returned None).")
except Exception as e:
    print(f"Caught Exception: {e}")
    import traceback
    traceback.print_exc()
