import json
import logging
import os
import re
import datetime
from dotenv import load_dotenv

# Ensure environment variables are loaded
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(override=True)

from db_ingestion import get_db_connection
from gemini_utils import call_gemini

logger = logging.getLogger(__name__)


def init_flow_diagrams_table():
    """Initializes the qa_analysis_diagrams table if it does not exist."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_analysis_diagrams (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                sitemap_data JSONB DEFAULT '[]'::jsonb,
                system_flowchart TEXT,
                usecase_diagram TEXT,
                activity_diagram TEXT,
                sequence_diagram TEXT,
                screen_mockups JSONB DEFAULT '[]'::jsonb,
                traceability_matrix JSONB DEFAULT '[]'::jsonb,
                summary_stats JSONB DEFAULT '{}'::jsonb,
                status VARCHAR(50) DEFAULT 'Completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE qa_analysis_diagrams ADD COLUMN IF NOT EXISTS system_flowchart TEXT;
            CREATE INDEX IF NOT EXISTS idx_qa_analysis_diagrams_project_id ON qa_analysis_diagrams(project_id);
        """)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("qa_analysis_diagrams table initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize qa_analysis_diagrams table: {e}")


def generate_mockup_for_node(node: dict, project_name: str = "System") -> dict:
    """
    Domain-neutral fallback screen wireframe generator for any sitemap node
    not explicitly emitted by the LLM. Uses strictly the node's own metadata
    so zero foreign-domain data ever leaks into a project.
    """
    nid = node.get('id', 'page')
    title = node.get('title', 'Screen')
    path = node.get('path', '/')
    sid = node.get('screen_id') or f"SCR-{str(nid).upper().replace('-', '_')}"
    desc = node.get('description') or f"หน้าจอ {title} สำหรับระบบ {project_name}"
    category = node.get('category') or 'Module'
    use_cases = node.get('use_case_ids') or []
    req_codes = node.get('req_codes') or []

    lower_title = title.lower()
    lower_path = path.lower()
    is_auth = any(k in lower_title or k in lower_path for k in ['login', 'auth', 'signin', 'register', 'เข้าสู่ระบบ'])
    is_list = any(k in lower_title or k in lower_path for k in ['list', 'table', 'manage', 'queue', 'history', 'log', 'รายการ', 'จัดการ', 'ประวัติ'])
    is_dashboard = any(k in lower_title or k in lower_path for k in ['dashboard', 'overview', 'analytics', 'report', 'summary', 'ภาพรวม', 'รายงาน'])

    layout_type = "form" if is_auth else ("dashboard" if is_dashboard else ("table" if is_list else "detail"))

    if is_auth:
        sections = [
            {
                "section_name": f"แบบฟอร์มยืนยันตัวตน ({title})",
                "type": "form",
                "fields": [
                    {"label": "ชื่อผู้ใช้งาน / อีเมล (Username / Email)", "type": "text", "default_value": "", "required": True},
                    {"label": "รหัสผ่าน (Password)", "type": "password", "default_value": "", "required": True}
                ],
                "buttons": [
                    {"label": "เข้าสู่ระบบ", "variant": "primary"},
                    {"label": "รีเซ็ตข้อมูล", "variant": "outline"}
                ]
            }
        ]
    elif is_list or is_dashboard:
        sections = [
            {
                "section_name": f"ตารางข้อมูลหลัก — {title}",
                "type": "table",
                "table_headers": ["รหัสรายการ", "รายละเอียด", "สถานะ", "วันที่อัปเดต", "การดำเนินการ"],
                "table_rows": [
                    ["ITEM-001", f"ข้อมูลตัวอย่างตามข้อกำหนดของ {title}", "Active", "-", "ดูรายละเอียด / แก้ไข"]
                ]
            }
        ]
    else:
        sections = [
            {
                "section_name": f"ข้อมูลและแบบฟอร์มหลัก — {title}",
                "type": "form",
                "fields": [
                    {"label": f"หัวข้อ / รหัสอ้างอิง ({title})", "type": "text", "default_value": "", "required": True},
                    {"label": "รายละเอียดเพิ่มเติม", "type": "textarea", "default_value": desc, "required": False}
                ],
                "buttons": [
                    {"label": "บันทึกข้อมูล", "variant": "primary"},
                    {"label": "ยกเลิก", "variant": "outline"}
                ]
            }
        ]

    return {
        "screen_id": sid,
        "screen_name": title,
        "route": path,
        "layout_type": layout_type,
        "description": desc,
        "header": {
            "title": f"{title} ({project_name})",
            "badge": category,
            "badge_color": "blue",
            "actions": ["บันทึก", "รีเฟรช"]
        },
        "stats": [
            {"label": "โมดูล", "value": category, "sub": project_name, "color": "blue"},
            {"label": "เส้นทางหน้าจอ", "value": path, "sub": sid, "color": "purple"}
        ],
        "tabs": ["ข้อมูลหลัก", "ประวัติการดำเนินการ"],
        "sections": sections,
        "connected_use_cases": use_cases if isinstance(use_cases, list) else [],
        "connected_req_codes": req_codes if isinstance(req_codes, list) else []
    }


