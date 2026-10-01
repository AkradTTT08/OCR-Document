"""
MCP Server สำหรับระบบ Spectra QA - Agent QA Consult
ใช้สำหรับเชื่อมต่อ AI Agents ภายนอก (เช่น Claude Desktop, Cursor, Custom Agents)
ผ่านโปรโตคอล Model Context Protocol (MCP) เพื่อทำหน้าที่เป็น QA Consult Agent โดยเฉพาะ
"""
import os
import sys
import io
import json
import logging
import socket
import ipaddress
from urllib.parse import urlparse
from PIL import Image

from mcp.server.fastmcp import FastMCP

# ตั้งค่า Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mcp_qa_consult_server")

# สร้าง MCP Server
mcp = FastMCP("Spectra QA Consult Server", host="0.0.0.0")

# ==========================================
# Helper Utilities & Security
# ==========================================

def _is_url(path: str) -> bool:
    try:
        result = urlparse(path)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def _is_safe_url(url: str) -> bool:
    """ตรวจสอบ SSRF ป้องกันไม่ให้เข้าถึง Private/Local IP"""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Resolve to IP
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
            logger.warning(f"SSRF Blocked: Attempted to access private IP {ip}")
            return False
            
        return True
    except Exception as e:
        logger.warning(f"URL Resolution failed: {e}")
        return False

# ==========================================
# Tool 1: OCR & Document Extraction
# ==========================================

@mcp.tool()
def ocr_document(source: str, lang: str = "tha+eng") -> str:
    """
    Extracts structured text/markdown from a document (PDF or Image) using GLM-OCR / Vision OCR.
    
    Args:
        source: Absolute path to a local file, or a direct HTTP/HTTPS URL to the file.
        lang: Language for extraction (default 'tha+eng').
        
    Returns:
        The extracted markdown text from the document.
    """
    from ocr_engine import ocr_pdf_bytes, ocr_image
    
    logger.info(f"Processing OCR request for source: {source}")
    file_bytes = None
    is_pdf = False
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
    
    if _is_url(source):
        if not _is_safe_url(source):
            return "Error: URL is not safe or accesses a private internal network."
            
        try:
            import requests
            logger.info("Downloading file from URL...")
            response = requests.get(source, stream=True, timeout=30)
            response.raise_for_status()
            
            content_length = response.headers.get('Content-Length')
            if content_length and int(content_length) > MAX_FILE_SIZE:
                return "Error: File size exceeds the 50MB limit."
                
            downloaded_bytes = io.BytesIO()
            size = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded_bytes.write(chunk)
                    size += len(chunk)
                    if size > MAX_FILE_SIZE:
                        return "Error: File size exceeds the 50MB limit."
            
            file_bytes = downloaded_bytes.getvalue()
            content_type = response.headers.get('Content-Type', '').lower()
            if 'pdf' in content_type or source.lower().endswith('.pdf'):
                is_pdf = True
        except Exception as e:
            return f"Error downloading file from URL: {str(e)}"
    else:
        if not os.path.exists(source):
            return f"Error: Local file not found at path {source}"
            
        try:
            with open(source, 'rb') as f:
                file_bytes = f.read()
            if source.lower().endswith('.pdf'):
                is_pdf = True
        except Exception as e:
            return f"Error reading local file: {str(e)}"
            
    try:
        extracted_text = ""
        if is_pdf:
            logger.info("Processing as PDF...")
            results = ocr_pdf_bytes(file_bytes, lang=lang)
            for page in results:
                if 'error' in page and page['error']:
                    extracted_text += f"\n\n--- Error on Page {page.get('page_number')} ---\n{page['error']}"
                else:
                    extracted_text += f"\n\n--- Page {page.get('page_number')} ---\n{page.get('text', '')}"
        else:
            logger.info("Processing as Image...")
            image = Image.open(io.BytesIO(file_bytes))
            result = ocr_image(image, lang=lang)
            if 'error' in result and result['error']:
                return f"Error during OCR: {result['error']}"
            extracted_text = result.get('text', '')
            
        logger.info("OCR Processing complete.")
        
        # Ingest document if filename is available
        try:
            from db_ingestion import ingest_markdown_document
            filename = os.path.basename(source) if not _is_url(source) else source.split('/')[-1]
            if not filename:
                filename = "mcp_scanned_document.md"
            ingest_markdown_document(filename, extracted_text.strip())
        except Exception as ingest_error:
            logger.warning(f"Note: Document ingestion skipped or failed: {ingest_error}")
            
        return extracted_text.strip()
        
    except Exception as e:
        return f"Unexpected error during OCR processing: {str(e)}"

