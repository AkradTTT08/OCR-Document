"""
Spell Checker - ตรวจสอบคำถูกคำผิดภาษาไทยและภาษาอังกฤษ
- ไทย: PyThaiNLP + พจนานุกรมราชบัณฑิตยสภา
- อังกฤษ: pyspellchecker (English frequency dictionary)
"""
import re
import logging
from typing import List, Dict, Any

from dictionary_manager import load_thai_dictionary, load_english_checker

logger = logging.getLogger(__name__)

# ── Patterns ──────────────────────────────────────────────────────────────────
THAI_CHAR_RE  = re.compile(r'[\u0E00-\u0E7F]+')
ENG_WORD_RE   = re.compile(r'^[a-zA-Z]{2,}$')          # อังกฤษล้วน ≥ 2 ตัว
SKIP_RE       = re.compile(                             # ข้าม: ตัวเลข สัญลักษณ์
    r'^[\d\s\.\,\!\?\:\;\(\)\[\]\{\}\'\"\-\_\+\=\/\\\@\#\$\%\^\&\*]+$'
)


# ── Tokenizer ─────────────────────────────────────────────────────────────────
# ── Tokenizer ─────────────────────────────────────────────────────────────────
_custom_trie = None

def tokenize_text(text: str) -> List[str]:
    """
    แบ่งคำโดยใช้ PyThaiNLP (รองรับทั้งไทย + อังกฤษในข้อความเดียวกัน)
    เพิ่มคำผิดที่คนไทยพิมพ์บ่อยแต่ระบบมักตัดเป็นคำย่อยลงใน Custom Dictionary (Trie)
    เพื่อให้ถูกจับเป็น 'คำผิด 1 คำ' แทนที่จะมองเป็นคำถูกต้อง 2 คำ
    """
    global _custom_trie
    try:
        from pythainlp.tokenize import word_tokenize
        from pythainlp.corpus.common import thai_words
        from pythainlp.util import dict_trie

        if _custom_trie is None:
            # ใช้คลังคำเดิมที่มี
            words = set(thai_words())
            # เพิ่มคำผิดที่มักถูกตัดแบ่ง (เช่น 'สำ' + 'หลับ' โดนตัดแล้วระบบมองว่าถูกทั้งคู่)
            known_misspellings = {
                'สำหลับ', 'สังเกตุ', 'อนุญาติ', 'ปรากฎ', 'ศริสเตียน', 
                'นะค่ะ', 'อะรัย', 'กะเพา', 'กระเพรา', 'สัมภาษ'
            }
            words.update(known_misspellings)
            _custom_trie = dict_trie(words)
            
        # เติม keep_whitespace=True เพื่อรักษา space ไว้สำหรับนับตำแหน่งอักษร
        return word_tokenize(text, custom_dict=_custom_trie, engine='newmm', keep_whitespace=True)
    except ImportError:
        logger.warning("PyThaiNLP not available – using whitespace tokenizer")
        return re.split(r'(\s+)', text)
    except Exception as e:
        logger.error(f"Tokenize error: {e}")
        return text.split()


# ── Language detection ────────────────────────────────────────────────────────
def detect_lang(token: str) -> str:
    """
    ตรวจสอบภาษาของ token
    Returns: 'thai' | 'english' | 'other'
    """
    if THAI_CHAR_RE.search(token):
        return 'thai'
    if ENG_WORD_RE.match(token):
        return 'english'
    return 'other'


# ── Thai suggestions ──────────────────────────────────────────────────────────
def _get_thai_suggestions(word: str, max_n: int = 5) -> List[str]:
    suggestions = []
    try:
        from pythainlp.spell import correct, spell
        corrected = correct(word)
        if corrected and corrected != word:
            suggestions.append(corrected)
        for s in spell(word)[:max_n]:
            if s not in suggestions and s != word:
                suggestions.append(s)
    except Exception:
        pass
    if not suggestions:
        suggestions = _edit_distance_suggestions(word, lang='thai', max_n=3)
    return suggestions[:max_n]


# ── English suggestions ───────────────────────────────────────────────────────
def _get_english_suggestions(word: str, max_n: int = 5) -> List[str]:
    checker = load_english_checker()
    if checker is None:
        return []
    try:
        candidates = checker.candidates(word.lower()) or set()
        # sort by frequency (highest first)
        scored = sorted(
            candidates,
            key=lambda w: checker.word_frequency[w],
            reverse=True
        )
        return [s for s in scored if s != word.lower()][:max_n]
    except Exception as e:
        logger.debug(f"English suggestion error: {e}")
        return []


