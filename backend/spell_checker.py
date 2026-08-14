"""
Spell Checker - ตรวจสอบคำถูกคำผิดภาษาไทยและภาษาอังกฤษด้วย Google Gemini API
"""
import re
import json
import logging
import os
import requests
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Pattern สำหรับตรวจสอบภาษาและตัวอักษร
THAI_CHAR_RE  = re.compile(r'[\u0E00-\u0E7F]+')
ENG_WORD_RE   = re.compile(r'^[a-zA-Z]{2,}$')
SKIP_RE       = re.compile(
    r'^[\d\s\.\,\!\?\:\;\(\)\[\]\{\}\'\"\-\_\+\=\/\\\@\#\$\%\^\&\*\`\|\<\>\~]+$'
)

def _build_line_map(text: str) -> list[int]:
    """Returns list where line_map[char_pos] = 1-indexed line number."""
    return [i for i, c in enumerate(text) if c == '\n']

def _get_line(pos: int, newline_positions: list) -> int:
    """Return 1-indexed line number for a character position."""
    import bisect
    return bisect.bisect_left(newline_positions, pos) + 1


def _get_custom_words() -> str:
    """โหลด custom words เป็น string เพื่อใส่ใน Prompt"""
    custom_words_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'thai_custom_words.txt')
    if not os.path.exists(custom_words_path):
        return ""
    words = []
    try:
        with open(custom_words_path, 'r', encoding='utf-8') as f:
            for line in f:
                word = line.strip()
                if word and not word.startswith('#'):
                    words.append(word)
    except Exception as e:
        logger.error(f"Error loading custom words: {e}")
    return ", ".join(words)