def ensure_all_screen_mockups(sitemap_data: list, screen_mockups: list, project_name: str = "System") -> list:
    """Ensures that every node (both root module and children) in sitemap_data has a matching screen mockup."""
    if not sitemap_data:
        return screen_mockups or []

    res_mockups = list(screen_mockups) if screen_mockups else []
    existing_ids = {m.get('screen_id') for m in res_mockups if m.get('screen_id')}
    existing_routes = {m.get('route') for m in res_mockups if m.get('route')}
    existing_names = {m.get('screen_name') for m in res_mockups if m.get('screen_name')}

    for node in sitemap_data:
        children = node.get('children', []) or []
        nodes_to_check = [node] + children
        for n in nodes_to_check:
            sid = n.get('screen_id')
            sroute = n.get('path')
            stitle = n.get('title')

            if (sid and sid in existing_ids) or (sroute and sroute in existing_routes) or (stitle and stitle in existing_names):
                continue

            new_m = generate_mockup_for_node(n, project_name)
            res_mockups.append(new_m)
            if new_m.get('screen_id'):
                existing_ids.add(new_m.get('screen_id'))
            if new_m.get('route'):
                existing_routes.add(new_m.get('route'))
            if new_m.get('screen_name'):
                existing_names.add(new_m.get('screen_name'))

    return res_mockups


def _merge_preserved_wireframe_assets(new_mockups: list, old_mockups: list) -> list:
    """
    Preserves user-uploaded wireframe images and Figma links when re-analyzing diagrams
    so users never lose manual visual assets on regeneration.
    """
    if not old_mockups or not isinstance(old_mockups, list):
        return new_mockups

    by_id = {}
    by_route = {}
    by_name = {}
    for om in old_mockups:
        if not isinstance(om, dict):
            continue
        has_asset = bool(om.get('figma_url') or om.get('image_url'))
        if not has_asset:
            continue
        if om.get('screen_id'):
            by_id[str(om['screen_id']).strip().lower()] = om
        if om.get('route'):
            by_route[str(om['route']).strip().lower()] = om
        if om.get('screen_name'):
            by_name[str(om['screen_name']).strip().lower()] = om

    for nm in new_mockups:
        if not isinstance(nm, dict):
            continue
        match = (
            by_id.get(str(nm.get('screen_id', '')).strip().lower())
            or by_route.get(str(nm.get('route', '')).strip().lower())
            or by_name.get(str(nm.get('screen_name', '')).strip().lower())
        )
        if match:
            for k in ('figma_url', 'image_url', 'image_filename', 'wireframe_type'):
                if match.get(k):
                    nm[k] = match[k]
    return new_mockups


