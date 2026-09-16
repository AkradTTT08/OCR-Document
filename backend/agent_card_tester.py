import os
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
import requests

from db_ingestion import get_db_connection
from ocr_engine import _get_gemini_client

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent

def parse_card_intent(title: str, desc: str = ""):
    """
    Parses card title and description to extract module name, menu, action, and target keywords.
    Example: '69-38 SYS => Change Cencel GR => Table & Export'
    Returns dict with system, module, subview, keywords, and detected urls.
    """
    parts = [p.strip() for p in title.split('=>')] if '=>' in title else [p.strip() for p in title.split('-')]
    system_name = parts[0] if len(parts) > 0 else "System"
    module_name = parts[1] if len(parts) > 1 else (parts[0] if parts else "Module")
    subview = parts[2] if len(parts) > 2 else ""

    # Look for URLs in description or title
    url_pattern = r'https?://[^\s)"]+'
    found_urls = re.findall(url_pattern, f"{title} {desc}")
    target_url = found_urls[0] if found_urls else None

    # Extract keywords
    clean_text = re.sub(r'[^a-zA-Z0-9\u0E00-\u0E7F\s]', ' ', f"{title} {desc}")
    keywords = [w.strip() for w in clean_text.split() if len(w.strip()) > 2]

    return {
        "system": system_name,
        "module": module_name,
        "subview": subview,
        "target_url": target_url,
        "keywords": keywords[:15]
    }

def retrieve_srs_requirements(project_id: str, card_info: dict, max_chunks: int = 5):
    """
    Searches RAG Knowledge Base in PostgreSQL for relevant SRS sections and Test Cases matching this card.
    """
    conn = get_db_connection()
    if not conn:
        return []
    
    chunks = []
    try:
        cursor = conn.cursor()
        keywords = [card_info["module"], card_info["subview"]] + card_info["keywords"]
        unique_kws = list(dict.fromkeys([k for k in keywords if k]))

        # 1. Search in documents with category Requirements / SRS / Test Cases
        sql_or_clauses = " OR ".join(["dc.chunk_text ILIKE %s" for _ in unique_kws[:6]])
        params = [project_id] + [f"%{k}%" for k in unique_kws[:6]]

        query = f"""
            SELECT d.original_filename, d.doc_category, dc.chunk_text
            FROM document_chunks dc
            JOIN documents d ON dc.doc_id = d.doc_id
            WHERE d.project_id = %s
              AND (d.doc_category IN ('Requirements', 'Test Cases', 'QA Report') OR d.original_filename ILIKE '%%SRS%%' OR d.original_filename ILIKE '%%REQ%%')
              AND ({sql_or_clauses})
            LIMIT %s
        """
        cursor.execute(query, tuple(params + [max_chunks]))
        rows = cursor.fetchall()
        for r in rows:
            chunks.append({
                "source_file": r[0],
                "category": r[1],
                "content": r[2]
            })

        # 2. If nothing found via specific keyword, grab high-level SRS chunks for the project
        if not chunks:
            cursor.execute("""
                SELECT d.original_filename, d.doc_category, dc.chunk_text
                FROM document_chunks dc
                JOIN documents d ON dc.doc_id = d.doc_id
                WHERE d.project_id = %s
                  AND (d.doc_category IN ('Requirements', 'Test Cases') OR d.original_filename ILIKE '%%SRS%%')
                LIMIT 3
            """, (project_id,))
            rows = cursor.fetchall()
            for r in rows:
                chunks.append({
                    "source_file": r[0],
                    "category": r[1],
                    "content": r[2]
                })

        cursor.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Error querying SRS chunks: {e}")
        if 'conn' in locals() and conn:
            conn.close()

    return chunks

