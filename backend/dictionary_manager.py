"""
Dictionary Manager - จัดการชุดคำศัพท์ภาษาไทยและอังกฤษ
- ไทย: PyThaiNLP (รวม word list จากราชบัณฑิตยสภา) + custom words
- อังกฤษ: pyspellchecker (frequency-based English dictionary)
"""
import os
import re
import logging
from typing import Set

logger = logging.getLogger(__name__)

# Path ของ custom word list
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
CUSTOM_WORDS_FILE = os.path.join(DATA_DIR, 'thai_custom_words.txt')
TELEX_TH_FILE = os.path.join(DATA_DIR, 'telex_th.txt')
ETLEX_EN_FILE = os.path.join(DATA_DIR, 'etlex_en.txt')

# Patterns
THAI_CHAR_RE = re.compile(r'[\u0E00-\u0E7F]')
ENG_CHAR_RE  = re.compile(r'^[a-zA-Z]')

_thai_cache: Set[str] | None = None
_eng_checker_cache = None       # pyspellchecker SpellChecker instance



def load_thai_dictionary() -> Set[str]:
    """
    โหลด Thai dictionary จาก PyThaiNLP + custom words
    Returns: Set ของคำไทยที่ถูกต้อง
    """
    global _thai_cache
    if _thai_cache is not None:
        return _thai_cache

    word_set: Set[str] = set()

    # 1. โหลดจาก PyThaiNLP (ราชบัณฑิตยสภา + คลังคำทั่วไป)
    try:
        from pythainlp.corpus.common import thai_words, thai_stopwords
        words = thai_words()
        word_set.update(words)
        stops = thai_stopwords()
        word_set.update(stops)
        logger.info(f"PyThaiNLP: {len(word_set):,} Thai words loaded")
    except ImportError:
        logger.warning("PyThaiNLP not found: pip install pythainlp")
    except Exception as e:
        logger.error(f"PyThaiNLP load error: {e}")

    # 2. LEXiTRON (telex_th.txt)
    if os.path.exists(TELEX_TH_FILE):
        try:
            with open(TELEX_TH_FILE, 'r', encoding='utf-8') as f:
                telex_words = {line.strip() for line in f if line.strip()}
                word_set.update(telex_words)
                logger.info(f"LEXiTRON: {len(telex_words):,} Thai words loaded")
        except Exception as e:
            logger.error(f"LEXiTRON Thai load error: {e}")

    # 3. Custom words (ภาษาไทยจากไฟล์)
    custom_thai = _load_custom_words(lang='thai')
    word_set.update(custom_thai)

    # 4. ตัวเลข
    for i in range(10):
        word_set.add(str(i))
        word_set.add(chr(0x0E50 + i))   # เลขไทย ๐-๙

    logger.info(f"Thai dictionary total: {len(word_set):,} words")
    _thai_cache = word_set
    return _thai_cache


def load_english_checker():
    """
    โหลด English spell checker (pyspellchecker)
    Returns: SpellChecker instance พร้อมคำ custom เพิ่มเติม
    """
    global _eng_checker_cache
    if _eng_checker_cache is not None:
        return _eng_checker_cache

    try:
        from spellchecker import SpellChecker
        checker = SpellChecker(language='en')

        # เพิ่ม LEXiTRON English words (etlex_en.txt)
        if os.path.exists(ETLEX_EN_FILE):
            try:
                with open(ETLEX_EN_FILE, 'r', encoding='utf-8') as f:
                    etlex_words = [line.strip().lower() for line in f if line.strip()]
                    checker.word_frequency.load_words(etlex_words)
                    logger.info(f"LEXiTRON: {len(etlex_words):,} English words added")
            except Exception as e:
                logger.error(f"LEXiTRON English load error: {e}")

        # เพิ่ม custom English words
        custom_eng = _load_custom_words(lang='english')
        if custom_eng:
            checker.word_frequency.load_words(custom_eng)
            logger.info(f"English custom: {len(custom_eng)} words added")

        logger.info("English SpellChecker ready")
        _eng_checker_cache = checker
        return checker
    except ImportError:
        logger.warning("pyspellchecker not found: pip install pyspellchecker")
        return None
    except Exception as e:
        logger.error(f"English checker load error: {e}")
        return None


# Keep backward-compat alias
def load_dictionary() -> Set[str]:
    return load_thai_dictionary()


def _load_custom_words(lang: str = 'all') -> set:
    """
    โหลด custom words จากไฟล์
    lang: 'thai' | 'english' | 'all'
    บรรทัดที่ขึ้นต้นด้วยตัวอักษรไทย → Thai, ขึ้นต้นด้วย a-z → English
    """
    result = set()
    if not os.path.exists(CUSTOM_WORDS_FILE):
        return result
    try:
        with open(CUSTOM_WORDS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                word = line.strip()
                if not word or word.startswith('#'):
                    continue
                is_thai = bool(THAI_CHAR_RE.search(word))
                is_eng  = bool(ENG_CHAR_RE.match(word))
                if lang == 'thai' and is_thai:
                    result.add(word)
                elif lang == 'english' and is_eng:
                    result.add(word.lower())
                elif lang == 'all':
                    result.add(word)
    except Exception as e:
        logger.error(f"Custom words load error: {e}")
    return result


def reload_dictionary() -> Set[str]:
    """โหลด dictionary ใหม่ทั้งหมด"""
    global _thai_cache, _eng_checker_cache
    _thai_cache = None
    _eng_checker_cache = None
    return load_thai_dictionary()


def add_custom_word(word: str) -> bool:
    """
    เพิ่มคำใหม่ใน custom word list
    ถ้าเป็นคำไทย → เพิ่มใน Thai cache
    ถ้าเป็นคำอังกฤษ → เพิ่มใน English checker
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

        # อัปเดต cache ที่เหมาะสม
        is_thai = bool(THAI_CHAR_RE.search(word))
        is_eng  = bool(ENG_CHAR_RE.match(word))

        global _thai_cache, _eng_checker_cache
        if is_thai and _thai_cache is not None:
            _thai_cache.add(word)
        if is_eng and _eng_checker_cache is not None:
            _eng_checker_cache.word_frequency.load_words([word.lower()])

        return True
    except Exception as e:
        logger.error(f"Error adding custom word: {e}")
        return False


def get_dictionary_stats() -> dict:
    """ดูสถิติ dictionary ทั้งไทยและอังกฤษ"""
    thai_dict = load_thai_dictionary()
    eng_checker = load_english_checker()

    thai_count = sum(1 for w in thai_dict if THAI_CHAR_RE.search(w))

    eng_count = 0
    if eng_checker is not None:
        try:
            eng_count = eng_checker.word_frequency.unique_words
        except Exception:
            eng_count = -1

    custom_count = 0
    if os.path.exists(CUSTOM_WORDS_FILE):
        with open(CUSTOM_WORDS_FILE, 'r', encoding='utf-8') as f:
            custom_count = sum(
                1 for line in f
                if line.strip() and not line.startswith('#')
            )

    return {
        'total_words': len(thai_dict) + max(eng_count, 0),
        'thai_words': thai_count,
        'english_words': eng_count,
        'custom_words': custom_count,
        'source': 'Thai: PyThaiNLP + LEXiTRON | English: pyspellchecker + LEXiTRON + Custom'
    }