# ── Edit-distance fallback ────────────────────────────────────────────────────
def _edit_distance_suggestions(word: str, lang: str = 'thai', max_n: int = 3) -> List[str]:
    if len(word) < 2:
        return []
    dictionary = load_thai_dictionary() if lang == 'thai' else set()
    word_len = len(word)
    candidates = []
    for dw in dictionary:
        if abs(len(dw) - word_len) <= 2:
            dist = _levenshtein(word, dw)
            if dist <= 2:
                candidates.append((dist, dw))
    candidates.sort(key=lambda x: x[0])
    return [w for _, w in candidates[:max_n]]


def _levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)
    if not s2:
        return len(s1)
    prev = range(len(s2) + 1)
    for c1 in s1:
        curr = [prev[0] + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(c1 != c2)))
        prev = curr
    return prev[-1]


# ── Core check ────────────────────────────────────────────────────────────────
def check_token(token: str, lang: str) -> bool:
    """ตรวจสอบว่า token สะกดถูกหรือไม่"""
    if lang == 'thai':
        thai_dict = load_thai_dictionary()
        return token in thai_dict

    if lang == 'english':
        checker = load_english_checker()
        if checker is None:
            return True     # ถ้าไม่มี checker ให้ผ่าน
        misspelled = checker.unknown([token.lower()])
        return len(misspelled) == 0

    return True     # 'other' – ไม่ตรวจ


def get_suggestions(token: str, lang: str, include: bool = True) -> List[str]:
    if not include:
        return []
    if lang == 'thai':
        return _get_thai_suggestions(token)
    if lang == 'english':
        return _get_english_suggestions(token)
    return []


def _build_line_map(text: str) -> list[int]:
    """
    Returns list where line_map[char_pos] = 1-indexed line number.
    Efficient: stores only newline positions, uses bisect for lookup.
    """
    import bisect
    newline_positions = [i for i, c in enumerate(text) if c == '\n']
    return newline_positions   # return sorted list of newline char-indices


def _get_line(pos: int, newline_positions: list) -> int:
    """Return 1-indexed line number for a character position."""
    import bisect
    return bisect.bisect_left(newline_positions, pos) + 1