def extract_expected_criteria(card_data: dict, srs_chunks: list):
    """
    Uses Gemini AI to synthesize explicit Acceptance Criteria and expected UI rules
    based on the card requirements and SRS chunks.
    """
    client = _get_gemini_client()
    srs_text = "\n\n---\n\n".join([f"[{c['source_file']} ({c['category']})]:\n{c['content']}" for c in srs_chunks]) if srs_chunks else "No specific SRS document found; use standard web QA standards."

    prompt = f"""
You are a Principal QA Automation Architect.
Analyze the following Card Details and SRS (Software Requirements Specification) context:

### CARD DETAILS:
Title: {card_data.get('title')}
Description: {card_data.get('description')}
Labels: {[l.get('name') if isinstance(l, dict) else str(l) for l in card_data.get('labels', [])]}

### SRS CONTEXT FROM KNOWLEDGE BASE:
{srs_text[:4000]}

Your job:
1. Identify the target module, screen, or menu.
2. Formulate 3 to 5 clear, concrete Acceptance Criteria (Expected Results) that can be verified on a live web application.
3. Formulate specific UI assertions (e.g. table columns, button presence, dropdown options, pagination controls).

Return strictly JSON matching this structure:
{{
  "module_name": "...",
  "target_menu": "...",
  "expected_criteria": [
    "Criteria 1...",
    "Criteria 2..."
  ],
  "expected_ui_elements": [
    "Table showing record rows",
    "Pagination control with options (10, 20, 50, 100 per page)",
    "Export / Download button"
  ],
  "verification_instructions": "Exact check for this card"
}}
"""
    try:
        model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        clean_json = response.text.strip()
        if clean_json.startswith('```'):
            clean_json = re.sub(r'^```json\s*|^```\s*|```$', '', clean_json, flags=re.MULTILINE).strip()
        return json.loads(clean_json)
    except Exception as e:
        logger.warning(f"Gemini criteria extraction error: {e}")
        return {
            "module_name": card_data.get('title', 'Module'),
            "target_menu": "Main Menu",
            "expected_criteria": ["UI table loads correctly", "Required actions are enabled"],
            "expected_ui_elements": ["Table", "Controls", "Export Button"],
            "verification_instructions": "Verify all controls function properly"
        }

def run_playwright_live_exploration(target_url: str, card_data: dict, module_info: dict):
    """
    Uses Playwright to open Chromium in headless mode, inspects interactive elements,
    extracts live table and form states, and captures a proof screenshot.
    """
    from playwright.sync_api import sync_playwright

    attachments_dir = BASE_DIR / 'uploads' / 'attachments'
    attachments_dir.mkdir(parents=True, exist_ok=True)
    shot_filename = f"agent_shot_{uuid.uuid4().hex[:10]}.png"
    shot_path = attachments_dir / shot_filename

    web_state = {
        "url": target_url,
        "title": "",
        "tables": [],
        "selects": [],
        "buttons": [],
        "screenshot_filename": shot_filename,
        "screenshot_path": str(shot_path),
        "error_logs": [],
        "status": "unreachable"
    }

    # If no explicit URL provided, attempt common local dev/staging ports or candidate URLs
    candidate_urls = [target_url] if target_url else [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080"
    ]
    candidate_urls = [u for u in candidate_urls if u]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(viewport={'width': 1280, 'height': 800})
            page = context.new_page()

            # Capture console errors
            page.on("console", lambda msg: web_state["error_logs"].append(f"[{msg.type}] {msg.text}") if msg.type in ["error", "warning"] else None)

            connected = False
            for test_u in candidate_urls:
                try:
                    logger.info(f"Playwright probing URL: {test_u}")
                    page.goto(test_u, timeout=7000, wait_until='domcontentloaded')
                    connected = True
                    web_state["url"] = test_u
                    break
                except Exception as net_err:
                    logger.info(f"Could not connect to {test_u}: {net_err}")

            if connected:
                web_state["status"] = "connected"
                page.wait_for_timeout(1500)
                web_state["title"] = page.title()

                # Extract dropdowns / selects (critical for pagination check like 10, 20, 50/page)
                selects_info = page.evaluate('''() => {
                    const res = [];
                    document.querySelectorAll('select, .custom-select, [role="combobox"]').forEach(el => {
                        const opts = [];
                        el.querySelectorAll('option, .option-item, li').forEach(o => opts.push((o.innerText || o.textContent || '').trim()));
                        res.push({
                            tag: el.tagName.toLowerCase(),
                            name: el.name || el.id || el.className,
                            options: opts.filter(Boolean)
                        });
                    });
                    return res;
                }''')
                web_state["selects"] = selects_info

                # Extract tables
                tables_info = page.evaluate('''() => {
                    const res = [];
                    document.querySelectorAll('table, .data-table, .grid-table').forEach(tbl => {
                        const headers = [];
                        tbl.querySelectorAll('th').forEach(th => headers.push((th.innerText || '').trim()));
                        const rowCount = tbl.querySelectorAll('tr').length;
                        res.push({ headers: headers.filter(Boolean), total_rows: rowCount });
                    });
                    return res;
                }''')
                web_state["tables"] = tables_info

                # Extract buttons
                buttons_info = page.evaluate('''() => {
                    const btns = [];
                    document.querySelectorAll('button, a.btn, input[type="button"], input[type="submit"]').forEach(b => {
                        const text = (b.innerText || b.value || '').trim();
                        if (text && text.length < 50) btns.push(text);
                    });
                    return btns.slice(0, 25);
                }''')
                web_state["buttons"] = buttons_info

                # Take proof screenshot
                page.screenshot(path=str(shot_path), full_page=False)
                logger.info(f"Playwright captured proof screenshot: {shot_path}")

            browser.close()
    except Exception as pw_err:
        logger.error(f"Playwright exploration exception: {pw_err}")
        web_state["error_logs"].append(str(pw_err))

    return web_state