def _resolve_project(project_id_or_code: str):
    """Resolves project ID, name, and code from UUID, project_code, or project_name."""
    if not project_id_or_code:
        return "", "General Project", ""
    try:
        from db_ingestion import get_projects
        projects = get_projects()
        clean_target = str(project_id_or_code).strip().lower()
        for p in projects:
            p_id = str(p.get("id") or p.get("project_id", "")).strip().lower()
            p_code = str(p.get("project_code", "")).strip().lower()
            p_name = str(p.get("name") or p.get("project_name", "")).strip().lower()
            if clean_target in [p_id, p_code, p_name]:
                return str(p.get("id") or p.get("project_id")), (p.get("name") or p.get("project_name") or "Project"), (p.get("project_code") or "")
        return str(project_id_or_code), "Project", ""
    except Exception as e:
        logger.warning(f"Error resolving project: {e}")
        return str(project_id_or_code), "Project", ""

# ==========================================
# Tool 2: Project & Group Management
# ==========================================

@mcp.tool()
def list_projects() -> str:
    """
    Retrieves the list of all available QA projects in the system.
    Returns project ID, code, name, description, status, and document counts.
    """
    try:
        from db_ingestion import get_projects
        projects = get_projects()
        return json.dumps(projects, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error in list_projects: {e}", exc_info=True)
        return json.dumps({"status": "ERROR", "message": str(e)})

@mcp.tool()
def list_groups(project_id: str = None) -> str:
    """
    Retrieves the list of existing QA Groups in a given project.
    
    Args:
        project_id: (Optional) The UUID or Code of the project. If not provided, lists all QA groups.
        
    Returns:
        JSON list of existing groups (group_name, group_type, project_id, project_code, created_at).
    """
    try:
        from db_ingestion import get_qa_groups
        resolved_pid = None
        if project_id:
            resolved_pid, _, _ = _resolve_project(project_id)
        groups = get_qa_groups(project_id=resolved_pid)
        return json.dumps(groups, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error in list_groups: {e}", exc_info=True)
        return json.dumps({"status": "ERROR", "message": str(e)})

# ==========================================
# Tool 3: Project Context & Knowledge Base (RAG)
# ==========================================

@mcp.tool()
def get_project_context(project_id: str, query: str = "") -> str:
    """
    Fetches the Knowledge Base (RAG) context, active Markdown documents, and golden reference data for a given project.
    Only retrieves resources that exist within that specific project.
    
    Args:
        project_id: The UUID or Code of the project.
        query: (Optional) A specific search query to retrieve semantic matching document chunks.
        
    Returns:
        JSON string containing the project documents list and relevant RAG context chunks.
    """
    try:
        from db_ingestion import get_project_markdown_documents_summary, search_knowledge_base
        resolved_pid, proj_name, proj_code = _resolve_project(project_id)
        
        # 1. Available MD Documents in this project only
        docs_summary = get_project_markdown_documents_summary(resolved_pid, limit=20)
        
        # 2. Semantic Search strictly scoped to this project
        search_chunks = []
        if query and query.strip():
            search_chunks = search_knowledge_base(query_text=query, project_id=resolved_pid, top_k=6)
            
        result = {
            "project_id": resolved_pid,
            "project_code": proj_code,
            "project_name": proj_name,
            "available_documents": docs_summary,
            "relevant_knowledge_chunks": search_chunks
        }
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error in get_project_context: {e}", exc_info=True)
        return json.dumps({"status": "ERROR", "message": str(e)})

# ==========================================
# Tool 4: QA Skills & Standards
# ==========================================

@mcp.tool()
def get_qa_skills(skill_id: str = None) -> str:
    """
    Retrieves the list of active QA consulting skills, guidelines, and review standards.
    
    Args:
        skill_id: (Optional) Specific skill UUID or name to fetch detailed instructions for.
    """
    try:
        from db_ingestion import get_db_connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        if skill_id:
            cur.execute(
                "SELECT skill_id, skill_name, skill_description, markdown_instructions, target_doc_type "
                "FROM agent_skills WHERE skill_id::text = %s OR skill_name ILIKE %s LIMIT 1",
                (skill_id, f"%{skill_id}%")
            )
            row = cur.fetchone()
            if row:
                res = {
                    "skill_id": str(row[0]),
                    "skill_name": row[1],
                    "description": row[2],
                    "markdown_instructions": row[3],
                    "target_doc_type": row[4]
                }
            else:
                res = {"status": "NOT_FOUND", "message": f"Skill '{skill_id}' not found."}
        else:
            cur.execute(
                "SELECT skill_id, skill_name, skill_description, target_doc_type "
                "FROM agent_skills WHERE is_active = TRUE ORDER BY skill_name ASC;"
            )
            rows = cur.fetchall()
            res = [
                {
                    "skill_id": str(r[0]),
                    "skill_name": r[1],
                    "description": r[2],
                    "target_doc_type": r[3]
                }
                for r in rows
            ]
            
        cur.close()
        conn.close()
        return json.dumps(res, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error in get_qa_skills: {e}", exc_info=True)
        return json.dumps({"status": "ERROR", "message": str(e)})

# ==========================================
# Tool 5: QA Consult (Deep Audit & Cross-check)
# ==========================================

@mcp.tool()
def qa_consult(
    project_id: str,
    document_content: str,
    group_name: str = "General",
    group_type: str = "Project Plan",
    doc_type: str = None,
    skill_id: str = None,
    email: str = None,
    filename: str = "MCP_Audited_Document.md",
    instruction: str = ""
) -> str:
    """
    Runs the Agent QA Consult multi-agent analysis to audit, cross-examine, and review a document against the project's knowledge base.
    Evaluates Exit Criteria according to the selected Group/Project and saves the result to QA transactions.
    
    Args:
        project_id: (Required) The UUID or Project Code of the project.
        document_content: (Required) The full markdown/text content of the document to audit.
        group_name: (Optional) The QA Group name in the project (e.g., 'Sprint 1', 'General'). Defaults to 'General'.
        group_type: (Optional) The QA Group type (e.g., 'Project Plan', 'Sprint 1', 'Release'). Defaults to 'Project Plan'.
        doc_type: (Optional) Type of document (e.g., 'Requirement', 'SRS', 'SDD', 'TestCase', 'Usermanual', 'UAT'). If not provided, automatically detected.
        skill_id: (Optional) Specific AI Skill ID or skill name to guide the audit.
        email: (Optional) User email to record with the transaction and receive report.
        filename: (Optional) Name of the document (e.g., 'MOM_REQ_01.pdf').
        instruction: (Optional) Custom review instructions or specific focus points.
        
    Returns:
        Structured QA Audit Report covering Conformity, Errors/Discrepancies, Missing Requirements, Exit Criteria Evaluation, and Actionable Recommendations.
    """
    try:
        from orchestrator.state import QAState
        from orchestrator.pipeline import run_qa_consult
        from db_ingestion import search_knowledge_base, get_latest_qa_transaction, save_qa_transaction, get_project_markdown_documents_summary
        
        # 1. Resolve Project
        resolved_pid, project_name, project_code = _resolve_project(project_id)
        
        # 2. Retrieve project documents and knowledge base context (Scoped ONLY to this project)
        available_md_docs = get_project_markdown_documents_summary(resolved_pid, limit=20)
        
        is_explicit = bool(doc_type and doc_type.strip())
        kb_chunks = search_knowledge_base(
            query_text=document_content[:2000],
            doc_type=[doc_type] if is_explicit else None,
            project_id=resolved_pid,
            top_k=6
        )
        
        kb_context = ""
        if kb_chunks:
            kb_context = f"=== ข้อมูลอ้างอิงจากฐานข้อมูลโครงการ {project_name} ({project_code}) ===\n"
            for c in kb_chunks:
                kb_context += f"- [Source: {c.get('filename', 'Doc')} | Category: {c.get('doc_category', '')}]: {c.get('chunk_text', '')}\n\n"
                
        # 3. Retrieve AI Skill instructions if skill_id provided
        skill_instructions = ""
        if skill_id:
            try:
                from db_ingestion import get_db_connection
                _conn = get_db_connection()
                _cur = _conn.cursor()
                _cur.execute("SELECT markdown_instructions FROM agent_skills WHERE skill_id::text = %s OR skill_name ILIKE %s LIMIT 1", (skill_id, f"%{skill_id}%"))
                _srow = _cur.fetchone()
                if _srow and _srow[0]:
                    skill_instructions = _srow[0]
                _cur.close()
                _conn.close()
            except Exception as s_err:
                logger.warning(f"Failed to fetch skill instructions: {s_err}")
                
        # 4. Fetch previous transaction in this group if exists
        prev_report_context = ""
        try:
            prev_tx = get_latest_qa_transaction(resolved_pid, filename=filename, group_name=group_name)
            if prev_tx:
                prev_findings_text = ""
                if prev_tx.get('qa_findings'):
                    prev_findings_text = "\n### ประเด็นที่พบในรอบก่อนหน้า:\n" + "\n".join([
                        f"- [{f.get('severity','Info')}] {f.get('issue','')} (ข้อเสนอแนะ: {f.get('recommendation','-')})"
                        for f in (prev_tx.get('qa_findings') or [])[:10]
                    ])
                prev_report_context = f"=== ประวัติการตรวจสอบรอบก่อนหน้าในกลุ่ม '{group_name}' ===\n{prev_findings_text}\n\n{prev_tx.get('qa_report','')}\n"
        except Exception as ptx_err:
            logger.warning(f"Could not fetch prev transaction: {ptx_err}")
            
        # 5. Formulate consult instruction
        full_instruction = (
            f"กรุณาวิเคราะห์และจัดทำรายงาน QA Consult Audit Report สำหรับโครงการ '{project_name}' ({project_code}) ในกลุ่ม '{group_name}':\n"
            f"1. ความสอดคล้อง (Conformity): ตรวจสอบความสอดคล้องกับเอกสารอ้างอิงและมาตรฐานในโครงการเท่านั้น\n"
            f"2. จุดที่พบข้อผิดพลาดหรือขัดแย้ง (Discrepancies / Errors): มีส่วนใดที่ไม่ตรงกับฐานข้อมูลโครงการ หรือผิดมาตรฐาน\n"
            f"3. สิ่งที่ขาดหายไป (Missing Information): ข้อมูลสำคัญหรือเงื่อนไขทางเทคนิคที่ควรมี\n"
            f"4. ข้อเสนอแนะแนวทางปรับปรุง (Recommendations)\n\n"
        )
        if is_explicit:
            full_instruction += f"ประเภทเอกสารเป้าหมาย: {doc_type}\n"
        elif available_md_docs:
            full_instruction += f"เอกสารอ้างอิงในโครงการที่มี ({len(available_md_docs)} รายการ):\n"
            for idx, d in enumerate(available_md_docs, 1):
                full_instruction += f"- {idx}. {d['filename']} (หมวดหมู่: {d['category']})\n"
                
        if instruction:
            full_instruction += f"\nคำสั่งหรือข้อกำหนดเพิ่มเติมจากผู้ใช้:\n{instruction}\n"
            
        state = QAState(
            project_id=resolved_pid,
            project_name=project_name,
            doc_type=doc_type if is_explicit else "ไม่ระบุ (Auto-detect)",
            skill_instructions=skill_instructions,
            kb_context=kb_context,
            prev_report_context=prev_report_context,
            original_text=document_content[:250000],
            instruction=full_instruction
        )
        
        result_state = run_qa_consult(state)
        
        if result_state.status == "failed":
            return json.dumps({
                "status": "ERROR",
                "message": f"QA Consult failed: {result_state.error}"
            }, ensure_ascii=False)
            
        qa_report_content = getattr(result_state, 'report', None) or getattr(result_state, 'final_report', None) or ""
        
        # 6. Parse findings & Evaluate Exit Criteria
        qa_findings = []
        try:
            from excel_report import parse_qa_report_with_ai
            qa_findings = parse_qa_report_with_ai(qa_report_content, filename)
        except Exception as pf_err:
            logger.warning(f"Findings parsing note: {pf_err}")
            
        exit_criteria_eval = None
        try:
            from app import evaluate_document_exit_criteria
            doc_type_eval = doc_type if doc_type else (group_type or 'ALL')
            exit_criteria_eval = evaluate_document_exit_criteria(
                document_content,
                doc_type=doc_type_eval,
                project_id=resolved_pid,
                qa_findings=qa_findings
            )
        except Exception as eval_err:
            logger.warning(f"Exit criteria evaluation note: {eval_err}")
            
        # 7. Save transaction to QA database
        transaction_id = None
        try:
            transaction_id = save_qa_transaction(
                project_id=resolved_pid,
                group_name=group_name,
                group_type=group_type,
                filename=filename,
                doc_type=doc_type or "Auto-detect",
                extracted_text=document_content[:250000],
                qa_report=qa_report_content,
                total_pages=1,
                email=email,
                qa_findings=qa_findings,
                exit_criteria_eval=exit_criteria_eval,
                project_code=project_code,
                project_name=project_name
            )
        except Exception as save_err:
            logger.error(f"Error saving QA transaction in MCP: {save_err}")
            
        # 8. Send email report if requested
        if email:
            try:
                from email_service import send_qa_report
                send_qa_report(email, doc_type or "QA Consult", filename, qa_report_content, exit_criteria_eval=exit_criteria_eval)
            except Exception as mail_err:
                logger.warning(f"Email send error: {mail_err}")
                
        return json.dumps({
            "status": "SUCCESS",
            "transaction_id": transaction_id,
            "project_id": resolved_pid,
            "project_code": project_code,
            "project_name": project_name,
            "group_name": group_name,
            "group_type": group_type,
            "doc_type": doc_type or "Auto-detect",
            "exit_criteria": exit_criteria_eval,
            "qa_findings": qa_findings,
            "qa_report": qa_report_content
        }, indent=2, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Error in qa_consult tool: {e}", exc_info=True)
        return json.dumps({"status": "ERROR", "message": str(e)}, ensure_ascii=False)

# ==========================================
# Tool 6: Exit Criteria & QA Evaluation
# ==========================================

@mcp.tool()
def evaluate_spectra_qa(
    document_content: str,
    project_id: str = None,
    group_name: str = "General",
    group_type: str = "Project Plan",
    document_type: str = "Requirement",
    target_email: str = "",
    ai_skill: str = None,
    filename: str = "MCP_Document.md",
    session_id: str = None
) -> str:
    """
    Evaluates a document's content against Spectra QA Exit Criteria, Rules, and Project Knowledge Base.
    
    Args:
        document_content: The full text/markdown content of the drafted document.
        project_id: (Optional) The UUID or Code of the project.
        group_name: (Optional) The QA Group name in the project (e.g., 'Sprint 1', 'General'). Defaults to 'General'.
        group_type: (Optional) The QA Group type (e.g., 'Project Plan', 'Sprint 1'). Defaults to 'Project Plan'.
        document_type: (Optional) Category of the document (e.g. 'Requirement', 'SRS', 'SDD', 'TestCase', 'Manual', 'ALL').
        target_email: (Optional) The email address to send the final report to (used for session tracking).
        ai_skill: (Optional) The specific AI Skill or Skill ID to use for evaluation.
        filename: (Optional) The filename of the document being evaluated.
        session_id: (Optional) The session ID from a previous evaluation attempt to track circuit breaker loops.
        
    Returns:
        A JSON string containing the evaluation status (PASS/REJECTED), circuit_breaker_hit flag, failed criteria, and recommendations.
    """
    import requests
    backend_base = os.environ.get("BACKEND_INTERNAL_URL") or ("http://backend:5000" if os.environ.get("DB_HOST") == "qa_agent_db" else "http://127.0.0.1:5000")
    url = f"{backend_base}/api/mcp/submit_document"
    payload = {
        "document_content": document_content,
        "document_type": document_type,
        "group_name": group_name or "General",
        "group_type": group_type or "Project Plan",
        "filename": filename or "MCP_Document.md",
        "target_email": target_email or "qa-consult@spectra.local"
    }
    
    if project_id: payload["project_id"] = project_id
    if ai_skill: payload["ai_skill"] = ai_skill
    if session_id: payload["session_id"] = session_id
        
    try:
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=60)
        response.raise_for_status()
        return json.dumps(response.json(), indent=2, ensure_ascii=False)
    except Exception as e:
        # Fallback to direct python evaluation if local Flask server is not reachable
        try:
            from app import evaluate_document_exit_criteria
            resolved_pid = None
            if project_id:
                resolved_pid, _, _ = _resolve_project(project_id)
            eval_result = evaluate_document_exit_criteria(document_content, doc_type=document_type, project_id=resolved_pid, qa_findings=[])
            final_status = eval_result.get('status')
            failed_criteria_list = [
                f"ข้อ {item.get('item_code')}: {item.get('question_text')} - {item.get('remarks')}"
                for item in eval_result.get('items', []) if item.get('status') == 'FAIL'
            ]
            return json.dumps({
                "status": "PASS" if final_status in ['PASSED', 'CONDITIONAL_PASSED'] else "REJECTED",
                "circuit_breaker_hit": False,
                "failed_criteria": failed_criteria_list,
                "recommendation": eval_result.get('summary_remarks', '')
            }, indent=2, ensure_ascii=False)
        except Exception as fallback_err:
            return json.dumps({
                "status": "ERROR",
                "message": f"Failed to evaluate document: {str(e)} (Fallback error: {fallback_err})"
            }, ensure_ascii=False)

# ==========================================
# Tool 7: Send QA Report Email
# ==========================================

@mcp.tool()
def send_email_report(to_email: str, subject: str, report_body: str) -> str:
    """
    Sends an email report containing the final QA Consult evaluation, audit report, or summary.
    
    Args:
        to_email: The recipient's email address.
        subject: The subject of the email (e.g., 'QA Audit Report: Login Module').
        report_body: The main content / markdown of the QA report.
        
    Returns:
        A success or error message.
    """
    try:
        import requests
        backend_base = os.environ.get("BACKEND_INTERNAL_URL") or ("http://backend:5000" if os.environ.get("DB_HOST") == "qa_agent_db" else "http://127.0.0.1:5000")
        url = f"{backend_base}/api/qa_send_email"
        payload = {
            "email": to_email,
            "docType": "QA Consult Audit",
            "filename": subject,
            "report": report_body
        }
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=15)
        response.raise_for_status()
        res_data = response.json()
        if res_data.get('success'):
            return "Email sent successfully."
        else:
            return f"Failed to send email: {res_data.get('error', 'Unknown error')}"
    except Exception as e:
        # Fallback to direct email service
        try:
            from email_service import send_qa_report
            send_qa_report(to_email, "QA Consult Audit", subject, report_body)
            return "Email sent successfully via direct service."
        except Exception as direct_err:
            return f"Failed to send email: {str(e)} (Direct error: {direct_err})"


# ==========================================
# Server Entrypoint
# ==========================================

if __name__ == "__main__":
    # Check if SSE mode is explicitly requested
    is_sse = "--sse" in sys.argv or os.environ.get("MCP_TRANSPORT", "").lower() == "sse"
    
    if is_sse:
        logger.info("Starting Spectra QA Consult MCP Server on SSE transport (Port 8000)...")
        import uvicorn
        app = mcp.sse_app()

        async def logging_middleware(scope, receive, send):
            has_sent_padding = False
            if scope["type"] == "http":
                logger.info(f">>> Incoming Request: {scope['method']} {scope['path']}")

            async def logging_send(message):
                nonlocal has_sent_padding
                if message["type"] == "http.response.start":
                    headers = message.get("headers", [])
                    new_headers = []
                    is_sse_stream = False
                    for k, v in headers:
                        if k.lower() == b"content-type" and b"text/event-stream" in v.lower():
                            is_sse_stream = True
                        if k.lower() == b"cache-control":
                            v = v + b", no-transform"
                        new_headers.append((k, v))
                    if is_sse_stream:
                        new_headers = [(k, v) for k, v in new_headers if k.lower() != b"content-length"]
                    if not any(k.lower() == b"cache-control" for k, v in headers):
                        new_headers.append((b"cache-control", b"no-cache, no-transform"))
                    message["headers"] = new_headers
                elif message["type"] == "http.response.body":
                    body = message.get("body", b"")
                    if not has_sent_padding and scope.get("path", "").startswith("/sse"):
                        padding = b": " + (b"x" * 8192) + b"\n\n"
                        message["body"] = padding + body
                        has_sent_padding = True
                        
                await send(message)
            await app(scope, receive, logging_send)

        uvicorn.run(logging_middleware, host="0.0.0.0", port=8000, proxy_headers=True, forwarded_allow_ips="*")
    else:
        # Standard stdio mode for Claude Desktop / Cursor
        logger.info("Starting Spectra QA Consult MCP Server on stdio transport...")
        mcp.run(transport="stdio")