# ── Main API ──────────────────────────────────────────────────────────────────
def spellcheck_text(text: str, include_suggestions: bool = True) -> Dict[str, Any]:
    """
    ตรวจสอบคำผิดในข้อความ (ไทย + อังกฤษ)
    เพิ่มระบบตรวจสอบบริบทเบื้องต้น (Semantic/Context aware)
    """
    newline_positions = _build_line_map(text)
    tokens_raw = tokenize_text(text)

    result_tokens: List[dict] = []
    error_list: List[dict] = []
    thai_count = eng_count = 0
    thai_errors = eng_errors = 0
    semantic_errors = 0
    position = 0

    # คู่คำที่มักใช้ผิดบริบท (ไทย)
    TH_HOMOPHONES = {
        'สำรับ': ['สำหรับ'],
        'สำหรับ': ['สำรับ'],
        'น่ารัก': ['หน้ารัก'],
        'หน้ารัก': ['น่ารัก'],
        'พรรณ': ['พันธ์', 'พันธุ์'],
        'พันธุ์': ['พรรณ', 'พันธ์'],
        'บันทึก': ['บรรทึก'],
        'บรรทึก': ['บันทึก'],
    }
    
    # คู่คำที่มักใช้ผิดบริบท (English)
    EN_HOMOPHONES = {
        'their': ['there', 'they\'re'],
        'there': ['their', 'they\'re'],
        'your': ['you\'re'],
        'you\'re': ['your'],
        'its': ['it\'s'],
        'it\'s': ['its'],
        'loose': ['lose'],
        'lose': ['loose'],
    }

    for i, token in enumerate(tokens_raw):
        if not token:
            position += len(token)
            continue

        line_number = _get_line(position, newline_positions)

        # ข้าม whitespace / สัญลักษณ์
        if not token.strip() or SKIP_RE.match(token):
            result_tokens.append({
                'token': token, 'lang': 'other',
                'is_correct': True, 'suggestions': [],
                'position': position, 'line_number': line_number,
                'error_type': None
            })
            position += len(token)
            continue

        lang = detect_lang(token)

        if lang == 'other':
            result_tokens.append({
                'token': token, 'lang': 'other',
                'is_correct': True, 'suggestions': [],
                'position': position, 'line_number': line_number,
                'error_type': None
            })
            position += len(token)
            continue

        if lang == 'thai':
            thai_count += 1
        else:
            eng_count += 1

        # 1. เช็คความถูกต้องตามพจนานุกรม
        is_correct = check_token(token, lang)
        error_type = 'misspelled' if not is_correct else None
        
        # 2. เช็คบริบทเบื้องต้น (Semantic Check)
        is_semantic_error = False
        context_suggestion = []
        
        if is_correct:
            # วิเคราะห์บริบทข้างเคียง (ห้ามติดช่องว่าง)
            def get_adj_token(idx, direction):
                curr = idx + direction
                while 0 <= curr < len(tokens_raw):
                    val = tokens_raw[curr].strip().lower()
                    if val and not SKIP_RE.match(val):
                        return val
                    curr += direction
                return ""

            prev_token = get_adj_token(i, -1)
            next_token = get_adj_token(i, 1)

            if lang == 'thai' and token in TH_HOMOPHONES:
                if token == 'สำหรับ' and prev_token in ['ชุด', 'ข้าว', 'อาหาร']:
                    is_semantic_error = True
                    context_suggestion = ['สำรับ']
                elif token == 'สำรับ' and (prev_token and prev_token not in ['ชุด', 'ข้าว', 'อาหาร']):
                    # ถ้าใช้สำรับ แต่บริบทไม่ใช่เรื่องอาหาร/ภาชนะ
                    is_semantic_error = True
                    context_suggestion = ['สำหรับ']
            
            elif lang == 'english' and token.lower() in EN_HOMOPHONES:
                t_low = token.lower()
                if t_low == 'your' and next_token in ['welcome', 'doing', 'going', 'right', 'better']:
                    is_semantic_error = True
                    context_suggestion = ["you're"]
                elif t_low == 'its' and next_token in ['a', 'the', 'an', 'very', 'not', 'really']:
                    # its a -> it's a
                    is_semantic_error = True
                    context_suggestion = ["it's"]
                elif t_low == 'there' and next_token in ['is', 'are', 'was', 'were']:
                    pass # correct
                elif t_low == 'their' and next_token in ['is', 'are', 'was', 'were']:
                    is_semantic_error = True
                    context_suggestion = ["there"]

            if is_semantic_error:
                error_type = 'semantic'
                is_correct = False
                suggestions = context_suggestion
                semantic_errors += 1
            else:
                suggestions = get_suggestions(token, lang, include=include_suggestions and not is_correct)
        else:
            suggestions = get_suggestions(token, lang, include=include_suggestions and not is_correct)

        if not is_correct:
            if error_type == 'misspelled':
                if lang == 'thai':
                    thai_errors += 1
                else:
                    eng_errors += 1
            
            error_list.append({
                'token': token,
                'lang': lang,
                'line_number': line_number,
                'suggestions': suggestions,
                'position': position,
                'error_type': error_type
            })

        result_tokens.append({
            'token': token,
            'lang': lang,
            'is_correct': is_correct,
            'suggestions': suggestions,
            'position': position,
            'line_number': line_number,
            'error_type': error_type
        })
        position += len(token)

    total_checked = thai_count + eng_count
    total_errors  = thai_errors + eng_errors + semantic_errors
    error_rate = round(total_errors / total_checked * 100, 2) if total_checked else 0

    return {
        'tokens': result_tokens,
        'errors': error_list,
        'summary': {
            'thai_tokens':    thai_count,
            'english_tokens': eng_count,
            'total_tokens':   total_checked,
            'error_count':    total_errors,
            'thai_errors':    thai_errors,
            'english_errors': eng_errors,
            'semantic_errors': semantic_errors,
            'error_rate':     error_rate
        }
    }


def spellcheck_pages(pages: List[Dict]) -> List[Dict]:
    """ตรวจสอบคำผิดในทุกหน้าของ OCR result"""
    results = []
    for page in pages:
        spell_result = spellcheck_text(page.get('text', ''))
        results.append({**page, 'spell_check': spell_result})
    return results
