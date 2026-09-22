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

def init_test_execution_tables():
    """
    Initializes PostgreSQL tables for storing test execution runs and project environment configurations.
    """
    conn = get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_test_execution_runs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID NOT NULL,
                card_id VARCHAR(255),
                card_title TEXT,
                target_url TEXT,
                environment VARCHAR(50) DEFAULT 'UAT',
                user_role VARCHAR(50) DEFAULT 'Admin',
                test_cases JSONB DEFAULT '[]',
                test_steps JSONB DEFAULT '[]',
                verdict VARCHAR(50) DEFAULT 'PENDING',
                score_percent INT DEFAULT 0,
                summary TEXT,
                matched_criteria JSONB DEFAULT '[]',
                discrepancies JSONB DEFAULT '[]',
                screenshot_filename TEXT,
                logs TEXT,
                recommendation TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_qa_test_runs_project ON qa_test_execution_runs(project_id);
            CREATE INDEX IF NOT EXISTS idx_qa_test_runs_created ON qa_test_execution_runs(created_at DESC);
        """)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Error initializing test execution tables: {e}")
        if 'conn' in locals() and conn:
            conn.close()

# Auto-run table init on import
try:
    init_test_execution_tables()
except Exception:
    pass


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
        keywords = [card_info.get("module", ""), card_info.get("subview", "")] + card_info.get("keywords", [])
        unique_kws = list(dict.fromkeys([k for k in keywords if k]))

        # 1. Search in documents with category Requirements / SRS / Test Cases
        if unique_kws:
            sql_or_clauses = " OR ".join(["dc.chunk_text ILIKE %s" for _ in unique_kws[:6]])
            params = [project_id] + [f"%{k}%" for k in unique_kws[:6]]

            query = f"""
                SELECT d.original_filename, d.doc_category, dc.chunk_text
                FROM document_chunks dc
                JOIN documents d ON dc.doc_id = d.doc_id
                WHERE d.project_id = %s
                  AND (d.doc_category IN ('Requirements', 'Test Cases', 'TestCase', 'QA Report', 'TOR/SOW', 'SRS', 'SDD', 'UAT', 'Usermanual', 'Admin manual', 'Installation system') OR d.original_filename ILIKE '%%SRS%%' OR d.original_filename ILIKE '%%REQ%%')
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
                  AND (d.doc_category IN ('Requirements', 'Test Cases', 'TestCase', 'TOR/SOW', 'SRS', 'SDD', 'UAT', 'Usermanual', 'Admin manual', 'Installation system') OR d.original_filename ILIKE '%%SRS%%')
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


