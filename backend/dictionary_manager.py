"""
Dictionary Manager - จัดการชุดคำศัพท์ภาษาไทยและอังกฤษแบบ Custom สำหรับ AI Proofreader
"""
import os
import re
import logging

logger = logging.getLogger(__name__)

# Path ของ custom word list
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
CUSTOM_WORDS_FILE = os.path.join(DATA_DIR, 'thai_custom_words.txt')


def _load_custom_words() -> set:
    """
    โหลด custom words จากไฟล์
    """
    result = set()
    if not os.path.exists(CUSTOM_WORDS_FILE):
        return result
    try:
        with open(CUSTOM_WORDS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                word = line.strip()
                if word and not word.startswith('#'):
                    result.add(word)
    except Exception as e:
        logger.error(f"Custom words load error: {e}")
    return result


def reload_dictionary() -> set:
    """โหลด dictionary ใหม่ทั้งหมด"""
    return _load_custom_words()

def load_dictionary() -> set:
    return _load_custom_words()


def add_custom_word(word: str) -> bool:
    """
    เพิ่มคำใหม่ใน custom word list (จะถูกส่งไปพร้อมกับ System Prompt ให้ AI รู้จัก)
    """
    word = word.strip()
    if not word:
        return False

    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        existing = set()
        if os.path.exists(CUSTOM_WORDS_FILE):
            with open(CUSTOM_WORDS_FILE, 'r', encoding='utf-8') as f:
                existing = {line.strip() for line in f if line.strip()}

        if word not in existing:
            with open(CUSTOM_WORDS_FILE, 'a', encoding='utf-8') as f:
                f.write(word + '\n')
        return True
    except Exception as e:
        logger.error(f"Error adding custom word: {e}")
        return False


def get_dictionary_stats() -> dict:
    """ดูสถิติ dictionary"""
    custom_count = len(_load_custom_words())
    return {
        'total_words': custom_count,
        'thai_words': custom_count,
        'english_words': 0,
        'custom_words': custom_count,
        'source': 'Custom Vocabulary for AI Proofreader'
    }