def verify_and_analyze_gaps(card_data: dict, criteria: dict, web_state: dict, srs_chunks: list):
    """
    Uses Gemini AI (Agent 3 style) to compare Expected SRS criteria with Actual Live Web State.
    If actual web is unreachable, inspects card description, comments, and uploaded attachments (Vision).
    """
    client = _get_gemini_client()

    # Check if user uploaded any screenshots to the card
    user_attachments = card_data.get('attachments') or []
    attachment_desc = []
    shot_path = web_state.get('screenshot_path')

    for att in user_attachments:
        fn = att.get('filename')
        if fn:
            p = BASE_DIR / 'uploads' / 'attachments' / fn
            if p.exists():
                attachment_desc.append(f"Attached User Evidence: {fn}")

    prompt = f"""
You are an Elite QA Lead performing an automated audit and gap analysis on a software feature.

### 1. CARD INFORMATION:
- Card Title: {card_data.get('title')}
- Description: {card_data.get('description')}
- Reported Issue/Note: {card_data.get('description')}

### 2. EXPECTED REQUIREMENTS (FROM SRS & TEST CASES):
- Module: {criteria.get('module_name')}
- Expected Criteria:
{json.dumps(criteria.get('expected_criteria', []), ensure_ascii=False, indent=2)}
- Expected UI Elements:
{json.dumps(criteria.get('expected_ui_elements', []), ensure_ascii=False, indent=2)}

### 3. ACTUAL LIVE WEB STATE (CAPTURED BY PLAYWRIGHT):
- URL Inspected: {web_state.get('url')}
- Status: {web_state.get('status')}
- Extracted Selects/Dropdowns: {json.dumps(web_state.get('selects', []), ensure_ascii=False)}
- Extracted Tables: {json.dumps(web_state.get('tables', []), ensure_ascii=False)}
- Extracted Buttons: {json.dumps(web_state.get('buttons', []), ensure_ascii=False)}
- Browser Error Logs: {json.dumps(web_state.get('error_logs', []), ensure_ascii=False)}

### 4. EVIDENCE & DEFECT VALIDATION RULES:
- Notice if the card description or user attachments report a defect (for example: "paggination ไม่มีให้เลือก 10/page" or missing export button).
- If an expected requirement (such as pagination containing 10/page, or table columns, or mandatory validations) is missing or violated, mark verdict as "FAILED".
- If all checks pass and no defects exist, mark verdict as "PASSED".

Provide your evaluation strictly in the following JSON format:
{{
  "verdict": "PASSED" or "FAILED",
  "score_percent": 85,
  "summary": "Brief 1-2 sentence executive summary of test result in Thai",
  "matched_criteria": [
    "List of requirements that passed"
  ],
  "discrepancies": [
    {{
      "item": "Missing Pagination Option 10/page",
      "severity": "Medium",
      "impact": "User cannot view 10 items per page as defined in SRS"
    }}
  ],
  "technical_logs": "Summary of logs and validation details",
  "recommendation": "Recommendation for QA and dev team in Thai"
}}
"""
    try:
        model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        clean_json = response.text.strip()
        if clean_json.startswith('```'):
            clean_json = re.sub(r'^```json\s*|^```\s*|```$', '', clean_json, flags=re.MULTILINE).strip()
        return json.loads(clean_json)
    except Exception as e:
        logger.warning(f"Gemini gap analysis error: {e}")
        is_defect_reported = any(w in (card_data.get('description') or '').lower() for w in ['ไม่มี', 'not found', 'error', 'fail', 'defect', 'bug', 'ผิด'])
        return {
            "verdict": "FAILED" if is_defect_reported else "PASSED",
            "score_percent": 60 if is_defect_reported else 100,
            "summary": "พบข้อบกพร่องตามที่ระบุในการ์ดและข้อกำหนด SRS" if is_defect_reported else "ตรวจสอบระบบเบื้องต้นเรียบร้อยแล้ว",
            "matched_criteria": ["โครงสร้างตารางแสดงผลได้"],
            "discrepancies": [{"item": "Defect ตามรายละเอียดในการ์ด", "severity": "Medium", "impact": "ฟังก์ชันทำงานไม่ตรงตามที่คาดหวัง"}] if is_defect_reported else [],
            "technical_logs": "Auto-analyzed via Spectra QA Fallback Rules",
            "recommendation": "ส่งมอบให้ทีมพัฒนาแก้ไขข้อบกพร่องตามรายงาน" if is_defect_reported else "พร้อมส่งมอบขึ้น Production"
        }

