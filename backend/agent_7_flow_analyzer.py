import json
import logging
import os
import datetime
from dotenv import load_dotenv

# Ensure environment variables are loaded
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(override=True)

import google.generativeai as genai
from db_ingestion import get_db_connection

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

def analyze_project_flow_and_diagrams(project_id: str, custom_instructions: str = ""):
    """
    Agent 7: QA Architecture, Flow & Diagram Analyzer
    Synthesizes project Markdown documents, RAG knowledge, and structured requirements into:
    1. Flow Sitemap (Hierarchical IA)
    2. UML & Flow Diagrams (Use Case, Activity, Sequence in Mermaid format)
    3. Interactive Screen Wireframes & UI Mockups
    4. Bidirectional Traceability Matrix
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

        # 2. Fetch all Markdown Documents stored in Project Knowledge Base
        cursor.execute("""
            SELECT doc_id, original_filename, doc_category, doc_type, full_markdown_content
            FROM documents
            WHERE project_id = %s::uuid AND status = 'Active'
            ORDER BY created_at DESC
        """, (project_id,))
        doc_rows = cursor.fetchall()

        docs_context = []
        for d in doc_rows:
            # Truncate very long documents if needed to fit token context
            content_snippet = (d[4] or "")[:6000]
            docs_context.append({
                "doc_id": str(d[0]),
                "filename": d[1],
                "category": d[2],
                "type": d[3],
                "content": content_snippet
            })

        # 3. Fetch Structured Requirements (Phase 1)
        cursor.execute("""
            SELECT req_code, title, description, category, steps, expected_results
            FROM structured_requirements
            WHERE project_id = %s::uuid
            ORDER BY req_code ASC
        """, (project_id,))
        req_rows = cursor.fetchall()
        reqs_context = []
        for r in req_rows:
            reqs_context.append({
                "req_code": r[0],
                "title": r[1],
                "description": r[2],
                "category": r[3],
                "steps": r[4],
                "expected_results": r[5]
            })

        # 4. Fetch Generated QA Documents (Test Cases / SRS)
        cursor.execute("""
            SELECT doc_name, doc_type, markdown_content
            FROM qa_generated_documents
            WHERE project_id = %s::uuid AND status = 'Completed'
            ORDER BY created_at DESC LIMIT 5
        """, (project_id,))
        qa_doc_rows = cursor.fetchall()
        qa_docs_context = []
        for q in qa_doc_rows:
            qa_docs_context.append({
                "doc_name": q[0],
                "doc_type": q[1],
                "snippet": (q[2] or "")[:3000]
            })

        cursor.close()
        conn.close()
        conn = None

        # 5. Configure Gemini AI
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured in .env")

        genai.configure(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name)

        user_instruction_section = ""
        if custom_instructions and custom_instructions.strip():
            user_instruction_section = f"""
# Additional Custom Instructions from User (High Priority)
{custom_instructions.strip()}
"""

        prompt = f"""
You are a Principal Software Architect, Senior QA Lead, and UX/System Analyst.
Your task is to analyze all the Markdown documents, knowledge base requirements, and workflows in project "{project_name}" ({project_code}) and construct a comprehensive, professional **System Flow & QA Architecture Model**.

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

{user_instruction_section}

---
# Output Format Requirements (MUST BE STRICT VALID JSON ONLY)
Generate a single, strict JSON object with the following keys and exact schema:

{{
  "sitemap": [
    {{
      "id": "node-1",
      "title": "Module / Page Title (e.g. Authentication / Login)",
      "path": "/login",
      "category": "Main / Admin / User / Service",
      "icon": "🔐 / 📊 / 📁 / ⚙️",
      "description": "Brief description of this page / module",
      "screen_id": "SCR-LOGIN",
      "use_case_ids": ["UC-001"],
      "children": [
        {{
          "id": "node-1-1",
          "title": "Forgot Password Modal",
          "path": "/forgot-password",
          "category": "Sub-page",
          "icon": "🔑",
          "description": "Password recovery flow",
          "screen_id": "SCR-FORGOT-PWD",
          "use_case_ids": ["UC-002"],
          "children": []
        }}
      ]
    }}
  ],

  "system_flowchart": "Mermaid syntax string for Complete End-to-End System Flowchart in Draw.io / Diagrams.net style e.g.
flowchart TD
  subgraph ClientLayer [🖥️ Client & Presentation Layer]
    Start([🏁 User Enters System]) --> SelectMenu[Select Module / Menu]
    SelectMenu --> FillForm[Fill Form / Upload File]
    FillForm --> ValidateClient{{Client Validation Passed?}}
    ValidateClient -->|No| ShowClientErr[⚠️ Display Form Error] --> FillForm
    ValidateClient -->|Yes| DispatchReq[🚀 Dispatch API Request]
  end

  subgraph GatewayLayer [🌐 API Gateway & Security Filter]
    DispatchReq --> CheckJWT{{JWT Token Valid & Authorized?}}
    CheckJWT -->|No 401| RejectAuth[⛔ Return 401 / 403 Error] --> Start
    CheckJWT -->|Yes| RateLimitCheck{{Rate Limit OK?}}
    RateLimitCheck -->|Exceeded| ThrottleResp[⏳ 429 Too Many Requests]
    RateLimitCheck -->|Pass| RouteService[🔀 Route to Target Service]
  end

  subgraph EngineLayer [🧠 Core Logic & AI Agents Execution]
    RouteService --> ExecuteLogic[⚙️ Process Business Transaction]
    ExecuteLogic --> AICheck{{Requires AI Agent / QA Ingestion?}}
    AICheck -->|Yes| InvokeLLM[🤖 Call Gemini / Embedding Agent]
    InvokeLLM --> AIEval{{Agent Quality Gate Passed?}}
    AIEval -->|Needs Healing| SelfHealLoop[🔄 Trigger Self-Healing] --> InvokeLLM
    AIEval -->|Passed| AggregateResult[📊 Build QA & Execution Result]
    AICheck -->|No| AggregateResult
  end

  subgraph DataLayer [💾 Persistence & External Systems]
    AggregateResult --> SavePostgres[('🗄️ Save to PostgreSQL / Vector DB')]
    SavePostgres --> AuditLog[📝 Write Audit Log & Event]
    AuditLog --> NotifyClient[🔔 Notify Client & Update Dashboard]
    NotifyClient --> EndFlow([🏁 End: Process Succeeded])
  end
",

  "usecase_diagram": "Mermaid syntax string for Use Case Diagram. Must be standard Mermaid format e.g.
flowchart LR
  subgraph SystemBoundary [System: {project_name}]
    UC1([UC-001: Login])
    UC2([UC-002: Upload Document])
    UC3([UC-003: Review Results])
  end
  User((Standard User)) --> UC1
  User --> UC2
  Admin((Admin)) --> UC1
  Admin --> UC3
  UC2 -.->|<<include>>| UC3
",

  "activity_diagram": "Mermaid syntax string for Activity / Process flow e.g.
flowchart TD
  Start([Start]) --> Login[User Login]
  Login --> CheckAuth{{Auth Valid?}}
  CheckAuth -- Yes --> SelectProject[Select Project]
  CheckAuth -- No --> ShowError[Show Error Message] --> Login
  SelectProject --> UploadDoc[Upload Document / Markdown]
  UploadDoc --> ProcessOCR[OCR & Extraction Engine]
  ProcessOCR --> Verify[QA Verification]
  Verify --> SaveKB[Save to Knowledge Base]
  SaveKB --> End([Complete])
",

  "sequence_diagram": "Mermaid syntax string for System Request-Response flow e.g.
sequenceDiagram
  autonumber
  actor User as Standard User
  participant UI as Svelte Frontend
  participant API as Backend API (Flask)
  participant AI as Gemini QA Agent
  participant DB as PostgreSQL / Vector DB

  User->>UI: Select Project & Upload Doc
  UI->>API: POST /api/kb/ingest
  API->>DB: Store Document Chunks & Embeddings
  API->>AI: Trigger Requirement Extraction
  AI-->>API: Return Structured Reqs
  API->>DB: Save Structured Reqs
  API-->>UI: Return Success Response
  UI-->>User: Display Ingested Confirmation
",

  "screen_mockups": [
    {{
      "screen_id": "SCR-LOGIN",
      "screen_name": "Login & Authentication Page",
      "route": "/login",
      "layout_type": "form",
      "description": "User authentication gateway with username, password, and remember me options",
      "header": {{
        "title": "Sign In to System",
        "badge": "Public",
        "actions": ["Language Toggle", "Dark Mode"]
      }},
      "sections": [
        {{
          "section_name": "Login Form Card",
          "type": "form",
          "fields": [
            {{ "label": "Username / Email", "type": "text", "placeholder": "admin@domain.com", "required": true }},
            {{ "label": "Password", "type": "password", "placeholder": "••••••••", "required": true }},
            {{ "label": "Remember Session", "type": "checkbox", "default": true }}
          ],
          "buttons": [
            {{ "label": "Sign In", "variant": "primary" }},
            {{ "label": "Forgot Password?", "variant": "link" }}
          ]
        }}
      ],
      "connected_use_cases": ["UC-001"],
      "connected_req_codes": ["REQ-001"]
    }}
  ],

  "traceability_matrix": [
    {{
      "req_code": "REQ-001",
      "req_title": "Requirement Title",
      "doc_name": "Original_Document.md",
      "doc_type": "SRS / Card / OCR",
      "sitemap_node_title": "Login Page",
      "use_case_id": "UC-001: User Login",
      "screen_id": "SCR-LOGIN",
      "screen_name": "Login & Authentication Page",
      "test_cases": ["TC-001: Valid Login", "TC-002: Invalid Password"],
      "status": "Covered"
    }}
  ],

  "summary_stats": {{
    "total_modules": 4,
    "total_screens": 6,
    "total_use_cases": 8,
    "total_requirements": 12,
    "coverage_percentage": 95,
    "executive_summary": "Comprehensive architecture synthesis summarizing core capabilities, user journeys, and QA coverage."
  }}
}}

