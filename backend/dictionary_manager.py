"""
Dictionary Manager - จัดการชุดคำศัพท์ภาษาไทยและอังกฤษแบบ Custom สำหรับ AI & Hybrid Proofreader
"""
import os
import logging
from typing import List, Set

logger = logging.getLogger(__name__)

# Path ของ custom word list
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
CUSTOM_WORDS_FILE = os.path.join(DATA_DIR, 'thai_custom_words.txt')
USER_WORDS_FILE = os.path.join(DATA_DIR, 'user_words.txt')

_PLACEHOLDER_LINES = {
    'กรุณาเพิ่มคำของคุณด้านล่าง',
    'ทดสอบคำพิเศษ999',
}


def _load_custom_words_list() -> List[str]:
    """โหลดรายการคำศัพท์ที่ผู้ใช้เพิ่มเอง (Custom Words) เรียงตามลำดับ"""
    result: List[str] = []
    seen: Set[str] = set()
    if not os.path.exists(CUSTOM_WORDS_FILE):
        return result
    try:
        with open(CUSTOM_WORDS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                word = line.strip()
                if not word or word.startswith('#') or word in _PLACEHOLDER_LINES:
                    continue
                key = word.lower()
                if key not in seen:
                    seen.add(key)
                    result.append(word)
    except Exception as e:
        logger.error(f"Custom words load error: {e}")
    return result


def _load_custom_words() -> set:
    """โหลด custom words เป็น set"""
    return set(_load_custom_words_list())


def get_custom_words_list() -> List[str]:
    """คืนค่ารายการคำศัพท์ Custom ทั้งหมด"""
    return _load_custom_words_list()


def reload_dictionary() -> set:
    """โหลด dictionary ใหม่ทั้งหมด"""
    return _load_custom_words()


def load_dictionary() -> set:
    return _load_custom_words()


def add_custom_word(word: str) -> bool:
    """
    เพิ่มคำใหม่ใน custom word list (จะถูกส่งไปพร้อมกับ System Prompt และใช้กรองใน Hybrid Spellchecker)
    """
    word = (word or '').strip()
    if not word or word.startswith('#'):
        return False

    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        existing_lower = {w.lower() for w in _load_custom_words_list()}
        if word.lower() not in existing_lower:
            with open(CUSTOM_WORDS_FILE, 'a', encoding='utf-8') as f:
                f.write(word + '\n')
        return True
    except Exception as e:
        logger.error(f"Error adding custom word: {e}")
        return False


def remove_custom_word(word: str) -> bool:
    """ลบคำออกจาก custom word list"""
    target = (word or '').strip().lower()
    if not target or not os.path.exists(CUSTOM_WORDS_FILE):
        return False
    try:
        with open(CUSTOM_WORDS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        new_lines = []
        removed = False
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and stripped.lower() == target:
                removed = True
                continue
            new_lines.append(line)
        if removed:
            with open(CUSTOM_WORDS_FILE, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
        return removed
    except Exception as e:
        logger.error(f"Error removing custom word: {e}")
        return False


def get_dictionary_stats() -> dict:
    """ดูสถิติ dictionary ทั้งภาษาไทยและอังกฤษ"""
    words = _load_custom_words_list()
    thai_words = sum(1 for w in words if any('\u0e00' <= c <= '\u0e7f' for c in w))
    eng_words = len(words) - thai_words

    system_it_words = 0
    if os.path.exists(USER_WORDS_FILE):
        try:
            with open(USER_WORDS_FILE, 'r', encoding='utf-8') as f:
                system_it_words = sum(1 for line in f if line.strip() and not line.strip().startswith('#'))
        except Exception:
            pass

    return {
        'total_words': len(words) + system_it_words,
        'thai_words': thai_words,
        'english_words': eng_words,
        'custom_words': len(words),
        'system_it_words': system_it_words,
        'words': words,
        'source': 'Hybrid Custom + IT Domain Vocabulary'
    }