def clean_mermaid_code(raw_code: str) -> str:
    """Sanitizes Mermaid syntax for strict Mermaid 10+ compatibility."""
    if not raw_code:
        return ""
    txt = str(raw_code).strip()
    if txt.startswith("```mermaid"):
        txt = txt[10:].strip()
    elif txt.startswith("```"):
        txt = txt[3:].strip()
    if txt.endswith("```"):
        txt = txt[:-3].strip()

    if re.match(r'^\s*sequenceDiagram\b', txt, re.IGNORECASE):
        return txt

    lines = txt.splitlines()
    cleaned_lines = []

    for line in lines:
        l = line.rstrip()
        if not l.strip():
            cleaned_lines.append("")
            continue

        indent = re.match(r'^\s*', l).group(0)

        # Fix actor declaration in flowchart
        actor_m = re.match(r'^\s*actor\s+([A-Za-z0-9_]+)(?:\s+(?:as\s+)?(.*))?$', l, re.IGNORECASE)
        if actor_m:
            act_id = actor_m.group(1)
            act_lbl = actor_m.group(2) or act_id
            act_lbl = act_lbl.strip().strip('"').strip("'").replace('"', "'")
            cleaned_lines.append(f'{indent}{act_id}["{act_lbl}"]')
            continue

        # Fix Subgraph quotes
        sub_m = re.match(r'^(\s*subgraph\s+[A-Za-z0-9_]+)\s*\[\s*([^\]]+?)\s*\]\s*$', l, re.IGNORECASE)
        if sub_m:
            title = sub_m.group(2).strip().strip('"').strip("'").replace('"', "'")
            cleaned_lines.append(f'{sub_m.group(1)} ["{title}"]')
            continue

        # Fix dotted & plantuml arrows
        l = re.sub(r'([A-Za-z0-9_]+)\s*<\.\.\s*([A-Za-z0-9_]+)\s*:\s*<?<?([^>\r\n]+)>?>?', r'\2 -.->|"\3"| \1', l)
        l = re.sub(r'([A-Za-z0-9_]+)\s*\.\.>\s*([A-Za-z0-9_]+)\s*:\s*<?<?([^>\r\n]+)>?>?', r'\1 -.->|"\3"| \2', l)
        l = re.sub(r'([A-Za-z0-9_]+)\s*<\.\.\s*([A-Za-z0-9_]+)', r'\2 -.-> \1', l)
        l = re.sub(r'([A-Za-z0-9_]+)\s*\.\.>\s*([A-Za-z0-9_]+)', r'\1 -.-> \2', l)

        # Fix inline edge labels
        l = re.sub(r'--\s*(?:\(([^()\r\n]+)\)|([^->\r\n|]+?))\s*-->', r'-->|"\1\2"|', l)
        l = re.sub(r'--\s*(?:\(([^()\r\n]+)\)|([^->\r\n|]+?))\s*--\s*>', r'-->|"\1\2"|', l)

        # Protect reserved End keyword
        if not re.match(r'^\s*end\s*$', l, re.IGNORECASE):
            l = re.sub(r'\bEnd\s*\(\[\s*(.*?)\s*\]\)', r'EndNode(["\1"])', l)
            l = re.sub(r'\bEnd\s*\[\s*(.*?)\s*\]', r'EndNode["\1"]', l)
            l = re.sub(r'(-->|-\.->|==>)\s*End\b', r'\1 EndNode', l)
            l = re.sub(r'\bEnd\s*(-->|-\.->|==>)', r'EndNode \1', l)

        cleaned_lines.append(l)

    # Auto-close unclosed subgraphs
    sub_count = sum(1 for line in cleaned_lines if re.match(r'^\s*subgraph\b', line, re.IGNORECASE))
    end_count = sum(1 for line in cleaned_lines if re.match(r'^\s*end\s*$', line.strip(), re.IGNORECASE))
    while sub_count > end_count:
        cleaned_lines.append("  end")
        end_count += 1

    return "\n".join(cleaned_lines)