Make sure:
1. All Sitemap nodes, Diagrams, Screen Mockups, and Traceability Matrix are deeply interconnected with matching IDs.
2. The Mermaid syntax MUST be valid and strictly compatible with Mermaid 10+. Avoid HTML tags inside Mermaid node text; use plain text with parenthesis/brackets.
3. The system_flowchart MUST be a rich Draw.io styled workflow diagram displaying tier subgraphs, decision branches, processes, and data stores.
4. Every screen mockup has realistic, detailed UI sections (cards, form fields, mock table headers/rows, badges, buttons) that reflect the true requirements.
5. Do NOT output markdown code blocks around the JSON (no ```json ... ```), output raw JSON only.
"""

        logger.info(f"Agent 7: Generating flow analysis & diagrams for project {project_name} ({project_id})...")
        resp = model.generate_content(prompt)
        
        if hasattr(resp, 'usage_metadata') and resp.usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_7_Flow_Analyzer", os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), resp.usage_metadata)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Agent 7: {log_err}")

        raw_text = resp.text.strip()

        # Clean JSON wrappers if any
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        data = json.loads(raw_text)

        sitemap_data = data.get("sitemap", [])
        system_flowchart = data.get("system_flowchart", "")
        usecase_diagram = data.get("usecase_diagram", "")
        activity_diagram = data.get("activity_diagram", "")
        sequence_diagram = data.get("sequence_diagram", "")
        screen_mockups = data.get("screen_mockups", [])
        traceability_matrix = data.get("traceability_matrix", [])
        summary_stats = data.get("summary_stats", {})

        # Fallback for system_flowchart if empty: use activity_diagram
        if not system_flowchart and activity_diagram:
            system_flowchart = activity_diagram

        # 6. Save or Update in database
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM qa_analysis_diagrams WHERE project_id = %s::uuid ORDER BY updated_at DESC LIMIT 1", (project_id,))
        existing_row = cursor.fetchone()

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
            except:
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
            SELECT id, sitemap_data, usecase_diagram, activity_diagram,
                   sequence_diagram, screen_mockups, traceability_matrix, summary_stats,
                   status, updated_at, system_flowchart
            FROM qa_analysis_diagrams
            WHERE project_id = %s::uuid
            ORDER BY updated_at DESC LIMIT 1
        """, (project_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return None

        system_flowchart_val = row[10] if len(row) > 10 and row[10] else (row[3] or "")

        return {
            "id": str(row[0]),
            "project_id": str(project_id),
            "sitemap": row[1] or [],
            "system_flowchart": system_flowchart_val,
            "usecase_diagram": row[2] or "",
            "activity_diagram": row[3] or "",
            "sequence_diagram": row[4] or "",
            "screen_mockups": row[5] or [],
            "traceability_matrix": row[6] or [],
            "summary_stats": row[7] or {},
            "status": row[8],
            "updated_at": row[9].isoformat() if row[9] else None
        }
    except Exception as e:
        logger.error(f"Error fetching flow analysis: {e}", exc_info=True)
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Agent 7 Flow Analyzer Module loaded.")