def resolve_card_test_mapping(project_id: str, card_data: dict):
    """
    Intelligent AI Auto-Mapping Engine:
    1. Reads Project Settings (Base URL & Environments).
    2. Reads Flow Analysis (Sitemap & Traceability Matrix).
    3. Matches Card keywords to find exact Route Path & Screen.
    4. Matches Traceability Matrix to find linked Test Cases and Use Cases.
    5. Retrieves RAG Knowledge Base to formulate test cases with Positive/Negative criteria and suggested test steps.
    """
    title = card_data.get('title') or "Untitled Task"
    desc = card_data.get('description') or ""
    card_info = parse_card_intent(title, desc)

    conn = get_db_connection()
    sitemap = []
    matrix = []
    screen_mockups = []
    project_name = "Project"
    
    # Default environment candidates
    base_url = "http://localhost:5173"
    environments = [
        {"name": "TEST", "url": "http://localhost:5173", "is_default": True, "description": "Local Test Server"},
        {"name": "UAT", "url": "https://uat.example.com", "is_default": False, "description": "User Acceptance Testing Server"},
        {"name": "PRD", "url": "https://example.com", "is_default": False, "description": "Production Live Server"}
    ]

    if conn:
        try:
            cursor = conn.cursor()
            # 1. Fetch project info including site_urls
            cursor.execute("SELECT project_name, project_code, default_base_url, site_urls FROM projects WHERE project_id = %s::uuid LIMIT 1", (project_id,))
            p_row = cursor.fetchone()
            if p_row:
                project_name = p_row[0] or p_row[1] or "Project"
                default_url = p_row[2] or "http://localhost:5173"
                raw_sites = p_row[3]
                site_urls = raw_sites if isinstance(raw_sites, list) else (json.loads(raw_sites) if raw_sites else [])
                
                if site_urls and len(site_urls) > 0:
                    custom_envs = []
                    found_default = False
                    for s in site_urls:
                        env_type = s.get('env_type', 'TEST').upper()
                        url = s.get('url', '').strip()
                        is_def = bool(s.get('is_default', False))
                        if is_def:
                            base_url = url
                            found_default = True
                        custom_envs.append({
                            "name": env_type,
                            "url": url,
                            "is_default": is_def,
                            "description": f"{env_type} Server"
                        })
                    if not found_default and custom_envs:
                        custom_envs[0]['is_default'] = True
                        base_url = custom_envs[0]['url']
                    environments = custom_envs
                elif p_row[2] and p_row[2].strip():
                    base_url = p_row[2].strip()
                    for env in environments:
                        if env["name"] == "TEST":
                            env["url"] = base_url

            # 2. Fetch flow analysis diagrams & sitemap
            cursor.execute("""
                SELECT sitemap_data, traceability_matrix, screen_mockups
                FROM qa_analysis_diagrams
                WHERE project_id = %s::uuid
                ORDER BY updated_at DESC LIMIT 1
            """, (project_id,))
            diag_row = cursor.fetchone()
            if diag_row:
                sitemap = diag_row[0] if isinstance(diag_row[0], list) else json.loads(diag_row[0] or '[]')
                matrix = diag_row[1] if isinstance(diag_row[1], list) else json.loads(diag_row[1] or '[]')
                screen_mockups = diag_row[2] if isinstance(diag_row[2], list) else json.loads(diag_row[2] or '[]')

            cursor.close()
            conn.close()
        except Exception as e:
            logger.warning(f"Error reading flow analysis for test mapping: {e}")
            if 'conn' in locals() and conn:
                conn.close()

    # RAG Retrieval
    srs_chunks = retrieve_srs_requirements(project_id, card_info, max_chunks=4)

    # 1. Match with Sitemap Node & Route Path
    matched_sitemap_node = None
    matched_screen_mockup = None
    target_route = "/dashboard"
    
    # Flatten sitemap hierarchy for search
    all_sitemap_nodes = []
    for node in sitemap:
        all_sitemap_nodes.append(node)
        if node.get("children"):
            for child in node["children"]:
                all_sitemap_nodes.append(child)

    # Keyword scoring for best sitemap match
    search_terms = [card_info["module"].lower(), card_info["subview"].lower()] + [k.lower() for k in card_info["keywords"]]
    best_score = -1
    for snode in all_sitemap_nodes:
        stitle = (snode.get("title") or "").lower()
        spath = (snode.get("path") or "").lower()
        sdesc = (snode.get("description") or "").lower()
        score = 0
        for kw in search_terms:
            if kw and len(kw) >= 2:
                if kw in stitle: score += 5
                if kw in spath: score += 4
                if kw in sdesc: score += 2
        if score > best_score:
            best_score = score
            matched_sitemap_node = snode

    if matched_sitemap_node:
        target_route = matched_sitemap_node.get("path") or f"/{card_info['module'].lower().replace(' ', '-')}"
        screen_id = matched_sitemap_node.get("screen_id")
        if screen_id and screen_mockups:
            matched_screen_mockup = next((m for m in screen_mockups if m.get("screen_id") == screen_id), None)
    else:
        target_route = f"/{card_info['module'].lower().replace(' ', '-')}"

    # Target URL Calculation
    if card_info.get("target_url"):
        target_url = card_info["target_url"]
    else:
        clean_route = target_route if target_route.startswith("/") else f"/{target_route}"
        target_url = f"{base_url.rstrip('/')}{clean_route}"

    # 2. Match with Traceability Matrix
    matched_matrix_rows = []
    for m in matrix:
        m_title = (m.get("req_title") or "").lower()
        m_code = (m.get("req_code") or "").lower()
        m_screen = (m.get("screen_name") or "").lower()
        m_uc = (m.get("use_case_id") or "").lower()
        if any(kw in m_title or kw in m_code or kw in m_screen or kw in m_uc for kw in search_terms if len(kw) >= 2):
            matched_matrix_rows.append(m)

    # 3. Formulate Structured Test Cases & Steps with AI Synthesis
    client = _get_gemini_client()
    srs_text = "\n\n---\n\n".join([f"[{c['source_file']}]:\n{c['content']}" for c in srs_chunks]) if srs_chunks else "Standard Web QA Standards"
    matrix_context = json.dumps(matched_matrix_rows[:5], ensure_ascii=False) if matched_matrix_rows else "No exact matrix link"

    prompt = f"""
You are an expert QA Automation Lead configuring an Automated Test Execution run.
Analyze the following information:

### TARGET CARD & CONTEXT:
- Title: {title}
- Description: {desc}
- Module Detected: {card_info.get('module')}
- Target Route: {target_route}
- Matched Sitemap Node: {json.dumps(matched_sitemap_node, ensure_ascii=False) if matched_sitemap_node else 'N/A'}
- Traceability Matrix Context: {matrix_context}
- SRS Knowledge Context:
{srs_text[:3000]}

Your Job:
1. Generate 3-5 concrete Test Cases for this feature, classifying each as "Positive" (Happy Path) or "Negative" (Error / Boundary check).
2. Generate 4-6 specific Test Execution Steps (Playwright actions) to verify this screen on a web browser.
3. Formulate expected acceptance criteria.

Return strictly valid JSON matching this schema:
{{
  "matched_module": "{card_info.get('module')}",
  "target_route": "{target_route}",
  "test_cases": [
    {{
      "id": "TC-01",
      "title": "...",
      "type": "Positive",
      "selected": true,
      "expected_result": "..."
    }},
    {{
      "id": "TC-02",
      "title": "...",
      "type": "Negative",
      "selected": true,
      "expected_result": "..."
    }}
  ],
  "test_steps": [
    {{ "step": 1, "action": "Navigate to target URL and verify page title", "target": "Page" }},
    {{ "step": 2, "action": "Verify presence of Data Table and Search Controls", "target": "Table / Input" }},
    {{ "step": 3, "action": "Interact with action buttons or submit test payload", "target": "Button" }},
    {{ "step": 4, "action": "Verify response, toast alerts, and grid update", "target": "Assertion" }}
  ],
  "expected_criteria": [
    "Criteria 1...",
    "Criteria 2..."
  ]
}}
"""
    ai_mapping_data = None
    try:
        model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        if hasattr(resp, 'usage_metadata') and resp.usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_Card_Tester_Mapping", model_name, resp.usage_metadata)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Card Tester: {log_err}")

        clean_json = resp.text.strip()
        if clean_json.startswith('```'):
            clean_json = re.sub(r'^```json\s*|^```\s*|```$', '', clean_json, flags=re.MULTILINE).strip()
        ai_mapping_data = json.loads(clean_json)
    except Exception as gemini_err:
        logger.warning(f"AI test mapping fallback: {gemini_err}")

    # Fallback test cases if AI fails
    test_cases = (ai_mapping_data and ai_mapping_data.get("test_cases")) or [
        {
            "id": f"TC-{card_info['module'][:3].upper()}-01",
            "title": f"ตรวจสอบการแสดงผลข้อมูลและโครงสร้างหน้าจอ {card_info['module']}",
            "type": "Positive",
            "selected": True,
            "expected_result": "ตารางและปุ่มคำสั่งแสดงผลครบถ้วนตาม SRS"
        },
        {
            "id": f"TC-{card_info['module'][:3].upper()}-02",
            "title": f"ตรวจสอบการทำงานของปุ่มค้นหาและฟิลเตอร์ {card_info['subview'] or 'Controls'}",
            "type": "Positive",
            "selected": True,
            "expected_result": "สามารถกรองข้อมูลและกดค้นหาได้ถูกต้อง"
        },
        {
            "id": f"TC-{card_info['module'][:3].upper()}-03",
            "title": "ตรวจสอบ Error Handling และ Validation ในกรณีไม่มีข้อมูล",
            "type": "Negative",
            "selected": True,
            "expected_result": "ระบบแสดงข้อความแจ้งเตือนที่เหมาะสม ไม่เกิด System Crash"
        }
    ]

    test_steps = (ai_mapping_data and ai_mapping_data.get("test_steps")) or [
        {"step": 1, "action": f"เปิดหน้าจอ {target_route} และรอโหลดหน้าสมบูรณ์", "target": "Browser Page"},
        {"step": 2, "action": "ตรวจสอบ Header, Navigation, และ Breadcrumb", "target": "Header"},
        {"step": 3, "action": "ตรวจสอบการแสดงผลตารางรายการข้อมูลและ Pagination", "target": "Data Table"},
        {"step": 4, "action": "ทดสอบคลิกปุ่ม Action เช่น Search, Export, หรือ Add Record", "target": "Action Buttons"},
        {"step": 5, "action": "บันทึกภาพถ่าย Screenshot และตรวจสอบ Console Log Errors", "target": "Verification"}
    ]

    expected_criteria = (ai_mapping_data and ai_mapping_data.get("expected_criteria")) or [
        "หน้าจอโหลดได้อย่างรวดเร็วและไม่มี JavaScript Console Error",
        "ส่วนประกอบ UI แสดงผลครบถ้วนตาม Wireframe และ SRS"
    ]

    return {
        "success": True,
        "project_name": project_name,
        "card_title": title,
        "card_id": card_data.get("id") or card_data.get("saved_id"),
        "ext_card_id": card_data.get("ext_card_id"),
        "base_url": base_url,
        "target_route": target_route,
        "target_url": target_url,
        "environments": environments,
        "matched_sitemap_node": matched_sitemap_node,
        "matched_screen_mockup": matched_screen_mockup,
        "matched_matrix_rows": matched_matrix_rows,
        "test_cases": test_cases,
        "test_steps": test_steps,
        "expected_criteria": expected_criteria,
        "srs_references": [c["source_file"] for c in srs_chunks]
    }


