"""
Format Checker - ระบบตรวจสอบรูปแบบเอกสารตามกฎเกณฑ์ที่กำหนดเอง (เช่น การเว้นวรรค)
"""
import re
import os
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

RULES_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'format_rules.json')

DEFAULT_RULES = [
    {
        "id": "rule_space_before_and",
        "name": "เว้นวรรคก่อน \"และ\"",
        "rule_type": "preceded_by_space",
        "pattern": "และ",
        "suggested_fix": " และ",
        "message": "ควรเว้นวรรคหน้าคำว่า \"และ\" เสมอตามหลักเกณฑ์"
    },
    {
        "id": "rule_space_after_etc",
        "name": "เว้นวรรคหลัง \"เป็นต้น\"",
        "rule_type": "followed_by_space",
        "pattern": "เป็นต้น",
        "suggested_fix": "เป็นต้น ",
        "message": "ควรเว้นวรรคหลังคำว่า \"เป็นต้น\" เสมอตามหลักเกณฑ์"
    }
]


def load_format_rules() -> List[Dict[str, Any]]:
    """โหลดกฎเกณฑ์การจัดฟอร์แมตจากไฟล์ JSON"""
    if not os.path.exists(RULES_FILE_PATH):
        # สร้างโฟลเดอร์ data หากยังไม่มี
        os.makedirs(os.path.dirname(RULES_FILE_PATH), exist_ok=True)
        # บันทึกกฎตั้งต้น (Seed)
        save_format_rules(DEFAULT_RULES)
        return DEFAULT_RULES

    try:
        with open(RULES_FILE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading format rules: {e}")
        return DEFAULT_RULES


def save_format_rules(rules: List[Dict[str, Any]]) -> bool:
    """บันทึกกฎเกณฑ์ลงไฟล์ JSON"""
    try:
        os.makedirs(os.path.dirname(RULES_FILE_PATH), exist_ok=True)
        with open(RULES_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving format rules: {e}")
        return False


def _build_line_map(text: str) -> list[int]:
    """สร้างแผนผังบรรทัดสำหรับการคำนวณตำแหน่งบรรทัด"""
    return [i for i, c in enumerate(text) if c == '\n']


def _get_line_number(pos: int, newline_positions: list) -> int:
    """คำนวณหมายเลขบรรทัดจากตำแหน่งตัวอักษร"""
    import bisect
    return bisect.bisect_left(newline_positions, pos) + 1


def check_format_rules(text: str) -> List[Dict[str, Any]]:
    """
    ตรวจสอบความผิดพลาดด้านรูปแบบ (Format errors) ของเอกสาร
    และส่งกลับในรูปแบบลิสต์ของข้อผิดพลาดที่สอดคล้องกับระบบ spellcheck
    """
    if not text.strip():
        return []

    rules = load_format_rules()
    violations = []
    newline_positions = _build_line_map(text)

    for rule in rules:
        rule_type = rule.get("rule_type")
        pattern = rule.get("pattern", "")
        message = rule.get("message", "พบข้อผิดพลาดด้านรูปแบบ")
        suggested_fix = rule.get("suggested_fix", "")

        if not pattern:
            continue

        try:
            if rule_type == "preceded_by_space":
                # ตรวจสอบว่าต้องมีช่องว่างข้างหน้า
                for m in re.finditer(re.escape(pattern), text):
                    start = m.start()
                    if start > 0:
                        preceding_char = text[start - 1]
                        if not preceding_char.isspace():
                            # ละเว้นในกรณีเป็นเครื่องหมายคำพูดหรือสัญลักษณ์เปิดวรรคตอนอื่น ๆ (ถ้าจำเป็น)
                            line_number = _get_line_number(start, newline_positions)
                            violations.append({
                                'token': m.group(),
                                'lang': 'thai',
                                'line_number': line_number,
                                'suggestions': [suggested_fix] if suggested_fix else [f" {pattern}"],
                                'position': start,
                                'error_type': 'format',
                                'message': message
                            })

            elif rule_type == "followed_by_space":
                # ตรวจสอบว่าต้องมีช่องว่างข้างหลัง
                for m in re.finditer(re.escape(pattern), text):
                    end = m.end()
                    if end < len(text):
                        following_char = text[end]
                        if not following_char.isspace():
                            start = m.start()
                            line_number = _get_line_number(start, newline_positions)
                            violations.append({
                                'token': m.group(),
                                'lang': 'thai',
                                'line_number': line_number,
                                'suggestions': [suggested_fix] if suggested_fix else [f"{pattern} "],
                                'position': start,
                                'error_type': 'format',
                                'message': message
                            })

            elif rule_type == "forbidden_pattern":
                # คำต้องห้าม/คำผิดตรงตัว
                for m in re.finditer(re.escape(pattern), text):
                    start = m.start()
                    line_number = _get_line_number(start, newline_positions)
                    violations.append({
                        'token': m.group(),
                        'lang': 'thai',
                        'line_number': line_number,
                        'suggestions': [suggested_fix] if suggested_fix else [],
                        'position': start,
                        'error_type': 'format',
                        'message': message
                    })

            elif rule_type == "custom_regex":
                # ตรวจสอบด้วย Regex กำหนดเอง
                for m in re.finditer(pattern, text):
                    start = m.start()
                    line_number = _get_line_number(start, newline_positions)
                    violations.append({
                        'token': m.group(),
                        'lang': 'thai',
                        'line_number': line_number,
                        'suggestions': [suggested_fix] if suggested_fix else [],
                        'position': start,
                        'error_type': 'format',
                        'message': message
                    })

        except Exception as rule_err:
            logger.error(f"Error executing rule {rule.get('name')}: {rule_err}")

    # เรียงลำดับตามตำแหน่งตัวอักษรเพื่อความเป็นระเบียบ
    violations.sort(key=lambda x: x['position'])
    return violations