def analyze_project_flow_and_diagrams(project_id: str, custom_instructions: str = ""):
    """
    Agent 7: QA Architecture, Flow & Diagram Analyzer
    Synthesizes ALL project sources (Knowledge Base prioritizing Golden/SRS/SDD, Structured Requirements,
    QA Generated Documents, and API Collections) into a deeply interconnected, domain-isolated model:
    1. Flow Sitemap (Hierarchical IA)
    2. UML & Flow Diagrams (System Flowchart, Use Case, Activity, Sequence in Mermaid 10+)
    3. Interactive Screen Wireframes & UI Mockups (preserving any existing Figma/Image uploads)
    4. Bidirectional Traceability Matrix (REQ -> Use Case -> Screen -> Test Cases -> UAT)
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Fetch Project Information
        cursor.execute("SELECT project_code, project_name, description FROM projects WHERE project_id = %s::uuid", (project_id,))
        proj_row = cursor.fetchone()
        project_code = proj_row[0] if proj_row else "PROJ"
        project_name = proj_row[1] if proj_row else "QA Project"
        project_desc = proj_row[2] if proj_row else ""

        # 2. Fetch ALL Active KB Documents (Prioritizing Golden Data & SRS/SDD/TOR with generous context budget)
        cursor.execute("""
            SELECT doc_id, original_filename, doc_category, doc_type, full_markdown_content,
                   COALESCE(is_golden_data, FALSE) AS is_golden
            FROM documents
            WHERE project_id = %s::uuid AND (status = 'Active' OR status IS NULL)
            ORDER BY COALESCE(is_golden_data, FALSE) DESC, created_at DESC
        """, (project_id,))
        doc_rows = cursor.fetchall()

        docs_context = []
        total_chars = 0
        MAX_TOTAL_DOC_CHARS = 140000
        for d in doc_rows:
            d_cat = str(d[2] or '')
            d_type = str(d[3] or '')
            d_name = str(d[1] or '')
            is_golden = bool(d[5]) if len(d) > 5 else False
            is_primary = is_golden or any(k in (d_cat + ' ' + d_type + ' ' + d_name).lower() for k in ['srs', 'requirement', 'sdd', 'tor', 'spec'])
            limit = 45000 if is_primary else 12000
            remaining = max(0, MAX_TOTAL_DOC_CHARS - total_chars)
            if remaining <= 0:
                break
            content_snippet = (d[4] or "")[:min(limit, remaining)]
            total_chars += len(content_snippet)
            docs_context.append({
                "doc_id": str(d[0]),
                "filename": d_name,
                "category": d_cat,
                "type": d_type,
                "is_golden_data": is_golden,
                "content": content_snippet
            })

        # 3. Fetch Structured Requirements
        reqs_context = []
        try:
            cursor.execute("""
                SELECT req_code, title, description, steps, expected_results
                FROM structured_requirements
                WHERE project_id = %s::uuid
                ORDER BY req_code ASC
            """, (project_id,))
            for r in cursor.fetchall():
                reqs_context.append({
                    "req_code": r[0],
                    "title": r[1],
                    "description": r[2],
                    "steps": r[3],
                    "expected_results": r[4]
                })
        except Exception as req_err:
            conn.rollback()
            logger.warning(f"Agent 7: structured_requirements fetch skipped: {req_err}")

        # 4. Fetch Generated QA Documents (Test Cases / SRS / UAT)
        qa_docs_context = []
        try:
            cursor.execute("""
                SELECT doc_name, doc_type, markdown_content
                FROM qa_generated_documents
                WHERE project_id = %s::uuid AND UPPER(COALESCE(status, '')) = 'COMPLETED'
                ORDER BY created_at DESC LIMIT 6
            """, (project_id,))
            for q in cursor.fetchall():
                qa_docs_context.append({
                    "doc_name": q[0],
                    "doc_type": q[1],
                    "snippet": (q[2] or "")[:5000]
                })
        except Exception as qd_err:
            conn.rollback()
            logger.warning(f"Agent 7: qa_generated_documents fetch skipped: {qd_err}")

        # 5. Fetch Project API Collections (real endpoints for accurate Sequence & Flowchart diagrams)
        api_context = []
        try:
            cursor.execute("""
                SELECT name, method, url, description
                FROM api_collections
                WHERE project_id = %s::uuid
                ORDER BY created_at DESC LIMIT 30
            """, (project_id,))
            for a in cursor.fetchall():
                api_context.append({
                    "name": a[0],
                    "method": a[1],
                    "url": a[2],
                    "description": (a[3] or "")[:300]
                })
        except Exception:
            conn.rollback()

        # Fetch existing mockups to preserve any user-uploaded Figma URLs or images
        existing_mockups = []
        existing_row = None
        try:
            cursor.execute("SELECT id, screen_mockups FROM qa_analysis_diagrams WHERE project_id = %s::uuid ORDER BY updated_at DESC LIMIT 1", (project_id,))
            existing_row = cursor.fetchone()
            if existing_row and existing_row[1]:
                existing_mockups = existing_row[1] if isinstance(existing_row[1], list) else []
        except Exception:
            conn.rollback()

        cursor.close()
        conn.close()
        conn = None

        user_instruction_section = ""
        if custom_instructions and custom_instructions.strip():
            user_instruction_section = f"""
# Additional Custom Instructions from User (High Priority)
{custom_instructions.strip()}
"""

        api_section = ""
        if api_context:
            api_section = f"""