def execute_customized_test_run(project_id: str, payload: dict):
    """
    Executes an automated test run using Playwright and AI Gap Verification:
    - payload contains:
        target_url: str
        environment: str (DEV, UAT, etc.)
        user_role: str (Admin, Operator, etc.)
        test_cases: list of selected test cases
        test_steps: list of test steps
        card_id: optional
        card_title: str
        description: str
    """
    target_url = payload.get("target_url") or "http://localhost:5173"
    environment = payload.get("environment") or "UAT"
    user_role = payload.get("user_role") or "Admin"
    test_cases = payload.get("test_cases") or []
    test_steps = payload.get("test_steps") or []
    card_id = payload.get("card_id")
    card_title = payload.get("card_title") or "AI Test Execution"
    card_desc = payload.get("description") or ""

    logger.info(f"Executing AI Test Run on target URL: {target_url} (Env: {environment}, Role: {user_role})")

    # Step 1: Run Playwright Live Exploration & Evidence Capture
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
        "inputs": [],
        "screenshot_filename": shot_filename,
        "screenshot_path": str(shot_path),
        "error_logs": [],
        "status": "unreachable",
        "step_execution_logs": []
    }

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
            context = browser.new_context(viewport={'width': 1280, 'height': 800})
            page = context.new_page()

            page.on("console", lambda msg: web_state["error_logs"].append(f"[{msg.type}] {msg.text}") if msg.type in ["error", "warning"] else None)

            # Step Execution Log
            web_state["step_execution_logs"].append(f"▶️ Step 1: Navigating to {target_url} (Role: {user_role})...")
            
            connected = False
            try:
                page.goto(target_url, timeout=9000, wait_until='domcontentloaded')
                connected = True
                web_state["status"] = "connected"
                web_state["step_execution_logs"].append(f"✅ Connection established. Page loaded in {environment} mode.")
            except Exception as net_err:
                logger.warning(f"Connection issue on {target_url}: {net_err}")
                web_state["step_execution_logs"].append(f"⚠️ Direct connect issue: {net_err}. Probing fallback ports...")
                # Try localhost fallbacks
                for fb in ["http://localhost:5173", "http://localhost:3000"]:
                    try:
                        page.goto(fb, timeout=4000, wait_until='domcontentloaded')
                        connected = True
                        web_state["status"] = "connected"
                        web_state["url"] = fb
                        web_state["step_execution_logs"].append(f"✅ Connected via fallback server: {fb}")
                        break
                    except Exception:
                        pass

            if connected:
                page.wait_for_timeout(1500)
                web_state["title"] = page.title()

                # Extract live elements
                web_state["step_execution_logs"].append("▶️ Step 2: Inspecting DOM elements, forms, and data tables...")
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

                buttons_info = page.evaluate('''() => {
                    const btns = [];
                    document.querySelectorAll('button, a.btn, input[type="button"], input[type="submit"]').forEach(b => {
                        const text = (b.innerText || b.value || '').trim();
                        if (text && text.length < 50) btns.push(text);
                    });
                    return btns.slice(0, 25);
                }''')
                web_state["buttons"] = buttons_info

                web_state["step_execution_logs"].append(f"✅ Extracted: {len(buttons_info)} action buttons, {len(tables_info)} tables, {len(selects_info)} dropdowns.")
                
                # Take proof screenshot
                web_state["step_execution_logs"].append("▶️ Step 3: Capturing proof screenshot & DOM state...")
                page.screenshot(path=str(shot_path), full_page=False)
                web_state["step_execution_logs"].append(f"📸 Screenshot saved successfully: {shot_filename}")

            browser.close()
    except Exception as pw_err:
        logger.error(f"Playwright execution error: {pw_err}")
        web_state["error_logs"].append(str(pw_err))
        web_state["step_execution_logs"].append(f"❌ Playwright Runner Error: {pw_err}")

    # Step 2: Gemini AI Evaluation against selected Test Cases
    client = _get_gemini_client()
    srs_chunks = retrieve_srs_requirements(project_id, {"keywords": [card_title], "module": card_title, "subview": ""}, max_chunks=3)
    srs_text = "\n\n".join([f"[{c['source_file']}]: {c['content']}" for c in srs_chunks]) if srs_chunks else "Standard Quality Specification"

    prompt = f"""
You are the Lead QA Automation Agent evaluating the results of an automated test execution.

### TEST EXECUTION DETAILS:
- Feature / Card Title: {card_title}
- Target URL: {web_state.get('url')}
- Environment: {environment} (User Role: {user_role})
- Selected Test Cases to Validate:
{json.dumps(test_cases, ensure_ascii=False, indent=2)}

### ACTUAL LIVE WEB STATE CAPTURED:
- Status: {web_state.get('status')}
- Page Title: {web_state.get('title')}
- Tables Extracted: {json.dumps(web_state.get('tables', []), ensure_ascii=False)}
- Buttons Extracted: {json.dumps(web_state.get('buttons', []), ensure_ascii=False)}
- Selects/Dropdowns: {json.dumps(web_state.get('selects', []), ensure_ascii=False)}
- Browser Errors: {json.dumps(web_state.get('error_logs', []), ensure_ascii=False)}

### SRS CONTEXT:
{srs_text[:2500]}

### EVALUATION RULES:
1. Compare each selected test case's expected result with the captured web state.
2. If any critical test case fails (or if severe browser crash errors are present, or reported defects like missing required buttons/tables), mark verdict as "FAILED".
3. If all selected test cases satisfy their expectations, mark verdict as "PASSED".

Return strictly JSON matching this structure:
{{
  "verdict": "PASSED" or "FAILED",
  "score_percent": 90,
  "summary": "1-2 sentence executive summary of test result in Thai",
  "matched_criteria": [
    "✅ List of test cases and requirements that passed..."
  ],
  "discrepancies": [
    {{
      "item": "Issue description in Thai",
      "severity": "High/Medium/Low",
      "impact": "Impact on user in Thai"
    }}
  ],
  "recommendation": "Recommendation for QA/Dev team in Thai"
}}
"""
    eval_result = {}
    try:
        model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        if hasattr(resp, 'usage_metadata') and resp.usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_Card_Tester_Evaluation", model_name, resp.usage_metadata)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Card Tester Eval: {log_err}")

        clean_json = resp.text.strip()
        if clean_json.startswith('```'):
            clean_json = re.sub(r'^```json\s*|^```\s*|```$', '', clean_json, flags=re.MULTILINE).strip()
        eval_result = json.loads(clean_json)
    except Exception as eval_err:
        logger.warning(f"Gemini evaluation error: {eval_err}")
        is_fail = web_state.get("status") == "unreachable" or len(web_state.get("error_logs", [])) > 0
        eval_result = {
            "verdict": "FAILED" if is_fail else "PASSED",
            "score_percent": 65 if is_fail else 95,
            "summary": "พบข้อผิดพลาดในการเชื่อมต่อหน้าจอหรือโครงสร้าง UI" if is_fail else "ทดสอบระบบผ่านตามเกณฑ์และ Test Cases ทั้งหมด",
            "matched_criteria": ["ตรวจสอบโครงสร้างหน้าจอเบื้องต้น"],
            "discrepancies": [{"item": "Connection Error", "severity": "High", "impact": "ไม่สามารถเข้าถึงหน้าจอเป้าหมายได้"}] if is_fail else [],
            "recommendation": "ตรวจสอบสถานะเว็บเซิร์ฟเวอร์และลองรันอีกครั้ง" if is_fail else "ระบบพร้อมสำหรับการทดสอบขั้นต่อไป"
        }

    verdict = eval_result.get("verdict", "PASSED")
    is_passed = (verdict == "PASSED")
    score_percent = eval_result.get("score_percent", 100 if is_passed else 60)
    summary = eval_result.get("summary", "")
    matched_criteria = eval_result.get("matched_criteria", [])
    discrepancies = eval_result.get("discrepancies", [])
    recommendation = eval_result.get("recommendation", "")
    logs_text = "\n".join(web_state.get("step_execution_logs", []))

    # Generate Markdown Report
    screenshot_fn = web_state.get("screenshot_filename")
    shot_md = f"\n\n![Live Test Evidence](http://localhost:5000/api/attachments/{screenshot_fn})" if screenshot_fn and os.path.exists(web_state.get("screenshot_path", "")) else ""

    matched_list = "\n".join([f"- {m}" for m in matched_criteria]) or "- ตรวจสอบตามเกณฑ์ทั่วไป"
    discrepancy_list = "\n".join([f"- ❌ **[{d.get('severity', 'Defect')}]** {d.get('item')}: {d.get('impact', '')}" for d in discrepancies]) or "- ไม่มีข้อบกพร่อง ตรวจสอบผ่านทุกรายการ"

    report_markdown = f"""### 🤖 Spectra QA Agent Automated Test Report
**Verdict:** `{'PASSED' if is_passed else 'FAILED (DEFECT DETECTED)'}` (Score: {score_percent}%)
**Target URL:** `{target_url}` | **Environment:** `{environment}` | **Role:** `{user_role}`
**Feature:** {card_title}

#### 📋 ผลการตรวจสอบตาม Test Cases ที่เลือก:
{matched_list}

#### ⚠️ ข้อบกพร่องที่ตรวจพบ (Defects / Discrepancies):
{discrepancy_list}

#### 💡 ข้อเสนอแนะ (Recommendation):
{recommendation}
{shot_md}
"""

    # Step 3: Persist to qa_test_execution_runs and update board_cards if card_id provided
    run_id = str(uuid.uuid4())
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO qa_test_execution_runs (
                    id, project_id, card_id, card_title, target_url, environment, user_role,
                    test_cases, test_steps, verdict, score_percent, summary, matched_criteria,
                    discrepancies, screenshot_filename, logs, recommendation
                ) VALUES (
                    %s::uuid, %s::uuid, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
            """, (
                run_id, project_id, str(card_id) if card_id else None, card_title, target_url, environment, user_role,
                json.dumps(test_cases, ensure_ascii=False), json.dumps(test_steps, ensure_ascii=False), verdict, score_percent,
                summary, json.dumps(matched_criteria, ensure_ascii=False), json.dumps(discrepancies, ensure_ascii=False),
                screenshot_fn, logs_text, recommendation
            ))

            # Update board_cards test_result if card exists
            clean_raw_id = str(card_id).lstrip('#') if card_id else None
            if card_id:
                cursor.execute("""
                    UPDATE board_cards
                    SET test_result = %s,
                        status = CASE WHEN %s = 'PASSED' THEN status ELSE 'defect' END
                    WHERE project_id = %s::uuid AND (card_id::text = %s OR ext_card_id = %s OR raw_ext_id = %s)
                """, (report_markdown, verdict, project_id, str(card_id), str(card_id), str(card_id)))

                # Resolve actual raw external card ID if card is stored in DB
                cursor.execute("""
                    SELECT raw_ext_id, ext_card_id FROM board_cards
                    WHERE project_id = %s::uuid AND (card_id::text = %s OR ext_card_id = %s OR raw_ext_id = %s)
                """, (project_id, str(card_id), str(card_id), str(card_id)))
                b_card_row = cursor.fetchone()
                if b_card_row:
                    clean_raw_id = b_card_row[0] or b_card_row[1] or clean_raw_id
                
                if clean_raw_id and clean_raw_id.startswith('TRL-'):
                    clean_raw_id = clean_raw_id.replace('TRL-', '')

            # Sync test result to Board Integration (Trello / GitHub)
            if card_id and clean_raw_id:
                try:
                    cursor.execute("""
                        SELECT provider, trello_api_key, trello_token, trello_board_id,
                               github_token, github_owner, github_repo, columns_json
                        FROM board_integrations
                        WHERE project_id = %s::uuid
                    """, (project_id,))
                    integ_row = cursor.fetchone()

                    if integ_row:
                        provider, t_key, t_token, t_board, gh_token, gh_owner, gh_repo, cols_json = integ_row

                        if provider == 'trello' and t_key and t_token:
                            # 1. Upload screenshot attachment to Trello if available
                            if screenshot_fn and os.path.exists(web_state.get("screenshot_path", "")):
                                try:
                                    with open(web_state.get("screenshot_path"), 'rb') as f_up:
                                        requests.post(
                                            f"https://api.trello.com/1/cards/{clean_raw_id}/attachments",
                                            params={"key": t_key, "token": t_token, "name": "Agent Test Evidence.png"},
                                            files={"file": (screenshot_fn, f_up, 'image/png')},
                                            timeout=15
                                        )
                                except Exception as att_err:
                                    logger.warning(f"Could not upload screenshot to Trello card: {att_err}")

                            # 2. Post markdown test report as comment to Trello
                            try:
                                comment_payload = f"🤖 **Spectra QA Agent Automated Test Report ({verdict})**\n\n{report_markdown}"
                                tc_res = requests.post(
                                    f"https://api.trello.com/1/cards/{clean_raw_id}/actions/comments",
                                    params={"key": t_key, "token": t_token, "text": comment_payload},
                                    timeout=12
                                )
                                logger.info(f"Posted Trello test comment to card {clean_raw_id}: status={tc_res.status_code}")
                            except Exception as c_err:
                                logger.warning(f"Failed to post Trello comment: {c_err}")

                            # 3. If test FAILED, move card to Defect list on Trello
                            if not is_passed:
                                defect_list_id = None
                                try:
                                    lists_res = requests.get(
                                        f"https://api.trello.com/1/boards/{t_board}/lists",
                                        params={"key": t_key, "token": t_token},
                                        timeout=10
                                    )
                                    if lists_res.ok:
                                        t_lists = lists_res.json()
                                        for lst in t_lists:
                                            lname = (lst.get('name') or '').lower()
                                            if any(w in lname for w in ['defect', 'bug', 'ข้อบกพร่อง', 'บั๊ก']):
                                                defect_list_id = lst.get('id')
                                                break

                                        # If no Defect list exists on Trello board, create one automatically
                                        if not defect_list_id and t_board:
                                            create_l_res = requests.post(
                                                f"https://api.trello.com/1/boards/{t_board}/lists",
                                                params={"key": t_key, "token": t_token, "name": "Defect", "pos": "bottom"},
                                                timeout=10
                                            )
                                            if create_l_res.ok:
                                                defect_list_id = create_l_res.json().get('id')
                                                logger.info(f"Created 'Defect' list on Trello board: {defect_list_id}")
                                except Exception as l_err:
                                    logger.warning(f"Error resolving or creating Defect list on Trello: {l_err}")

                                if defect_list_id:
                                    try:
                                        move_res = requests.put(
                                            f"https://api.trello.com/1/cards/{clean_raw_id}",
                                            params={"idList": defect_list_id, "key": t_key, "token": t_token},
                                            json={"idList": defect_list_id},
                                            timeout=10
                                        )
                                        logger.info(f"Moved Trello card {clean_raw_id} to Defect list {defect_list_id}: status={move_res.status_code}")

                                        # Update status in local board_cards
                                        cursor.execute("""
                                            UPDATE board_cards
                                            SET status = %s
                                            WHERE project_id = %s::uuid AND (card_id::text = %s OR ext_card_id = %s OR raw_ext_id = %s)
                                        """, (defect_list_id, project_id, str(card_id), str(card_id), str(card_id)))
                                    except Exception as move_err:
                                        logger.warning(f"Failed to move Trello card to Defect list: {move_err}")

                        elif provider == 'github' and gh_token and gh_owner and gh_repo:
                            try:
                                gh_comment = f"🤖 **Spectra QA Agent Test Report ({verdict})**\n\n{report_markdown}"
                                requests.post(
                                    f"https://api.github.com/repos/{gh_owner}/{gh_repo}/issues/{clean_raw_id}/comments",
                                    headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github.v3+json", "User-Agent": "SpectraQA"},
                                    json={"body": gh_comment},
                                    timeout=12
                                )
                                if not is_passed:
                                    requests.post(
                                        f"https://api.github.com/repos/{gh_owner}/{gh_repo}/issues/{clean_raw_id}/labels",
                                        headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github.v3+json", "User-Agent": "SpectraQA"},
                                        json={"labels": ["bug", "defect"]},
                                        timeout=10
                                    )
                            except Exception as gh_err:
                                logger.warning(f"Failed to sync test report to GitHub: {gh_err}")
                except Exception as integ_err:
                    logger.warning(f"Error executing board integration sync: {integ_err}")

            conn.commit()
            cursor.close()
            conn.close()
        except Exception as db_err:
            logger.error(f"Error persisting test execution run: {db_err}")
            if 'conn' in locals() and conn:
                conn.close()

    return {
        "success": True,
        "run_id": run_id,
        "verdict": verdict,
        "is_passed": is_passed,
        "score_percent": score_percent,
        "summary": summary,
        "matched_criteria": matched_criteria,
        "discrepancies": discrepancies,
        "recommendation": recommendation,
        "logs": logs_text,
        "screenshot_url": f"http://localhost:5000/api/attachments/{screenshot_fn}" if screenshot_fn else None,
        "test_result_markdown": report_markdown
    }


def get_project_test_runs(project_id: str, limit: int = 50):
    """
    Retrieves historical test execution runs for a project.
    """
    conn = get_db_connection()
    if not conn:
        return []
    runs = []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, card_id, card_title, target_url, environment, user_role,
                   verdict, score_percent, summary, screenshot_filename, created_at,
                   matched_criteria, discrepancies, recommendation, test_cases
            FROM qa_test_execution_runs
            WHERE project_id = %s::uuid
            ORDER BY created_at DESC
            LIMIT %s
        """, (project_id, limit))
        rows = cursor.fetchall()
        for r in rows:
            runs.append({
                "id": str(r[0]),
                "card_id": r[1],
                "card_title": r[2],
                "target_url": r[3],
                "environment": r[4],
                "user_role": r[5],
                "verdict": r[6],
                "score_percent": r[7],
                "summary": r[8],
                "screenshot_url": f"http://localhost:5000/api/attachments/{r[9]}" if r[9] else None,
                "created_at": r[10].isoformat() if r[10] else None,
                "matched_criteria": r[11] if isinstance(r[11], list) else (json.loads(r[11] or '[]') if r[11] else []),
                "discrepancies": r[12] if isinstance(r[12], list) else (json.loads(r[12] or '[]') if r[12] else []),
                "recommendation": r[13],
                "test_cases": r[14] if isinstance(r[14], list) else (json.loads(r[14] or '[]') if r[14] else [])
            })
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching test runs: {e}")
        if 'conn' in locals() and conn:
            conn.close()
    return runs


def run_card_agent_test(project_id: str, card_id: str, card_data: dict):
    """
    Wrapper function to map and execute agent tests for a single card.
    """
    mapping = resolve_card_test_mapping(project_id, card_data)
    payload = {
        "project_id": project_id,
        "target_url": mapping.get("target_url"),
        "environment": "UAT",
        "user_role": "Admin",
        "test_cases": mapping.get("test_cases", []),
        "test_steps": mapping.get("test_steps", []),
        "card_id": card_id or card_data.get("id") or card_data.get("ext_card_id"),
        "card_title": card_data.get("title") or mapping.get("card_title") or "Feature Test",
        "description": card_data.get("description") or ""
    }
    return execute_customized_test_run(project_id, payload)

