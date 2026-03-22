import os
import cv2
import numpy as np
import logging
from paddleocr import PaddleOCR

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ocr():
    logger.info("Starting PaddleOCR Debug Test...")
    
    # Force disable model source check
    os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
    
    try:
        # Initialize engine
        logger.info("Initializing PaddleOCR...")
        # Try disable mkldnn for stability
        ocr = PaddleOCR(lang='th', enable_mkldnn=False, use_angle_cls=True)
        logger.info("Engine initialized.")
        
        # Create a dummy image (white with black text placeholder)
        img = np.ones((500, 500, 3), dtype=np.uint8) * 255
        cv2.putText(img, "Test OCR", (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
        
        logger.info("Running OCR on dummy image...")
        result = ocr.ocr(img)
        
        logger.info("OCR Result received!")
        logger.info(f"Result: {result}")
        
        logger.info("Test Completed Successfully!")
        
    except Exception as e:
        logger.error(f"Test Failed with error: {e}", exc_info=True)

if __name__ == "__main__":
    test_ocr()