# Captured Project API Endpoints ({len(api_context)} endpoints)
Use these real API methods & routes inside the Sequence Diagram and System Flowchart where applicable:
{json.dumps(api_context, ensure_ascii=False, indent=2)}
"""

        prompt = f"""
You are a Principal Software Architect, Senior QA Lead, and UX/System Analyst.
Your task is to analyze ALL provided Knowledge Base documents, Structured Requirements, QA Generated Documents, and API Endpoints for project "{project_name}" ({project_code}) and construct an exhaustive, high-precision **System Flow & QA Architecture Model**.

CRITICAL DOMAIN ISOLATION RULE:
- Every single Sitemap node, Screen Mockup, Diagram label, Field, Table, and Traceability row MUST belong 100% strictly to project "{project_name}" ({project_code}) based on the documents below.
- NEVER invent, borrow, or hallucinate screens or data from unrelated domains (e.g. restaurant ordering, food delivery, e-commerce) unless explicitly present in this project's documents.
- This output will be stored in the central database and consumed downstream by QA Document Creation, QA Consult, QA Research, and QA Test Automation (Playwright MCP) — precision of module names, screen routes, API paths, REQ codes, and edge/error branches is critical.

# Project Context
- Project Code: {project_code}
- Project Name: {project_name}
- Description: {project_desc}

# Project Documents ({len(docs_context)} documents)
{json.dumps(docs_context, ensure_ascii=False, indent=2)}

# Structured Requirements ({len(reqs_context)} requirements)
{json.dumps(reqs_context, ensure_ascii=False, indent=2)}

# QA Generated Documents Context
{json.dumps(qa_docs_context, ensure_ascii=False, indent=2)}
{api_section}
{user_instruction_section}

---
# Output Format Requirements (MUST BE STRICT VALID JSON ONLY)
Generate a single, strict JSON object following this exact schema (replace all angle-bracket placeholders with real data from project "{project_name}"):

{{
  "sitemap": [
    {{
      "id": "mod-1",
      "title": "<Real Module / Menu Name from SRS>",
      "path": "/<real-route>",
      "category": "Main / Admin / User / API",
      "icon": "🔐",
      "description": "<Detailed Thai description of this module's purpose>",
      "screen_id": "SCR-MOD-01",
      "use_case_ids": ["UC-001"],
      "req_codes": ["REQ-001"],
      "children": [
        {{
          "id": "mod-1-1",
          "title": "<Real Sub-screen / Modal Name>",
          "path": "/<real-route>/<sub-route>",
          "category": "Sub-page",
          "icon": "📄",
          "description": "<Detailed Thai description>",
          "screen_id": "SCR-MOD-01-SUB",
          "use_case_ids": ["UC-002"],
          "req_codes": ["REQ-002"],
          "children": []
        }}
      ]
    }}
  ],

  "system_flowchart": "Mermaid 10+ flowchart TD with tier subgraphs (ClientLayer, APIGateway, BusinessLogic, DataLayer), decision diamonds, error/validation branches, and data persistence strictly reflecting this project's real workflows. Always wrap labels with double quotes.",

  "usecase_diagram": "Mermaid 10+ flowchart LR showing SystemBoundary subgraph with all real Use Cases (UC-xxx) and Actors declared as standard nodes e.g. User[\"ผู้ใช้งาน\"]. Never use `actor X as ...` inside flowchart.",

  "activity_diagram": "Mermaid 10+ flowchart TD detailing step-by-step user/system decision branches including both Happy Path and Unhappy/Validation Error Paths for the project's core workflows.",

  "sequence_diagram": "Mermaid 10+ sequenceDiagram with autonumber showing real actors, UI screens, real API endpoints/services, and database/external integrations from this project.",

  "screen_mockups": [
    {{
      "screen_id": "SCR-MOD-01",
      "screen_name": "<Real Screen Name>",
      "route": "/<real-route>",
      "layout_type": "dashboard | form | table | detail",
      "description": "<Thai description of what this screen does and its key business rules>",
      "header": {{
        "title": "<Real Screen Title>",
        "badge": "<Module Category>",
        "badge_color": "blue | emerald | purple | amber",
        "actions": ["<Primary Action Button>", "<Secondary Action>"]
      }},
      "stats": [
        {{ "label": "<Relevant Metric>", "value": "<Sample Value>", "sub": "<Context>", "color": "blue" }}
      ],
      "tabs": ["<Tab 1>", "<Tab 2>"],
      "sections": [
        {{
          "section_name": "<Real Form / Table Section Name>",
          "type": "form | table | cards",
          "fields": [
            {{ "label": "<Real Field Name from SRS>", "type": "text | select | date | toggle | textarea", "default_value": "<Realistic Domain Value>", "required": true }}
          ],
          "buttons": [
            {{ "label": "<Action Button Label>", "variant": "primary | secondary | outline" }}
          ],
          "table_headers": ["<Col 1>", "<Col 2>", "<Col 3>"],
          "table_rows": [["<Val 1>", "<Val 2>", "<Val 3>"]]
        }}
      ],
      "connected_use_cases": ["UC-001: <Use Case Title>"],
      "connected_req_codes": ["REQ-001"]
    }}
  ],

  "traceability_matrix": [
    {{
      "req_code": "<Real REQ Code from SRS/Requirements>",
      "req_title": "<Real Requirement Title>",
      "doc_name": "<Source Filename from KB>",
      "doc_type": "SRS / TOR / Requirement",
      "sitemap_node_title": "<Matching Sitemap Node Title>",
      "use_case_id": "UC-001: <Title>",
      "screen_id": "SCR-MOD-01",
      "screen_name": "<Matching Screen Name>",
      "test_cases": ["TC-001: <Positive Scenario>", "TC-002: <Negative/Error Scenario>"],
      "defect_log": [],
      "uat_item": "UAT-001: <Acceptance Verification Clause>",
      "uat_ref": "<Section / Acceptance Criteria Ref>",
      "uat_status": "Ready for UAT",
      "status": "Covered"
    }}
  ],

  "summary_stats": {{
    "total_modules": 4,
    "total_screens": 6,
    "total_use_cases": 8,
    "total_requirements": 12,
    "coverage_percentage": 95,
    "executive_summary": "<Comprehensive Thai executive summary of architecture, user journeys, integration points, and QA coverage>"
  }}
}}

