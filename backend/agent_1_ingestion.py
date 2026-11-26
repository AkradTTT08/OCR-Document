import os
import re
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from db_ingestion import get_db_connection
from gemini_utils import call_gemini, get_actual_model_for_usage

logger = logging.getLogger(__name__)


def init_requirements_table():
    """Initializes the structured_requirements table in AIAgentQA."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        conn.autocommit = True
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS structured_requirements (
                req_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                doc_id UUID REFERENCES documents(doc_id) ON DELETE CASCADE,
                req_code VARCHAR(100),
                title VARCHAR(255),
                description TEXT,
                actors VARCHAR(255),
                preconditions TEXT,
                steps JSONB,
                expected_results JSONB,
                ui_elements JSONB,
                api_endpoints JSONB,
                status VARCHAR(50) DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Checked/Created structured_requirements table.")
    except Exception as e:
        logger.error(f"Error initializing structured_requirements table: {e}", exc_info=True)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def _clean_ocr_noise(text: str) -> str:
    """Removes OCR dot-leader repetition and excess whitespace while preserving all real content."""
    if not text:
        return ""
    # Collapse long runs of dots, dashes, underscores, etc. (e.g. table-of-contents dot leaders)
    cleaned = re.sub(r'([.\-_=~*#])\1{5,}', r'\1\1\1', text)
    # Collapse excessive horizontal spaces/tabs
    cleaned = re.sub(r'[ \t]{4,}', '  ', cleaned)
    # Collapse 4+ consecutive newlines
    cleaned = re.sub(r'\n{4,}', '\n\n', cleaned)
    return cleaned.strip()


def _chunk_document_text(text: str, max_chunk_chars: int = 55000, max_chunks: int = 4) -> list:
    """Splits a long SRS document cleanly on headings/newlines into bounded chunks."""
    if len(text) <= max_chunk_chars:
        return [text]

    chunks = []
    start = 0
    total_len = len(text)
    while start < total_len and len(chunks) < max_chunks:
        end = min(start + max_chunk_chars, total_len)
        if end < total_len:
            # Prefer splitting on a markdown heading or double newline near the boundary
            window = text[start:end]
            split_pos = window.rfind("\n## ")
            if split_pos < int(max_chunk_chars * 0.55):
                split_pos = window.rfind("\n# ")
            if split_pos < int(max_chunk_chars * 0.55):
                split_pos = window.rfind("\n\n")
            if split_pos < int(max_chunk_chars * 0.55):
                split_pos = window.rfind("\n")
            if split_pos > 0:
                end = start + split_pos
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def _parse_json_array(raw_text: str) -> list:
    """Robustly extracts a JSON array from LLM output, recovering complete objects even if truncated."""
    if not raw_text:
        return []
    s = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\[[\s\S]*\])\s*```", s)
    if fence_match:
        s = fence_match.group(1).strip()
    else:
        first_bracket = s.find("[")
        last_bracket = s.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            s = s[first_bracket:last_bracket + 1]
        elif first_bracket != -1:
            s = s[first_bracket:]

    try:
        parsed = json.loads(s, strict=False)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        # Incremental object recovery for truncated or slightly malformed JSON arrays
        decoder = json.JSONDecoder(strict=False)
        recovered = []
        idx = 0
        n = len(s)
        while idx < n:
            brace = s.find("{", idx)
            if brace == -1:
                break
            try:
                obj, end_idx = decoder.raw_decode(s, brace)
                if isinstance(obj, dict) and obj.get("title"):
                    recovered.append(obj)
                idx = max(end_idx, brace + 1)
            except Exception:
                idx = brace + 1
        return recovered


def extract_requirements_from_text(text: str, project_id: str, doc_id):
    """
    Uses Gemini to extract accurate, Thai-language structured requirements from full document text
    using OCR-noise cleaning and section-aware chunking.
    """
    if not text or not text.strip():
        return False, "Empty text provided"

    clean_text = _clean_ocr_noise(text)
    if not clean_text:
        return False, "Document contained no readable text after cleaning"

    chunks = _chunk_document_text(clean_text, max_chunk_chars=55000, max_chunks=4)
    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    extracted_all = []
    seen_titles = set()

    def _extract_single_chunk(chunk_idx: int, chunk: str):
        part_note = (
            f"(ส่วนที่ {chunk_idx} จาก {len(chunks)} ของเอกสาร)"
            if len(chunks) > 1
            else "(ทั้งฉบับ)"
        )
        prompt = f"""คุณคือ Senior QA System Analyst & Test Architect ผู้เชี่ยวชาญการวิเคราะห์เอกสาร SRS/Requirement ของระบบ Enterprise
