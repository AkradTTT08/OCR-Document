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
    system_prompt = f"""You are a professional Thai and English proofreader. 
Your task is to detect spelling errors, grammatical mistakes, and context errors (e.g., ตากลม, สำรับ vs สำหรับ, their vs there).
Ignore markdown symbols, code, formulas, or standalone numbers.
{custom_instruction}

Return your result STRICTLY in JSON format as a list of errors:
{{
  "errors": [
    {{
      "token": "The exactly misspelled word as it appears in text",
      "suggestions": ["correct_word_1", "correct_word_2"],
      "error_type": "misspelled" // or "semantic"
    }}
  ]
}}
If there are no errors, return {{"errors": []}}.
Do not include any <think> reasoning blocks in your final output, just output the raw JSON."""

    model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash-lite')
    api_key = os.environ.get('GOOGLE_API_KEY', '')

    ai_errors = []
    if not api_key:
        logger.error("GOOGLE_API_KEY is missing! Cannot run spellcheck.")
        return _empty_spell_check(text)

    try:
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=api_key)
        logger.info(f"Calling Gemini ({model_name}) for spellcheck...")
        
        response = client.models.generate_content(
            model=model_name,
            contents=f"Check this text for errors:\n\n{text}",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0,
                response_mime_type="application/json",
            )
        )
        
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
    # Since we dropped PyThaiNLP, we approximate tokenization to build the full array
    newline_positions = _build_line_map(text)
    
    # Split text into tokens (keeping whitespace separated)
    tokens_raw = re.split(r'(\s+)', text)
    
    result_tokens = []
    final_error_list = []
    position = 0
    thai_count = 0
    eng_count = 0
    thai_errors = 0
    eng_errors = 0
    semantic_errors = 0

    # Create a quick lookup for AI errors
    ai_error_map = {err.get("token"): err for err in ai_errors if "token" in err}

    for token in tokens_raw:
        if not token:
            position += len(token)
            continue

        line_number = _get_line(position, newline_positions)

        if not token.strip() or SKIP_RE.match(token):
            result_tokens.append({
                'token': token, 'lang': 'other',
                'is_correct': True, 'suggestions': [],
                'position': position, 'line_number': line_number,
                'error_type': None
            })
            position += len(token)
            continue

        # Language Detection
        if THAI_CHAR_RE.search(token):
            lang = 'thai'
            thai_count += 1
        elif ENG_WORD_RE.search(token):
            lang = 'english'
            eng_count += 1
        else:
            lang = 'other'

        # Check if AI marked this token as an error
        # Match exact token, or clean token
        clean_token = token.strip('.,!?;:()[]{}""''')
        matched_error = ai_error_map.get(token) or ai_error_map.get(clean_token)
        
        is_correct = True
        error_type = None
        suggestions = []

        if matched_error:
            is_correct = False
            error_type = matched_error.get("error_type", "misspelled")
            suggestions = matched_error.get("suggestions", [])
            
            if error_type == "semantic":
                semantic_errors += 1
            else:
                if lang == 'thai':
                    thai_errors += 1
                elif lang == 'english':
                    eng_errors += 1

            final_error_list.append({
                'token': token,
                'lang': lang,
                'line_number': line_number,
                'suggestions': suggestions if include_suggestions else [],
                'position': position,
                'error_type': error_type
            })

        result_tokens.append({
            'token': token,
            'lang': lang,
            'is_correct': is_correct,
            'suggestions': suggestions if include_suggestions else [],
            'position': position,
            'line_number': line_number,
            'error_type': error_type
        })
        position += len(token)

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