def spellcheck_text(text: str, include_suggestions: bool = True) -> Dict[str, Any]:
    """
    ตรวจสอบคำผิดในข้อความด้วย Ollama Qwen
    """
    if not text.strip():
        return _empty_spell_check(text)

    custom_words = _get_custom_words()
    custom_instruction = f"Special vocabulary to treat as CORRECT: {custom_words}." if custom_words else ""

    # System prompt สำหรับ AI Proofreader
    system_prompt = f"""You are an expert Thai and English linguist and proofreader.
Your task is to detect spelling errors, typographical errors, grammatical mistakes, and context-based semantic errors in the provided text.
Pay special attention to common Thai context errors (e.g., สำรับ vs สำหรับ, คะ vs ค่ะ, อนุญาติ vs อนุญาต, สังเกตุ vs สังเกต, กฏหมาย vs กฎหมาย) and English homophones (e.g., their/there).

CRITICAL RULES:
1. ONLY report actual errors. Do not report valid names, technical terms, or stylistic choices as errors.
2. Ignore markdown symbols, code blocks, URLs, mathematical formulas, and standalone numbers.
3. {custom_instruction}
4. When suggesting corrections, ensure they fit perfectly into the surrounding context.
5. The "token" MUST be the EXACT misspelled substring as it appears in the text.

Return your result STRICTLY in JSON format matching this schema:
{{
  "errors": [
    {{
      "token": "The exact misspelled word exactly as it appears in the text",
      "suggestions": ["most_likely_correction", "alternative_correction"],
      "error_type": "misspelled" // use "misspelled" for typos, "semantic" for context/grammar errors
    }}
  ]
}}
If there are no errors, return {{"errors": []}}.
Do not include any <think> reasoning blocks, markdown formatting, or any extra text outside the JSON block. Return ONLY raw JSON."""

    model_name = os.environ.get('GEMINI_MODEL', 'gemini-3.1-flash')
    
    ai_errors = []
    try:
        from ocr_engine import get_all_api_keys, _get_gemini_client
        keys = get_all_api_keys()
        if not keys:
            logger.error("GOOGLE_API_KEY is missing! Cannot run spellcheck.")
            return _empty_spell_check(text)

        from google.genai import types
        
        raw_fallback_models = [model_name, 'gemini-3.1-pro', 'gemini-3.1-flash', 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
        seen = set()
        fallback_models = [m for m in raw_fallback_models if not (m in seen or seen.add(m))]
        
        response = None
        for key_idx in range(len(keys)):
            client = _get_gemini_client(key_idx)
            for current_model in fallback_models:
                try:
                    logger.info(f"Calling Gemini [Key #{key_idx+1}] ({current_model}) for spellcheck...")
                    response = client.models.generate_content(
                        model=current_model,
                        contents=f"Check this text for errors:\n\n{text}",
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.0,
                            response_mime_type="application/json",
                        )
                    )
                    if response and response.text:
                        break
                except Exception as model_err:
                    logger.warning(f"Gemini Spellcheck error with Key #{key_idx+1} {current_model}: {model_err}")
                    continue
            if response and response.text:
                break

        if not response or not response.text:
            logger.warning("All Gemini models failed for spellcheck. Returning empty check.")
            return _empty_spell_check(text)

        if hasattr(response, 'usage_metadata'):
            try:
                from db_ingestion import log_api_usage
                used_model = getattr(response, 'model_version', None) or 'gemini-3.1-flash'
                log_api_usage("Spell_Check", used_model, response.usage_metadata)
            except Exception as usage_err:
                logger.error(f"Failed to log API usage: {usage_err}")

        content = response.text or ""
        
        # Clean potential markdown wrapping just in case
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
            
        data = json.loads(content.strip())
        ai_errors = data.get("errors", [])
        logger.info(f"Gemini spellcheck found {len(ai_errors)} errors.")
    except Exception as e:
        logger.error(f"Gemini Spellcheck Error: {e}")
        return _empty_spell_check(text)

    # Reconstruct tokens array & errors array for frontend compatibility
    newline_positions = _build_line_map(text)
    
    # 1. Filter valid errors that actually exist in the text
    valid_errors = []
    for err in ai_errors:
        token = err.get("token", "")
        if token and token in text:
            valid_errors.append(err)

    # 2. Find all occurrences of these valid error tokens in the text
    intervals = []
    for err in valid_errors:
        token = err["token"]
        start = 0
        while True:
            idx = text.find(token, start)
            if idx == -1:
                break
            intervals.append((idx, idx + len(token), err))
            start = idx + len(token)

    # 3. Sort intervals by start index and resolve overlaps (keep longest)
    intervals.sort(key=lambda x: (x[0], -x[1]))
    non_overlapping = []
    last_end = 0
    for itv in intervals:
        start, end, err = itv
        if start >= last_end:
            non_overlapping.append(itv)
            last_end = end

    # 4. Build the final tokens array
    result_tokens = []
    final_error_list = []
    
    thai_count = 0
    eng_count = 0
    thai_errors = 0
    eng_errors = 0
    semantic_errors = 0
    current_idx = 0

    def _count_lang(chunk: str):
        nonlocal thai_count, eng_count
        for w in re.split(r'(\s+)', chunk):
            if not w.strip(): continue
            if THAI_CHAR_RE.search(w): thai_count += 1
            elif ENG_WORD_RE.search(w): eng_count += 1

    for itv in non_overlapping:
        start, end, err = itv
        
        # Add the text before the error as correct tokens (split by spaces)
        if start > current_idx:
            prefix = text[current_idx:start]
            _count_lang(prefix)
            prefix_tokens = re.split(r'(\s+)', prefix)
            for pt in prefix_tokens:
                if not pt: continue
                lang = 'other'
                if THAI_CHAR_RE.search(pt): lang = 'thai'
                elif ENG_WORD_RE.search(pt): lang = 'english'
                
                result_tokens.append({
                    'token': pt, 'lang': lang, 'is_correct': True,
                    'suggestions': [], 'position': current_idx,
                    'line_number': _get_line(current_idx, newline_positions),
                    'error_type': None
                })
                current_idx += len(pt)
                
        # Add the error token
        token_str = text[start:end]
        error_type = err.get("error_type", "misspelled")
        lang = 'other'
        if THAI_CHAR_RE.search(token_str):
            lang = 'thai'
            thai_count += 1
        elif ENG_WORD_RE.search(token_str):
            lang = 'english'
            eng_count += 1
            
        if error_type == "semantic": semantic_errors += 1
        else:
            if lang == 'thai': thai_errors += 1
            elif lang == 'english': eng_errors += 1
            
        suggestions = err.get("suggestions", [])
        
        result_tokens.append({
            'token': token_str, 'lang': lang, 'is_correct': False,
            'suggestions': suggestions if include_suggestions else [],
            'position': start,
            'line_number': _get_line(start, newline_positions),
            'error_type': error_type
        })
        
        final_error_list.append({
            'token': token_str, 'lang': lang,
            'line_number': _get_line(start, newline_positions),
            'suggestions': suggestions if include_suggestions else [],
            'position': start,
            'error_type': error_type
        })
        current_idx = end

    # Add the remaining text after the last error
    if current_idx < len(text):
        suffix = text[current_idx:]
        _count_lang(suffix)
        suffix_tokens = re.split(r'(\s+)', suffix)
        for pt in suffix_tokens:
            if not pt: continue
            lang = 'other'
            if THAI_CHAR_RE.search(pt): lang = 'thai'
            elif ENG_WORD_RE.search(pt): lang = 'english'
            
            result_tokens.append({
                'token': pt, 'lang': lang, 'is_correct': True,
                'suggestions': [], 'position': current_idx,
                'line_number': _get_line(current_idx, newline_positions),
                'error_type': None
            })
            current_idx += len(pt)

    total_checked = thai_count + eng_count
    total_errors = thai_errors + eng_errors + semantic_errors
    error_rate = round(total_errors / total_checked * 100, 2) if total_checked else 0

    return {
        'tokens': result_tokens,
        'errors': final_error_list,
        'summary': {
            'thai_tokens': thai_count,
            'english_tokens': eng_count,
            'total_tokens': total_checked,
            'error_count': total_errors,
            'thai_errors': thai_errors,
            'english_errors': eng_errors,
            'semantic_errors': semantic_errors,
            'error_rate': error_rate
        }
    }


def spellcheck_pages(pages: List[Dict]) -> List[Dict]:
    """ตรวจสอบคำผิดในทุกหน้าของ OCR result"""
    results = []
    for page in pages:
        spell_result = spellcheck_text(page.get('text', ''))
        results.append({**page, 'spell_check': spell_result})
    return results


def _empty_spell_check(text: str) -> Dict[str, Any]:
    """Fallback ในกรณีที่ API error"""
    return {
        'tokens': [{'token': text, 'is_correct': True, 'position': 0}],
        'errors': [],
        'summary': {
            'thai_tokens': 0, 'english_tokens': 0,
            'total_tokens': len(text.split()), 'error_count': 0,
            'thai_errors': 0, 'english_errors': 0,
            'semantic_errors': 0, 'error_rate': 0
        }
    }