งานของคุณคือสกัดข้อกำหนดความต้องการทางธุรกิจ (Functional / Business Requirements) และเงื่อนไขการทดสอบที่ชัดเจนจากเอกสารต้นฉบับ {part_note}

กฎสำคัญที่ต้องปฏิบัติอย่างเคร่งครัด:
1. **ภาษา**: เขียน `title`, `description`, `actors`, `preconditions`, `steps` และ `expected_results` เป็น **ภาษาไทยทั้งหมดตามเอกสารต้นฉบับ** (คงคำศัพท์เทคนิค ชื่อฟิลด์ ชื่อปุ่ม รหัสหน้าจอ หรือ API Path เป็นภาษาอังกฤษตามที่ปรากฏจริงในเอกสาร)
2. **อ้างอิงจากเนื้อหาจริงเท่านั้น**: ห้ามแต่งเติมฟีเจอร์ที่ไม่มีในเอกสาร และห้ามเขียนกว้างๆ เช่น "ตามหัวข้อ 5" — ให้ระบุเงื่อนไข ฟิลด์ หรือกฎธุรกิจจริงที่พบในเอกสาร
3. **Steps และ Expected Results ต้องครบถ้วน**:
   - `steps` ต้องระบุลำดับการทำงานของ User/System อย่างน้อย 2-6 ขั้นตอนที่นำไปเขียน Automate Test ได้จริง
   - `expected_results` ต้องระบุผลลัพธ์ที่ตรวจสอบได้จริง (ทั้งกรณีสำเร็จและการแจ้งเตือน/Validation เมื่อข้อมูลไม่ถูกต้อง)
4. **ไม่ซ้ำซ้อนและกระชับ**: รวมรายละเอียดย่อยของหน้าจอ/ฟีเจอร์เดียวกันไว้ใน Requirement เดียวกัน (ไม่เกิน 10 ข้อต่อส่วน, `description` กระชับ 2-3 ประโยค)

ตอบกลับเป็น JSON Array เท่านั้น (ห้ามใส่คำอธิบายนอก JSON) ตามโครงสร้างนี้:
[
  {{
    "req_code": "รหัส Requirement จากเอกสาร หรือ REQ-001",
    "title": "ชื่อหัวข้อ Requirement ภาษาไทยที่กระชับชัดเจน (ไม่เกิน 120 ตัวอักษร)",
    "description": "คำอธิบายรายละเอียดความต้องการและกฎธุรกิจ (Business Rules) จากเอกสารจริง",
    "actors": "ผู้ใช้งานหรือบทบาทที่เกี่ยวข้อง เช่น เจ้าหน้าที่คีย์ข้อมูล, ผู้ดูแลระบบ",
    "preconditions": "เงื่อนไขเริ่มต้นก่อนทำรายการ เช่น เข้าสู่ระบบและมีสิทธิ์ใช้งานเมนู...",
    "steps": ["1. ขั้นตอนที่ 1...", "2. ขั้นตอนที่ 2..."],
    "expected_results": ["ผลลัพธ์ที่คาดหวัง 1...", "ผลลัพธ์ที่คาดหวัง 2..."],
    "ui_elements": ["ชื่อปุ่ม/ฟิลด์/ตารางที่ระบุในเอกสาร"],
    "api_endpoints": ["METHOD /api/... (ถ้ามีในเอกสาร มิฉะนั้นใส่ [])"]
  }}
]