Make sure:
1. All Sitemap nodes, Diagrams, Screen Mockups, and Traceability Matrix are deeply interconnected with matching IDs (`screen_id`, `req_code`, `use_case_id`).
2. Cover EVERY major module, screen, and requirement from the project documents (do not skip screens or summarize them away).
3. All Mermaid syntax MUST be valid Mermaid 10+. Avoid raw HTML tags inside Mermaid node text; wrap labels containing special characters/Thai text in double quotes.
4. Do NOT output markdown code blocks around the JSON (no ```json ... ```), output raw JSON only.
"""

        logger.info(f"Agent 7: Generating high-precision flow analysis & diagrams for project {project_name} ({project_id})...")
        model_to_use = os.environ.get("GEMINI_DOC_MODEL", "gemini-2.5-pro")
        raw_text, usage_metadata = call_gemini(prompt, model_name=model_to_use, max_output_tokens=32768)

        if usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_7_Flow_Analyzer", model_to_use, usage_metadata)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Agent 7: {log_err}")

        # Robust JSON parsing (supports multi-line Mermaid strings and unescaped control chars)
        def robust_json_loads(text: str) -> dict:
            if not text:
                return {}
            clean = text.strip()
            if "```json" in clean:
                clean = clean.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in clean:
                clean = clean.split("```", 1)[1].split("```", 1)[0]
            clean = clean.strip()

            try:
                return json.loads(clean, strict=False)
            except Exception:
                pass

            match = re.search(r'(\{[\s\S]*\})', clean)
            if match:
                try:
                    return json.loads(match.group(1), strict=False)
                except Exception:
                    pass

            cleaned_trailing = re.sub(r',\s*([\]}])', r'\1', clean)
            try:
                return json.loads(cleaned_trailing, strict=False)
            except Exception:
                pass

            match = re.search(r'(\{[\s\S]*\})', cleaned_trailing)
            if match:
                return json.loads(match.group(1), strict=False)

            return json.loads(clean, strict=False)

        data = robust_json_loads(raw_text)
        if not data or not isinstance(data, dict):
            logger.warning("Agent 7: Parsed JSON is empty or not a dict! Falling back to empty structure.")
            data = {}

        sitemap_data = data.get("sitemap", [])
        system_flowchart = clean_mermaid_code(data.get("system_flowchart", ""))
        usecase_diagram = clean_mermaid_code(data.get("usecase_diagram", ""))
        activity_diagram = clean_mermaid_code(data.get("activity_diagram", ""))
        sequence_diagram = clean_mermaid_code(data.get("sequence_diagram", ""))
        screen_mockups = ensure_all_screen_mockups(sitemap_data, data.get("screen_mockups", []), project_name)
        screen_mockups = _merge_preserved_wireframe_assets(screen_mockups, existing_mockups)
        traceability_matrix = data.get("traceability_matrix", [])
        summary_stats = data.get("summary_stats", {})

        # Compute accurate summary counts if missing or zero
        if isinstance(summary_stats, dict):
            summary_stats.setdefault("total_modules", len(sitemap_data))
            summary_stats.setdefault("total_screens", len(screen_mockups))
            summary_stats.setdefault("total_requirements", max(len(traceability_matrix), len(reqs_context)))

        if not system_flowchart and activity_diagram:
            system_flowchart = activity_diagram

        # 6. Save or Update in database
        conn = get_db_connection()
        cursor = conn.cursor()

        if existing_row:
            analysis_id = existing_row[0]
            cursor.execute("""
                UPDATE qa_analysis_diagrams
                SET sitemap_data = %s,
                    system_flowchart = %s,
                    usecase_diagram = %s,
                    activity_diagram = %s,
                    sequence_diagram = %s,
                    screen_mockups = %s,
                    traceability_matrix = %s,
                    summary_stats = %s,
                    status = 'Completed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
            """, (
                json.dumps(sitemap_data, ensure_ascii=False),
                system_flowchart,
                usecase_diagram,
                activity_diagram,
                sequence_diagram,
                json.dumps(screen_mockups, ensure_ascii=False),
                json.dumps(traceability_matrix, ensure_ascii=False),
                json.dumps(summary_stats, ensure_ascii=False),
                analysis_id
            ))
        else:
            cursor.execute("""
                INSERT INTO qa_analysis_diagrams (
                    project_id, sitemap_data, system_flowchart, usecase_diagram, activity_diagram,
                    sequence_diagram, screen_mockups, traceability_matrix, summary_stats, status
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, 'Completed'
                ) RETURNING id
            """, (
                project_id,
                json.dumps(sitemap_data, ensure_ascii=False),
                system_flowchart,
                usecase_diagram,
                activity_diagram,
                sequence_diagram,
                json.dumps(screen_mockups, ensure_ascii=False),
                json.dumps(traceability_matrix, ensure_ascii=False),
                json.dumps(summary_stats, ensure_ascii=False)
            ))
            analysis_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Successfully saved flow analysis (ID: {analysis_id}) for project {project_id}")
        return True, {
            "id": str(analysis_id),
            "project_id": str(project_id),
            "sitemap": sitemap_data,
            "system_flowchart": system_flowchart,
            "usecase_diagram": usecase_diagram,
            "activity_diagram": activity_diagram,
            "sequence_diagram": sequence_diagram,
            "screen_mockups": screen_mockups,
            "traceability_matrix": traceability_matrix,
            "summary_stats": summary_stats,
            "status": "Completed"
        }

    except Exception as e:
        logger.error(f"Error in analyze_project_flow_and_diagrams: {e}", exc_info=True)
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False, str(e)


def get_project_flow_analysis(project_id: str):
    """
    Fetches the latest saved flow analysis for a project.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT d.id, d.sitemap_data, d.usecase_diagram, d.activity_diagram,
                   d.sequence_diagram, d.screen_mockups, d.traceability_matrix, d.summary_stats,
                   d.status, d.updated_at, d.system_flowchart, p.project_name
            FROM qa_analysis_diagrams d
            LEFT JOIN projects p ON d.project_id = p.project_id
            WHERE d.project_id = %s::uuid
            ORDER BY d.updated_at DESC LIMIT 1
        """, (project_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return None

        system_flowchart_val = row[10] if len(row) > 10 and row[10] else (row[3] or "")
        proj_name = row[11] if len(row) > 11 and row[11] else "System"
        sitemap_val = row[1] or []
        mockups_val = ensure_all_screen_mockups(sitemap_val, row[5] or [], proj_name)

        return {
            "id": str(row[0]),
            "project_id": str(project_id),
            "sitemap": sitemap_val,
            "system_flowchart": system_flowchart_val,
            "usecase_diagram": row[2] or "",
            "activity_diagram": row[3] or "",
            "sequence_diagram": row[4] or "",
            "screen_mockups": mockups_val,
            "traceability_matrix": row[6] or [],
            "summary_stats": row[7] or {},
            "status": row[8],
            "updated_at": row[9].isoformat() if row[9] else None
        }
    except Exception as e:
        logger.error(f"Error fetching flow analysis: {e}", exc_info=True)
        return None


def get_diagram_context_for_agents(project_id: str, include_mockups: bool = True, include_matrix: bool = True) -> str:
    """
    Canonical cross-agent context formatter for QA Document Creation, QA Consult,
    QA Research, QA Test Automation, and Alignment Agents.
    Returns a clean, structured Markdown summary of the project's saved QA Analysis Diagram.
    """
    if not project_id or str(project_id).strip().lower() in ('', 'none', 'null'):
        return ""
    try:
        flow = get_project_flow_analysis(str(project_id))
        if not flow:
            return ""

        parts = ["# System Architecture, Workflows & Screen Map (from QA Analysis Diagram)"]

        stats = flow.get("summary_stats") or {}
        if stats.get("executive_summary"):
            parts.append(f"**Executive Architecture Summary:** {stats['executive_summary']}")

        sitemap = flow.get("sitemap") or []
        if sitemap:
            sm_lines = ["## Sitemap & Module Hierarchy"]
            for node in sitemap[:20]:
                sm_lines.append(f"- **{node.get('title', '')}** (`{node.get('path', '/')}`, Screen: `{node.get('screen_id', '-')}`): {node.get('description', '')}")
                for ch in (node.get("children") or [])[:8]:
                    sm_lines.append(f"  - {ch.get('title', '')} (`{ch.get('path', '/')}`, Screen: `{ch.get('screen_id', '-')}`): {ch.get('description', '')}")
            parts.append("\n".join(sm_lines))

        if flow.get("system_flowchart"):
            parts.append(f"## End-to-End System Flowchart (Mermaid)\n```mermaid\n{flow['system_flowchart'][:4500]}\n```")

        if flow.get("usecase_diagram"):
            parts.append(f"## Use Case Architecture (Mermaid)\n```mermaid\n{flow['usecase_diagram'][:3000]}\n```")

        if flow.get("sequence_diagram"):
            parts.append(f"## System Sequence & API Flow (Mermaid)\n```mermaid\n{flow['sequence_diagram'][:3500]}\n```")

        if include_mockups and flow.get("screen_mockups"):
            scr_lines = ["## Screen Specifications & UI Fields"]
            for m in (flow.get("screen_mockups") or [])[:15]:
                field_names = []
                for sec in (m.get("sections") or []):
                    for f in (sec.get("fields") or []):
                        if f.get("label"):
                            field_names.append(f["label"])
                fields_str = f" | Fields: {', '.join(field_names[:8])}" if field_names else ""
                reqs_str = f" | REQs: {', '.join(m.get('connected_req_codes') or [])}" if m.get("connected_req_codes") else ""
                scr_lines.append(f"- **[{m.get('screen_id', '')}] {m.get('screen_name', '')}** (`{m.get('route', '/')}`): {m.get('description', '')}{fields_str}{reqs_str}")
            parts.append("\n".join(scr_lines))

        if include_matrix and flow.get("traceability_matrix"):
            tm_lines = ["## Bidirectional Traceability Matrix (REQ -> Screen -> Test Cases -> UAT)"]
            for row in (flow.get("traceability_matrix") or [])[:35]:
                tcs = ", ".join((row.get("test_cases") or [])[:4]) if isinstance(row.get("test_cases"), list) else str(row.get("test_cases") or "")
                tm_lines.append(
                    f"- [{row.get('req_code', '-')}] {row.get('req_title', '')} -> Screen: {row.get('screen_id', '-')} ({row.get('screen_name', '')}) | UC: {row.get('use_case_id', '-')} | TCs: {tcs} | UAT: {row.get('uat_item', '-')}"
                )
            parts.append("\n".join(tm_lines))

        return "\n\n".join(parts) + "\n"
    except Exception as err:
        logger.warning(f"Failed to format diagram context for project {project_id}: {err}")
        return ""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Agent 7 Flow Analyzer Module loaded.")
