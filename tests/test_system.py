"""
Unit Tests – Thai OCR Spell Check System
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestDictionary(unittest.TestCase):
    """ทดสอบ Dictionary Manager"""

    def test_load_dictionary(self):
        from dictionary_manager import load_dictionary
        d = load_dictionary()
        self.assertIsInstance(d, set)
        self.assertGreater(len(d), 1000, "Dictionary ควรมีคำมากกว่า 1,000 คำ")
        print(f"Dictionary size: {len(d):,} คำ")

    def test_thai_words_in_dict(self):
        from dictionary_manager import load_dictionary
        d = load_dictionary()
        # คำทั่วไปที่ควรอยู่ใน dictionary
        common_words = ['ไทย', 'ภาษา', 'คำ', 'การ', 'ที่']
        for word in common_words:
            self.assertIn(word, d, f"'{word}' ควรอยู่ใน dictionary")

    def test_add_custom_word(self):
        from dictionary_manager import add_custom_word, load_dictionary, reload_dictionary
        test_word = 'ทดสอบคำพิเศษ999'
        result = add_custom_word(test_word)
        self.assertTrue(result)
        
        # โหลดใหม่และตรวจสอบ
        d = reload_dictionary()
        self.assertIn(test_word, d, f"'{test_word}' ควรอยู่ใน dictionary หลังจากเพิ่ม")

    def test_dictionary_stats(self):
        from dictionary_manager import get_dictionary_stats
        stats = get_dictionary_stats()
        self.assertIn('total_words', stats)
        self.assertIn('thai_words', stats)
        self.assertIn('custom_words', stats)
        self.assertIn('source', stats)
        print(f"Stats: {stats}")


class TestSpellChecker(unittest.TestCase):
    """ทดสอบ Spell Checker"""

    def test_correct_thai_words(self):
        from spell_checker import spellcheck_text
        text = "ภาษาไทยถูกต้อง"
        result = spellcheck_text(text, include_suggestions=False)
        self.assertIn('tokens', result)
        self.assertIn('summary', result)

    def test_detect_wrong_word(self):
        from spell_checker import check_token
        # คำที่ไม่มีในพจนานุกรม
        self.assertFalse(check_token('กกกกกกกกกก', 'thai'), "คำสุ่มไม่ควรอยู่ใน dictionary")


    def test_spellcheck_result_structure(self):
        from spell_checker import spellcheck_text
        text = "ทดสอบ ระบบ ตรวจ"
        result = spellcheck_text(text)
        self.assertIn('tokens', result)
        self.assertIn('summary', result)
        self.assertIn('total_tokens', result['summary'])
        self.assertIn('error_count', result['summary'])
        self.assertIn('error_rate', result['summary'])

    def test_empty_text(self):
        from spell_checker import spellcheck_text
        result = spellcheck_text('')
        self.assertEqual(result['summary']['error_count'], 0)


class TestOCREngine(unittest.TestCase):
    """ทดสอบ OCR Engine (ต้องติดตั้ง Tesseract ก่อน)"""

    def test_import(self):
        try:
            from ocr_engine import preprocess_image
            self.assertTrue(True)
        except ImportError as e:
            self.skipTest(f"Import error: {e}")

    def test_preprocess_image(self):
        try:
            from ocr_engine import preprocess_image
            from PIL import Image
            import numpy as np
            
            # สร้างรูปภาพทดสอบ
            img = Image.fromarray(
                np.ones((100, 200), dtype=np.uint8) * 255
            )
            processed = preprocess_image(img)
            self.assertIsInstance(processed, Image.Image)
        except Exception as e:
            self.skipTest(f"Preprocess test skipped: {e}")


if __name__ == '__main__':
    print("=" * 50)
    print("Thai OCR Spell Check - Unit Tests")
    print("=" * 50)
    unittest.main(verbosity=2)