เนื้อหาเอกสารต้นฉบับ {part_note}:
{chunk}
"""
        raw_json, usage_metadata = call_gemini(prompt, model_name=model_name)

        if usage_metadata:
            try:
                from db_ingestion import log_api_usage
                actual_model = get_actual_model_for_usage(model_name)
                log_api_usage("Agent_1_Ingestion", actual_model, usage_metadata)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Agent 1: {log_err}")

        return chunk_idx, _parse_json_array(raw_json)

    try:
        chunk_results = {}
        if len(chunks) == 1:
            idx, items = _extract_single_chunk(1, chunks[0])
            chunk_results[idx] = items
        else:
            with ThreadPoolExecutor(max_workers=min(3, len(chunks))) as pool:
                futures = [
                    pool.submit(_extract_single_chunk, i, ch)
                    for i, ch in enumerate(chunks, 1)
                ]
                for fut in as_completed(futures):
                    try:
                        idx, items = fut.result()
                        chunk_results[idx] = items
                    except Exception as chunk_err:
                        logger.warning(f"Agent 1 chunk extraction warning: {chunk_err}")

        for idx in sorted(chunk_results.keys()):
            for req in chunk_results[idx]:
                if not isinstance(req, dict):
                    continue
                title = str(req.get("title") or "").strip()
                if not title:
                    continue
                norm_title = re.sub(r'\s+', ' ', title.lower())
                if norm_title in seen_titles:
                    continue
                seen_titles.add(norm_title)
                extracted_all.append(req)

        if not extracted_all:
            return False, "ไม่พบรายการ Requirement ที่สามารถสกัดได้จากเอกสารนี้"

        # Save to DB (replace previous requirements for this doc_id to avoid stale duplicates)
        conn = get_db_connection()
        cursor = conn.cursor()

        if doc_id:
            cursor.execute("DELETE FROM structured_requirements WHERE doc_id = %s;", (doc_id,))

        saved_ids = []
        for idx, req in enumerate(extracted_all, 1):
            req_code = str(req.get("req_code") or f"REQ-{idx:03d}").strip()[:100]
            if not req_code or req_code.upper().startswith("REQ-"):
                req_code = f"REQ-{idx:03d}"

            steps = req.get("steps") if isinstance(req.get("steps"), list) else []
            expected = req.get("expected_results") if isinstance(req.get("expected_results"), list) else []
            ui_elems = req.get("ui_elements") if isinstance(req.get("ui_elements"), list) else []
            apis = req.get("api_endpoints") if isinstance(req.get("api_endpoints"), list) else []

            cursor.execute("""
                INSERT INTO structured_requirements
                (project_id, doc_id, req_code, title, description, actors, preconditions, steps, expected_results, ui_elements, api_endpoints)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
                RETURNING req_id
            """, (
                project_id,
                doc_id,
                req_code,
                str(req.get("title") or "").strip()[:255],
                str(req.get("description") or "").strip(),
                str(req.get("actors") or "").strip()[:255],
                str(req.get("preconditions") or "").strip(),
                json.dumps(steps, ensure_ascii=False),
                json.dumps(expected, ensure_ascii=False),
                json.dumps(ui_elems, ensure_ascii=False),
                json.dumps(apis, ensure_ascii=False)
            ))
            saved_ids.append(str(cursor.fetchone()[0]))

        conn.commit()
        cursor.close()
        conn.close()

        return True, f"สกัดและบันทึก {len(saved_ids)} Requirements สำเร็จ (จาก {len(chunks)} ช่วงเอกสาร)"

    except Exception as e:
        logger.error(f"Failed to extract requirements: {e}", exc_info=True)
        return False, str(e)
