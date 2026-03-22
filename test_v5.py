import os
import sys
import logging

# Add current directory to path
sys.path.append(os.getcwd())

from paddleocr import PaddleOCR
import cv2
import numpy as np

os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_v5_inference():
    th_model_dir = r"d:\OCRDocument\data\models\th"
    dict_path = r"d:\OCRDocument\data\th_dict.txt"
    
    logger.info(f"Testing PaddleOCR V5 with model dir: {th_model_dir}")
    
    try:
        # Initialize OCR with V5 model
        # For V5, we specify the model name and the local directory
        ocr = PaddleOCR(
            text_recognition_model_name="th_PP-OCRv5_mobile_rec",
            text_recognition_model_dir=th_model_dir,
            lang='th',
            device='cpu',
            show_log=True
        )
        
        logger.info("OCR Engine initialized successfully.")
        
        # Test with a blank image if no real image is provided
        img = np.zeros((100, 300, 3), dtype=np.uint8)
        cv2.putText(img, "TEST", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        results = ocr.predict(img)
        logger.info(f"OCR Results: {results}")
        
    except Exception as e:
        logger.error(f"OCR Failed: {e}", exc_info=True)

if __name__ == "__main__":
    test_v5_inference()