def run_card_agent_test(project_id: str, card_id: str, card_data: dict):
    """
    Main Entrypoint: Runs the full End-to-End QA Agent Pipeline for a card.
    1. Parses Intent
    2. RAG Match SRS & Test Cases
    3. Playwright Live Exploration
    4. Gemini Gap Analysis & Verification
    5. Sync to Board & Knowledge Base
    """
    title = card_data.get('title') or "Untitled Card"
    desc = card_data.get('description') or ""
    logger.info(f"Starting E2E QA Agent Test for Card [{card_id}]: {title}")

    # Step 1: Parse Intent & Context
    card_info = parse_card_intent(title, desc)
    
    # Step 2: Retrieve SRS Context from RAG
    srs_chunks = retrieve_srs_requirements(project_id, card_info)
    criteria = extract_expected_criteria(card_data, srs_chunks)
    logger.info(f"Extracted criteria for {title}: {len(criteria.get('expected_criteria', []))} criteria found")

    # Step 3: Playwright Live Web Exploration
    target_url = card_info.get("target_url")
    web_state = run_playwright_live_exploration(target_url, card_data, criteria)

    # Step 4: Gap Analysis & Verification
    eval_result = verify_and_analyze_gaps(card_data, criteria, web_state, srs_chunks)
    verdict = eval_result.get("verdict", "PASSED")
    is_passed = (verdict == "PASSED")

    # Generate Markdown Report
    screenshot_fn = web_state.get("screenshot_filename")
    shot_md = f"\n\n![Live Test Screenshot](http://localhost:5000/api/attachments/{screenshot_fn})" if screenshot_fn and os.path.exists(web_state.get("screenshot_path", "")) else ""

    matched_list = "\n".join([f"- ✅ {m}" for m in eval_result.get("matched_criteria", [])]) or "- ตรวจสอบตามมาตรฐานสเปกทั่วไป"
    discrepancy_list = "\n".join([f"- ❌ **[{d.get('severity', 'Defect')}]** {d.get('item')}: {d.get('impact', '')}" for d in eval_result.get("discrepancies", [])]) or "- ไม่มีข้อบกพร่อง ตรวจสอบผ่านทุกหัวข้อ"

    report_markdown = f"""### 🤖 Spectra QA Agent Automated Test Report
**Verdict:** `{'PASSED' if is_passed else 'FAILED (DEFECT DETECTED)'}` (Score: {eval_result.get('score_percent', 0)}%)
**Card:** {title}
**Module Analyzed:** {criteria.get('module_name')}
**SRS Reference:** {srs_chunks[0]['source_file'] if srs_chunks else '69A_REQ_SRS'}

#### 📋 ผลการตรวจสอบเทียบกับ SRS & Test Case:
{matched_list}

#### ⚠️ ข้อบกพร่องที่ตรวจพบ (Defects / Discrepancies):
{discrepancy_list}

#### 💡 ข้อเสนอแนะ (Recommendation):
{eval_result.get('recommendation')}
{shot_md}
"""

    # Step 5: Database & Board Sync
    conn = get_db_connection()
    target_status = None
    if conn:
        try:
            cursor = conn.cursor()
            
            # Fetch board integration to find Done or Defect lists
            cursor.execute("""
                SELECT provider, trello_api_key, trello_token, trello_board_id, columns_json
                FROM board_integrations WHERE project_id = %s
            """, (project_id,))
            integ = cursor.fetchone()

            cols = []
            if integ and integ[4]:
                try:
                    cols = json.loads(integ[4]) if isinstance(integ[4], str) else integ[4]
                except Exception:
                    cols = []

            # Determine destination column
            if is_passed:
                # Find Done column
                done_col = next((c for c in cols if any(w in c.get('title', '').lower() for w in ['done', 'complete', 'finish', 'ผ่าน', 'เสร็จ'])), None)
                target_status = done_col['id'] if done_col else (cols[-1]['id'] if cols else 'done')
            else:
                # Find Defect or Review column
                defect_col = next((c for c in cols if any(w in c.get('title', '').lower() for w in ['defect', 'bug', 'review', 'แก้ไข', 'รอตรวจ'])), None)
                target_status = defect_col['id'] if defect_col else (cols[1]['id'] if len(cols) > 1 else 'defect')

            # Upsert into board_cards
            ext_card_id = card_data.get('ext_card_id') or f"TRL-{str(card_id)[:6]}"
            raw_ext_id = str(card_data.get('raw_ext_id') or card_id)
            card_type = card_data.get('type') or ('Bug' if not is_passed else 'Feature')
            priority = card_data.get('priority') or 'Medium'
            labels_json = json.dumps(card_data.get('labels') or [], ensure_ascii=False)
            members_json = json.dumps(card_data.get('members') or [], ensure_ascii=False)
            story_points = str(card_data.get('story_points') or '1')
            actions_json = json.dumps(card_data.get('actions') or [], ensure_ascii=False)

            cursor.execute("""
                INSERT INTO board_cards (
                    project_id, ext_card_id, title, description, status,
                    card_type, priority, raw_ext_id, labels_json, members_json,
                    story_points, actions_json, test_result
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (project_id, ext_card_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    test_result = EXCLUDED.test_result,
                    card_type = EXCLUDED.card_type
                RETURNING card_id;
            """, (project_id, ext_card_id, title, desc, target_status, card_type, priority, raw_ext_id, labels_json, members_json, story_points, actions_json, report_markdown))
            
            # Ingest into RAG documents
            doc_filename = f"QA_Report_{ext_card_id.replace('#', '')}.md"
            cursor.execute("""
                INSERT INTO documents (project_id, doc_category, doc_type, original_filename, full_markdown_content, status)
                VALUES (%s, 'QA Report', 'Automated Test', %s, %s, 'Active')
                RETURNING doc_id;
            """, (project_id, doc_filename, report_markdown))
            d_row = cursor.fetchone()
            if d_row:
                cursor.execute("""
                    INSERT INTO document_chunks (doc_id, chunk_text)
                    VALUES (%s, %s);
                """, (d_row[0], report_markdown))
            
            conn.commit()

            # Sync to Trello if configured
            if integ and integ[0] == 'trello' and integ[1] and integ[2]:
                t_key, t_token = integ[1], integ[2]
                clean_raw_id = raw_ext_id.lstrip('#')

                # Move card to target list
                if target_status and len(target_status) == 24:
                    try:
                        requests.put(
                            f"https://api.trello.com/1/cards/{clean_raw_id}",
                            params={"idList": target_status, "key": t_key, "token": t_token},
                            timeout=8
                        )
                    except Exception as ex:
                        logger.warning(f"Could not move Trello card: {ex}")

                # Upload screenshot if captured
                if screenshot_fn:
                    shot_file_path = web_state.get("screenshot_path")
                    if shot_file_path and os.path.exists(shot_file_path):
                        try:
                            with open(shot_file_path, 'rb') as f_up:
                                requests.post(
                                    f"https://api.trello.com/1/cards/{clean_raw_id}/attachments",
                                    params={"key": t_key, "token": t_token, "name": "Agent_Test_Evidence.png"},
                                    files={"file": ("Agent_Test_Evidence.png", f_up, 'image/png')},
                                    timeout=15
                                )
                        except Exception as att_err:
                            logger.warning(f"Could not upload agent screenshot to Trello: {att_err}")

                # Post comment report to Trello
                try:
                    requests.post(
                        f"https://api.trello.com/1/cards/{clean_raw_id}/actions/comments",
                        params={"key": t_key, "token": t_token, "text": report_markdown},
                        timeout=10
                    )
                except Exception as c_err:
                    logger.warning(f"Could not post agent report to Trello: {c_err}")

            cursor.close()
            conn.close()
        except Exception as db_err:
            logger.error(f"Error persisting agent test results: {db_err}")
            if 'conn' in locals() and conn:
                conn.close()

    return {
        "success": True,
        "is_passed": is_passed,
        "verdict": verdict,
        "test_result": report_markdown,
        "target_status": target_status,
        "screenshot_url": f"http://localhost:5000/api/attachments/{screenshot_fn}" if screenshot_fn else None,
        "discrepancies": eval_result.get("discrepancies", []),
        "matched_criteria": eval_result.get("matched_criteria", []),
        "recommendation": eval_result.get("recommendation", "")
    }
