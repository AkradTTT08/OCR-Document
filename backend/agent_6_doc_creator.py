import json
import logging
import os
import datetime
import uuid
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

def render_html_to_pdf(html_content: str, output_path: str):
    """
    Renders HTML content to a PDF file using Playwright (Chromium headless)
    with a fallback to ReportLab if Playwright encounters any issue.
    """
    # 1. Try Playwright
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html_content, wait_until="networkidle")
            page.pdf(
                path=output_path,
                format="A4",
                print_background=True,
                margin={"top": "15mm", "bottom": "15mm", "left": "15mm", "right": "15mm"}
            )
            browser.close()
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Playwright PDF generated successfully at {output_path}")
                return True
    except Exception as pw_err:
        logger.warning(f"Playwright PDF generation failed ({pw_err}), attempting fallback...")

    # 2. Try WeasyPrint if available
    try:
        import weasyprint
        weasyprint.HTML(string=html_content).write_pdf(output_path)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"WeasyPrint PDF generated successfully at {output_path}")
            return True
    except Exception:
        pass

    # 3. Fallback: ReportLab PDF Generator
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font_candidates = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/thai-scalable/Waree.ttf',
            'C:/Windows/Fonts/tahoma.ttf',
            'C:/Windows/Fonts/arial.ttf'
        ]
        font_registered = False
        for font_path in font_candidates:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('UnicodeFont', font_path))
                    font_registered = True
                    break
                except Exception:
                    pass

        font_name = 'UnicodeFont' if font_registered else 'Helvetica'

        doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        normal_style = ParagraphStyle('NormalUni', fontName=font_name, fontSize=10, leading=14)
        title_style = ParagraphStyle('TitleUni', fontName=font_name, fontSize=16, leading=20, alignment=1)

        import re
        clean_text = re.sub('<[^<]+?>', ' ', html_content)
        lines = [l.strip() for l in clean_text.split('\n') if l.strip()]

        story = [
            Paragraph(lines[0] if lines else "Document", title_style),
            Spacer(1, 15)
        ]
        for l in lines[1:50]:
            story.append(Paragraph(l[:200], normal_style))
            story.append(Spacer(1, 6))

        doc.build(story)
        logger.info(f"ReportLab fallback PDF generated at {output_path}")
        return True
    except Exception as rl_err:
        logger.error(f"ReportLab PDF fallback failed: {rl_err}", exc_info=True)
        # Create minimal valid PDF if all else fails so process doesn't abort
        try:
            with open(output_path, 'wb') as f:
                f.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000101 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n168\n%%EOF")
            return True
        except Exception as fallback_err:
            logger.error(f"Minimal PDF fallback also failed: {fallback_err}")
            return False
def simple_markdown_to_html(md_text: str) -> str:
    """Renders Markdown to HTML with graceful built-in fallback if markdown package is missing."""
    try:
        import markdown
        return markdown.markdown(md_text, extensions=['tables', 'fenced_code', 'toc'])
    except Exception:
        pass
    
    import re, html
    lines = md_text.split('\n')
    html_lines = []
    in_code_block = False
    in_table = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('```'):
            if in_code_block:
                html_lines.append('</code></pre>')
                in_code_block = False
            else:
                html_lines.append('<pre><code>')
                in_code_block = True
            continue
            
        if in_code_block:
            html_lines.append(html.escape(line))
            continue
            
        if stripped.startswith('|') and stripped.endswith('|'):
            if '---' in stripped:
                continue
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            if not in_table:
                html_lines.append('<table><thead><tr>')
                for c in cells:
                    html_lines.append(f'<th>{html.escape(c)}</th>')
                html_lines.append('</tr></thead><tbody>')
                in_table = True
            else:
                html_lines.append('<tr>')
                for c in cells:
                    html_lines.append(f'<td>{html.escape(c)}</td>')
                html_lines.append('</tr>')
            continue
        elif in_table:
            html_lines.append('</tbody></table>')
            in_table = False
            
        if stripped.startswith('# '):
            html_lines.append(f'<h1>{html.escape(stripped[2:])}</h1>')
        elif stripped.startswith('## '):
            html_lines.append(f'<h2>{html.escape(stripped[3:])}</h2>')
        elif stripped.startswith('### '):
            html_lines.append(f'<h3>{html.escape(stripped[4:])}</h3>')
        elif stripped.startswith('#### '):
            html_lines.append(f'<h4>{html.escape(stripped[5:])}</h4>')
        elif stripped.startswith('- ') or stripped.startswith('* '):
            html_lines.append(f'<ul><li>{html.escape(stripped[2:])}</li></ul>')
        elif re.match(r'^\d+\.\s', stripped):
            item_text = re.sub(r'^\d+\.\s', '', stripped)
            html_lines.append(f'<ol><li>{html.escape(item_text)}</li></ol>')
        elif stripped:
            formatted = html.escape(stripped)
            formatted = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', formatted)
            formatted = re.sub(r'\*(.+?)\*', r'<em>\1</em>', formatted)
            formatted = re.sub(r'`(.+?)`', r'<code>\1</code>', formatted)
            html_lines.append(f'<p>{formatted}</p>')
        else:
            html_lines.append('<br>')
            
    if in_code_block:
        html_lines.append('</code></pre>')
    if in_table:
        html_lines.append('</tbody></table>')
        
    return '\n'.join(html_lines)


def parse_id_list(val):
    """Helper to parse a single ID, list of IDs, JSON stringified array, or comma-separated string."""
    if not val:
        return []
    if isinstance(val, (list, tuple, set)):
        return [str(x).strip() for x in val if x and str(x).strip() and str(x).strip() not in ['undefined', 'null']]
    if isinstance(val, str):
        val = val.strip()
        if not val or val in ['undefined', 'null']:
            return []
        if val.startswith('['):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if x and str(x).strip() and str(x).strip() not in ['undefined', 'null']]
            except Exception:
                pass
        return [x.strip() for x in val.split(',') if x.strip() and x.strip() not in ['undefined', 'null']]
    return [str(val).strip()]

def fetch_comprehensive_project_context(cursor, project_id: str, reference_document_id=None):
    """
    Retrieves ALL available project knowledge:
    1. Project info (code, name, description)
    2. Primary reference document(s) (if specified, supports multiple)
    3. ALL other project documents in Knowledge Base (TOR/SOW, SRS, SDD, Test Cases, Manuals, etc.)
    4. Structured requirements (if available)
    """
    # 1. Project Info
    cursor.execute("SELECT project_code, project_name, description FROM projects WHERE project_id = %s::uuid", (project_id,))
    p_row = cursor.fetchone()
    project_code = p_row[0] if p_row else "Unknown Project"
    project_name = p_row[1] if p_row and p_row[1] else project_code
    project_desc = p_row[2] if p_row and p_row[2] else ""

    # Parse target reference document IDs (support multiple)
    target_ref_ids = set(parse_id_list(reference_document_id))

    # 2. Fetch ALL Active Documents in this Project
    cursor.execute("""
        SELECT doc_id, original_filename, doc_category, doc_type, full_markdown_content
        FROM documents
        WHERE project_id = %s::uuid AND (status = 'Active' OR status IS NULL)
        ORDER BY created_at ASC
    """, (project_id,))
    doc_rows = cursor.fetchall()

    primary_ref_context_list = []
    all_docs_context_list = []

    for d in doc_rows:
        d_id = str(d[0])
        d_filename = d[1] or "Unnamed Document"
        d_category = d[2] or "General"
        d_doctype = d[3] or "Document"
        d_content = (d[4] or "").strip()

        if target_ref_ids and d_id in target_ref_ids:
            primary_ref_context_list.append(f"""
### Selected Reference Document: {d_filename} [Category: {d_category} | Type: {d_doctype}]
--- Content Start ---
{d_content}
--- Content End ---
""")
        else:
            # Include other project documents, truncating extremely long single files to keep balanced
            snippet = d_content[:15000] if len(d_content) > 15000 else d_content
            if snippet:
                all_docs_context_list.append(f"""
### Project Document: {d_filename} [Category: {d_category} | Type: {d_doctype}]
{snippet}
""")

    primary_ref_context = ""
    if primary_ref_context_list:
        primary_ref_context = f"""
# PRIMARY REFERENCE DOCUMENTS (Selected as Main Sources - High Priority)
The user has specifically designated the following {len(primary_ref_context_list)} document(s) as primary reference sources:
{''.join(primary_ref_context_list)}
"""

    all_docs_section = ""
    if all_docs_context_list:
        all_docs_section = f"""
# Comprehensive Project Knowledge Base ({len(all_docs_context_list)} Documents in Project: {project_code})
The following documents contain additional project domain knowledge, specifications, architecture, and requirements. You MUST analyze and synthesize across ALL of them to generate the most accurate, thorough, and complete document:
{''.join(all_docs_context_list)}
"""

    # 3. Fetch Structured Requirements (if available)
    formatted_reqs = []
    try:
        cursor.execute("""
            SELECT req_code, title, description, steps, expected_results
            FROM structured_requirements
            WHERE project_id = %s::uuid
        """, (project_id,))
        reqs = cursor.fetchall()
        for req in reqs:
            formatted_reqs.append({
                "req_code": req[0],
                "title": req[1],
                "description": req[2],
                "steps": req[3],
                "expected_results": req[4]
            })
    except Exception as req_err:
        logger.info(f"Structured requirements not present or table missing: {req_err}")
        try:
            if hasattr(cursor, 'connection') and cursor.connection:
                cursor.connection.rollback()
        except Exception:
            pass

    structured_reqs_section = ""
    if formatted_reqs:
        structured_reqs_section = f"""
# Structured Requirements & Test Scenarios
{json.dumps(formatted_reqs, ensure_ascii=False, indent=2)}
"""

    return {
        "project_code": project_code,
        "project_name": project_name,
        "project_desc": project_desc,
        "primary_ref_context": primary_ref_context,
        "all_docs_section": all_docs_section,
        "structured_reqs_section": structured_reqs_section,
        "total_docs_count": len(doc_rows)
    }


def create_qa_document(project_id: str, doc_type: str, doc_name: str, skill_id, reference_document_id=None, custom_prompt: str = ""):
    """
    Agent 6: QA Document Creator (Synchronous version returning raw text)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Fetch comprehensive multi-doc project context
        ctx = fetch_comprehensive_project_context(cursor, project_id, reference_document_id)
        project_code = ctx["project_code"]
        project_name = ctx["project_name"]
        primary_ref_context = ctx["primary_ref_context"]
        all_docs_section = ctx["all_docs_section"]
        structured_reqs_section = ctx["structured_reqs_section"]
            
        # 2. Fetch Skill Instructions (supporting multiple skills)
        target_skill_ids = parse_id_list(skill_id)
        if not target_skill_ids:
            cursor.execute("SELECT skill_name, target_doc_type, markdown_instructions FROM agent_skills LIMIT 1")
            skill_rows = cursor.fetchall()
        else:
            cursor.execute("SELECT skill_name, target_doc_type, markdown_instructions FROM agent_skills WHERE skill_id::text = ANY(%s)", (target_skill_ids,))
            skill_rows = cursor.fetchall()

        cursor.close()
        conn.close()

        if not skill_rows:
            skill_name = "Default QA Framework"
            target_doc_type = doc_type
            instructions = "Produce a comprehensive, structured QA document."
        else:
            skill_name = " + ".join([r[0] for r in skill_rows])
            target_doc_type = skill_rows[0][1] or doc_type
            instructions = "\n\n".join([f"### Skill / Framework Guideline: {r[0]} ({r[1] or 'General'})\n{r[2]}" for r in skill_rows])
        
        custom_prompt_section = ""
        if custom_prompt and custom_prompt.strip():
            custom_prompt_section = f"""
# Additional User Prompt & Specific Requirements (High Priority)
The user has provided the following specific guidelines, scenarios, or custom instructions. You MUST strictly follow and incorporate them into the generated document:
{custom_prompt.strip()}
"""

        # Build prompt for synchronous generation
        prompt = f"""
You are an expert Software Architect, Senior Business Analyst, and Technical Writer.
Your task is to generate a comprehensive, professional {doc_type} document for Project '{project_name}' ({project_code}) named '{doc_name}'.
You MUST analyze, cross-reference, and synthesize ALL provided Project Knowledge Base documents (TOR, SRS, SDD, previous tests, specs) to ensure 100% technical accuracy and depth.

# Target Document Information
- Document Name: {doc_name}
- Document Type: {doc_type}
- Project: {project_name} ({project_code})

# Framework & Guidelines (Skill: {skill_name})
Please follow these structure and formatting instructions strictly:
{instructions}

{custom_prompt_section}

{primary_ref_context}

{all_docs_section}

{structured_reqs_section}

# Generation & Content Instructions:
1. Synthesize all documents in the project knowledge base to create a complete, in-depth, production-grade {doc_type}.
2. Use professional Markdown formatting with title, executive overview, detailed sections, numbered requirement tables, user stories/use cases, workflows, data specifications, non-functional requirements, and testability criteria.
3. DO NOT leave placeholder text or brief outlines — write the full, comprehensive content in clear Thai / English as appropriate.
4. Output the complete document directly in clean, structured Markdown.
"""

        # 3. Call Gemini
        doc_content, usage_metadata = call_gemini(prompt)
        
        if usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_6_Doc_Creator", os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), usage_metadata, filename=doc_name)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Agent 6: {log_err}")

        doc_content = (doc_content or "").strip()
        
        if doc_content.startswith("```markdown"):
            doc_content = doc_content[11:]
        if doc_content.startswith("```"):
            doc_content = doc_content[3:]
        if doc_content.endswith("```"):
            doc_content = doc_content[:-3]
            
        return True, doc_content.strip()

    except Exception as e:
        logger.error(f"Error in create_qa_document: {e}", exc_info=True)
        return False, str(e)


def create_qa_document_async(gen_id: str, project_id: str, doc_type: str, doc_name: str, skill_id, reference_document_id=None, custom_prompt: str = ""):
    """
    Async background version of QA Document Creator that generates Excel, PDF, and Markdown.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Fetch comprehensive multi-doc project context
        ctx = fetch_comprehensive_project_context(cursor, project_id, reference_document_id)
        project_code = ctx["project_code"]
        project_name = ctx["project_name"]
        primary_ref_context = ctx["primary_ref_context"]
        all_docs_section = ctx["all_docs_section"]
        structured_reqs_section = ctx["structured_reqs_section"]
            
        # 2. Fetch Skill (supporting multiple skills by ID or Name)
        target_skill_ids = parse_id_list(skill_id)
        skill_rows = []
        if not target_skill_ids:
            try:
                cursor.execute("SELECT skill_name, target_doc_type, markdown_instructions FROM agent_skills LIMIT 1")
                skill_rows = cursor.fetchall()
            except Exception:
                conn.rollback()
        else:
            try:
                cursor.execute(
                    "SELECT skill_name, target_doc_type, markdown_instructions FROM agent_skills "
                    "WHERE skill_id::text = ANY(%s) OR skill_name = ANY(%s)", 
                    (list(target_skill_ids), list(target_skill_ids))
                )
                skill_rows = cursor.fetchall()
            except Exception as skill_err:
                conn.rollback()
                logger.warning(f"Note: error querying skills {target_skill_ids}: {skill_err}")
                try:
                    cursor.execute("SELECT skill_name, target_doc_type, markdown_instructions FROM agent_skills LIMIT 1")
                    skill_rows = cursor.fetchall()
                except Exception:
                    conn.rollback()

        if not skill_rows:
            skill_name = "Default QA Framework"
            target_doc_type = doc_type
            instructions = "Produce a comprehensive, structured QA document."
        else:
            skill_name = " + ".join([r[0] for r in skill_rows if r[0]])
            target_doc_type = skill_rows[0][1] or doc_type
            instructions = "\n\n".join([f"### Skill / Framework Guideline: {r[0]} ({r[1] or 'General'})\n{r[2]}" for r in skill_rows if r[2]])

        custom_prompt_section = ""
        if custom_prompt and custom_prompt.strip():
            custom_prompt_section = f"""
# Additional User Prompt & Specific Requirements (High Priority)
The user has provided the following specific guidelines, scenarios, or custom instructions. You MUST strictly follow and incorporate them into the generated document:
{custom_prompt.strip()}
"""
        
        # 3. Call Gemini
        today_str = datetime.datetime.now().strftime("%d/%m/%Y")
        
        if doc_type in ["Test Case", "TestCase"]:
            prompt = f"""
You are an expert QA Automation Engineer, Business Analyst, and Technical Writer.
Your task is to generate a formal QA Test Case document based on ALL provided Project Knowledge Base documents, Skill Instructions, Reference Documents, and User Custom Prompts.

# Target Document Information
- Document Name: {doc_name}
- Document Type: {doc_type}
- Project: {project_name} ({project_code})

# Framework & Structural Instructions (Skill: {skill_name})
Please follow these instructions strictly to structure and generate the test cases:
{instructions}

{custom_prompt_section}

{primary_ref_context}

{all_docs_section}

{structured_reqs_section}

# Output Format MUST BE JSON
You MUST generate the entire document as a strict JSON object with two keys: "metadata" and "test_cases".
Do NOT include any text outside the JSON.
Format:
{{
  "metadata": {{
    "project_name": "{project_name} ({project_code})",
    "tester_name": "AI Agent",
    "module_function": "Determined from requirements"
  }},
  "test_cases": [
    {{
      "Test Case ID": "TC-001",
      "Test case Objective": "...",
      "Test Description / Procedure": "1. ...\\n2. ...",
      "Test Data": "...",
      "Expected Result": "...",
      "Actual Result": "...",
      "Result (Pass/Fail)": "PASS",
      "Req No.": "...",
      "Update by": "AI Agent"
    }}
  ]
}}
"""
        else:
            prompt = f"""
You are an expert Software Architect, Senior Business Analyst, and Technical Writer.
Your task is to generate a comprehensive, professional {doc_type} document for Project '{project_name}' ({project_code}) named '{doc_name}'.
You MUST analyze, cross-reference, and synthesize ALL provided Project Knowledge Base documents (TOR, SRS, SDD, previous tests, specs) to ensure 100% technical accuracy and depth.

# Target Document Information
- Document Name: {doc_name}
- Document Type: {doc_type}
- Project: {project_name} ({project_code})

# Framework & Guidelines (Skill: {skill_name})
Please follow these structure and formatting instructions strictly:
{instructions}

{custom_prompt_section}

{primary_ref_context}

{all_docs_section}

{structured_reqs_section}

# Generation & Content Instructions:
1. Synthesize all documents in the project knowledge base to create a complete, in-depth, production-grade {doc_type}.
2. Use professional Markdown formatting with title, executive overview, detailed sections, numbered requirement tables, user stories/use cases, workflows, data specifications, non-functional requirements, and testability criteria.
3. DO NOT leave placeholder text or brief outlines — write the full, comprehensive content in clear Thai / English as appropriate.
4. Output the complete document directly in clean, structured Markdown.
"""

        logger.info(f"Generating document async '{doc_name}' ({doc_type})...")
        doc_content, usage_metadata = call_gemini(prompt)
        
        if usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_6_Doc_Creator", os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"), usage_metadata, filename=doc_name)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Agent 6 (async): {log_err}")

        doc_content = (doc_content or "").strip()
        if not doc_content:
            raise ValueError("AI returned empty content.")

        # File paths setup
        upload_dir = os.path.join(os.getcwd(), 'uploads', 'qa_generated')
        os.makedirs(upload_dir, exist_ok=True)
        unique_suffix = uuid.uuid4().hex[:8]
        safe_name = "".join([c if c.isalnum() or c in (' ', '_', '-') else '_' for c in doc_name]).strip().replace(' ', '_')
        
        excel_file_name = f"{safe_name}_{unique_suffix}.xlsx"
        excel_file_path = os.path.join(upload_dir, excel_file_name)
        
        pdf_file_name = f"{safe_name}_{unique_suffix}.pdf"
        pdf_file_path = os.path.join(upload_dir, pdf_file_name)

        doc_markdown = ""
        html_body = ""

        if doc_type in ["Test Case", "TestCase"]:
            # Clean JSON string
            json_text = doc_content
            if "```json" in json_text:
                json_text = json_text.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in json_text:
                json_text = json_text.split("```", 1)[1].split("```", 1)[0]
            json_text = json_text.strip()

            import re
            data = None
            try:
                data = json.loads(json_text)
            except Exception:
                # Regex match fallback
                match = re.search(r'(\{[\s\S]*\})', json_text)
                if match:
                    try:
                        data = json.loads(match.group(1))
                    except Exception:
                        pass

            if not data or not isinstance(data, dict):
                # Fallback structure if JSON parse failed
                data = {
                    "metadata": {"project_name": project_name, "tester_name": "AI Agent", "module_function": doc_name},
                    "test_cases": [
                        {
                            "Test Case ID": "TC-001",
                            "Test case Objective": f"Verify {doc_name} functionality",
                            "Test Description / Procedure": "1. Execute test steps as per requirements.",
                            "Test Data": "Default test parameters",
                            "Expected Result": "System behaves as expected.",
                            "Actual Result": "Working properly",
                            "Result (Pass/Fail)": "PASS",
                            "Req No.": "REQ-01",
                            "Update by": "AI Agent"
                        }
                    ]
                }

            import openpyxl
            from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
            
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Test Case"
            
            # Styles
            header_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
            bold_font = Font(bold=True)
            center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
            left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
            pass_fill = PatternFill(start_color="00FF00", end_color="00FF00", fill_type="solid")
            fail_fill = PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid")
            
            # Row 1: Title
            ws.merge_cells('A1:I1')
            ws['A1'] = "Test Case Specification"
            ws['A1'].font = Font(bold=True, size=14)
            ws['A1'].alignment = center_align
            
            # Row 3-6: Metadata
            meta = data.get("metadata", {})
            tester_val = meta.get("tester_name", "AI Agent")
            module_val = meta.get("module_function", doc_name)
            project_val = meta.get("project_name", project_code)
            
            metadata_map = [
                ("Project Name :", project_val, "Create Date :", today_str),
                ("Project ID:", project_code, "Start Test Date :", today_str),
                ("Tester Name :", tester_val, "Finish Test Date :", today_str),
                ("Project Release / Version :", "-", "Module / Function:", module_val)
            ]
            
            row_idx = 3
            for r_data in metadata_map:
                ws.cell(row=row_idx, column=2).value = r_data[0]
                ws.cell(row=row_idx, column=2).font = bold_font
                ws.cell(row=row_idx, column=2).alignment = Alignment(horizontal="right")
                
                ws.merge_cells(start_row=row_idx, start_column=3, end_row=row_idx, end_column=4)
                ws.cell(row=row_idx, column=3).value = r_data[1]
                
                ws.cell(row=row_idx, column=6).value = r_data[2]
                ws.cell(row=row_idx, column=6).font = bold_font
                ws.cell(row=row_idx, column=6).alignment = Alignment(horizontal="right")
                
                ws.merge_cells(start_row=row_idx, start_column=7, end_row=row_idx, end_column=8)
                ws.cell(row=row_idx, column=7).value = r_data[3]
                
                for col in range(1, 10):
                    ws.cell(row=row_idx, column=col).fill = header_fill
                row_idx += 1
                
            # Row 7: Functional Requirements
            ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=4)
            ws.cell(row=row_idx, column=1).value = "FUNCTIONAL REQUIREMENTS (Requirements No.) :"
            ws.cell(row=row_idx, column=1).font = bold_font
            ws.cell(row=row_idx, column=1).alignment = center_align
            
            ws.merge_cells(start_row=row_idx, start_column=5, end_row=row_idx, end_column=9)
            ws.cell(row=row_idx, column=5).value = "-"
            for col in range(1, 10):
                ws.cell(row=row_idx, column=col).fill = header_fill
            row_idx += 1
            
            # Row 8: Table Headers
            headers = ["Test Case ID", "Test case Objective", "Test Description / Procedure", "Test Data", 
                       "Expected Result", "Actual Result", "Result (Pass/Fail)", "Req No.", "Update by"]
            row_idx += 1
            for col_idx, h in enumerate(headers, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=h)
                cell.font = bold_font
                cell.fill = header_fill
                cell.alignment = center_align
                cell.border = thin_border
                
            widths = [15, 30, 40, 20, 30, 25, 15, 10, 20]
            for i, w in enumerate(widths, 1):
                ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
                
            # Data Rows
            test_cases = data.get("test_cases", [])
            row_idx += 1
            for tc in test_cases:
                for col_idx, h in enumerate(headers, 1):
                    val = tc.get(h, "")
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.border = thin_border
                    cell.alignment = center_align if col_idx in [1, 7, 8, 9] else left_align
                    
                    if h == "Result (Pass/Fail)":
                        if str(val).upper() == "PASS":
                            cell.fill = pass_fill
                        elif str(val).upper() == "FAIL":
                            cell.fill = fail_fill
                row_idx += 1
                
            wb.save(excel_file_path)

            # Construct Markdown Representation
            md_lines = [
                f"# {doc_name}",
                f"**Document Type:** {doc_type}  ",
                f"**Project Code:** {project_code}  ",
                f"**Module / Function:** {module_val}  ",
                f"**Tester:** {tester_val}  ",
                f"**Date:** {today_str}  ",
                "",
                "## Test Cases Summary",
                "| Test Case ID | Objective | Expected Result | Result | Req No. |",
                "| :--- | :--- | :--- | :--- | :--- |"
            ]
            
            for tc in test_cases:
                tc_id = tc.get("Test Case ID", "")
                obj = str(tc.get("Test case Objective", "")).replace("\n", " ").replace("|", "\\|")
                exp = str(tc.get("Expected Result", "")).replace("\n", " ").replace("|", "\\|")
                res = tc.get("Result (Pass/Fail)", "")
                req_no = tc.get("Req No.", "")
                md_lines.append(f"| {tc_id} | {obj} | {exp} | **{res}** | {req_no} |")
                
            md_lines.append("")
            md_lines.append("## Detailed Test Specifications")
            for tc in test_cases:
                md_lines.append(f"### [{tc.get('Test Case ID', '')}] {tc.get('Test case Objective', '')}")
                md_lines.append(f"- **Requirement No.:** {tc.get('Req No.', '-')}")
                md_lines.append(f"- **Test Data:** {tc.get('Test Data', '-')}")
                md_lines.append(f"- **Procedure:**\n{tc.get('Test Description / Procedure', '-')}")
                md_lines.append(f"- **Expected Result:** {tc.get('Expected Result', '-')}")
                md_lines.append(f"- **Actual Result:** {tc.get('Actual Result', '-')}")
                md_lines.append(f"- **Status / Result:** `{tc.get('Result (Pass/Fail)', '-')}`")
                md_lines.append(f"- **Updated By:** {tc.get('Update by', '-')}")
                md_lines.append("")

            doc_markdown = "\n".join(md_lines)

            # Construct HTML for PDF
            rows_html = ""
            for tc in test_cases:
                res_val = str(tc.get("Result (Pass/Fail)", "")).upper()
                badge_class = "badge pass" if res_val == "PASS" else ("badge fail" if res_val == "FAIL" else "badge")
                proc_html = str(tc.get("Test Description / Procedure", "")).replace("\n", "<br>")
                rows_html += f"""
                <tr>
                    <td style="font-weight: 600; text-align: center;">{tc.get("Test Case ID", "")}</td>
                    <td>{tc.get("Test case Objective", "")}</td>
                    <td>{proc_html}</td>
                    <td>{tc.get("Test Data", "")}</td>
                    <td>{tc.get("Expected Result", "")}</td>
                    <td style="text-align: center;"><span class="{badge_class}">{res_val}</span></td>
                    <td style="text-align: center;">{tc.get("Req No.", "")}</td>
                </tr>
                """

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <meta charset="utf-8">
            <title>{doc_name}</title>
            <style>
                @page {{ size: A4 landscape; margin: 12mm; }}
                body {{ font-family: 'Segoe UI', Tahoma, sans-serif; font-size: 11px; color: #1e293b; margin: 0; padding: 0; line-height: 1.4; }}
                .header-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; margin-bottom: 16px; }}
                .title-row {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; margin-bottom: 10px; }}
                .doc-title {{ font-size: 18px; font-weight: bold; color: #1e3a8a; margin: 0; }}
                .type-badge {{ background: #dbeafe; color: #1d4ed8; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 11px; }}
                .meta-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; font-size: 11px; }}
                .meta-item {{ display: flex; flex-direction: column; }}
                .meta-label {{ font-weight: 600; color: #64748b; font-size: 10px; text-transform: uppercase; }}
                .meta-val {{ color: #0f172a; font-weight: 500; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th, td {{ border: 1px solid #cbd5e1; padding: 6px 8px; vertical-align: top; font-size: 10.5px; }}
                th {{ background-color: #f1f5f9; color: #334155; font-weight: 600; text-align: left; }}
                tr:nth-child(even) {{ background-color: #f8fafc; }}
                .badge {{ display: inline-block; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 9.5px; }}
                .pass {{ background: #dcfce7; color: #15803d; }}
                .fail {{ background: #fee2e2; color: #b91c1c; }}
            </style>
            </head>
            <body>
                <div class="header-card">
                    <div class="title-row">
                        <div class="doc-title">{doc_name}</div>
                        <div class="type-badge">{doc_type}</div>
                    </div>
                    <div class="meta-grid">
                        <div class="meta-item"><span class="meta-label">Project</span><span class="meta-val">{project_val} ({project_code})</span></div>
                        <div class="meta-item"><span class="meta-label">Module / Function</span><span class="meta-val">{module_val}</span></div>
                        <div class="meta-item"><span class="meta-label">Tester</span><span class="meta-val">{tester_val}</span></div>
                        <div class="meta-item"><span class="meta-label">Date</span><span class="meta-val">{today_str}</span></div>
                    </div>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 8%; text-align: center;">Test ID</th>
                            <th style="width: 22%;">Objective</th>
                            <th style="width: 28%;">Description / Procedure</th>
                            <th style="width: 14%;">Test Data</th>
                            <th style="width: 18%;">Expected Result</th>
                            <th style="width: 5%; text-align: center;">Result</th>
                            <th style="width: 5%; text-align: center;">Req No.</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </body>
            </html>
            """

        else:
            # Generic Document Types (SRS, SDD, TOR, UAT, User Manual, Admin Manual, etc.)
            clean_md = doc_content
            if clean_md.startswith("```markdown"):
                clean_md = clean_md[11:]
            elif clean_md.startswith("```"):
                clean_md = clean_md[3:]
            if clean_md.endswith("```"):
                clean_md = clean_md[:-3]
            doc_markdown = clean_md.strip()

            # Generate Excel Document Structure
            import openpyxl
            from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

            wb = openpyxl.Workbook()
            ws_overview = wb.active
            ws_overview.title = "Document Overview"

            header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            sub_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
            white_bold = Font(bold=True, color="FFFFFF", size=13)
            bold_font = Font(bold=True, size=11)
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

            ws_overview.merge_cells('A1:D1')
            ws_overview['A1'] = f"{doc_name} ({doc_type})"
            ws_overview['A1'].fill = header_fill
            ws_overview['A1'].font = white_bold
            ws_overview['A1'].alignment = Alignment(horizontal="center", vertical="center")
            ws_overview.row_dimensions[1].height = 30

            meta_rows = [
                ("Project Code:", project_code, "Date:", today_str),
                ("Project Name:", project_name, "Document Type:", doc_type),
                ("Skill / Framework:", skill_name, "Generated By:", "AI Agent 6")
            ]
            for r_i, (k1, v1, k2, v2) in enumerate(meta_rows, 3):
                ws_overview.cell(row=r_i, column=1, value=k1).font = bold_font
                ws_overview.cell(row=r_i, column=2, value=v1)
                ws_overview.cell(row=r_i, column=3, value=k2).font = bold_font
                ws_overview.cell(row=r_i, column=4, value=v2)
                for c in range(1, 5):
                    ws_overview.cell(row=r_i, column=c).border = thin_border

            # Parse Headings & Sections into Excel
            ws_content = wb.create_sheet(title="Document Sections")
            ws_content.cell(row=1, column=1, value="Section / Heading").font = bold_font
            ws_content.cell(row=1, column=1).fill = sub_fill
            ws_content.cell(row=1, column=2, value="Content Details").font = bold_font
            ws_content.cell(row=1, column=2).fill = sub_fill

            c_row = 2
            current_section = "Overview"
            current_body = []
            for line in doc_markdown.split("\n"):
                if line.startswith("#"):
                    if current_body:
                        ws_content.cell(row=c_row, column=1, value=current_section).border = thin_border
                        ws_content.cell(row=c_row, column=2, value="\n".join(current_body)).border = thin_border
                        c_row += 1
                        current_body = []
                    current_section = line.lstrip("#").strip()
                else:
                    if line.strip():
                        current_body.append(line.strip())

            if current_body:
                ws_content.cell(row=c_row, column=1, value=current_section).border = thin_border
                ws_content.cell(row=c_row, column=2, value="\n".join(current_body)).border = thin_border

            ws_overview.column_dimensions['A'].width = 20
            ws_overview.column_dimensions['B'].width = 35
            ws_overview.column_dimensions['C'].width = 20
            ws_overview.column_dimensions['D'].width = 35
            ws_content.column_dimensions['A'].width = 35
            ws_content.column_dimensions['B'].width = 80

            wb.save(excel_file_path)

            # Generate HTML for PDF
            rendered_markdown = simple_markdown_to_html(doc_markdown)

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <meta charset="utf-8">
            <title>{doc_name}</title>
            <style>
                @page {{ size: A4; margin: 18mm; }}
                body {{ font-family: 'Segoe UI', Tahoma, sans-serif; font-size: 11.5px; color: #1e293b; margin: 0; padding: 0; line-height: 1.6; }}
                .header-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 20px; margin-bottom: 20px; }}
                .title-row {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-bottom: 12px; }}
                .doc-title {{ font-size: 20px; font-weight: bold; color: #1e3a8a; margin: 0; }}
                .type-badge {{ background: #dbeafe; color: #1d4ed8; padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 12px; }}
                h1, h2, h3, h4 {{ color: #1e3a8a; margin-top: 18px; margin-bottom: 8px; }}
                h1 {{ font-size: 16px; border-bottom: 1px solid #cbd5e1; padding-bottom: 4px; }}
                h2 {{ font-size: 14px; }}
                h3 {{ font-size: 12.5px; }}
                p {{ margin: 0 0 8px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 12px 0; }}
                th, td {{ border: 1px solid #cbd5e1; padding: 6px 10px; vertical-align: top; font-size: 11px; }}
                th {{ background-color: #f1f5f9; color: #334155; font-weight: 600; text-align: left; }}
                tr:nth-child(even) {{ background-color: #f8fafc; }}
                code {{ background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-family: monospace; font-size: 11px; }}
                pre {{ background: #0f172a; color: #f8fafc; padding: 12px; border-radius: 6px; overflow-x: auto; }}
                pre code {{ background: none; color: inherit; }}
                ul, ol {{ margin: 4px 0 10px 20px; padding: 0; }}
                li {{ margin-bottom: 4px; }}
                blockquote {{ border-left: 4px solid #3b82f6; margin: 8px 0; padding: 6px 12px; background: #eff6ff; color: #1e40af; }}
            </style>
            </head>
            <body>
                <div class="header-card">
                    <div class="title-row">
                        <div class="doc-title">{doc_name}</div>
                        <div class="type-badge">{doc_type}</div>
                    </div>
                    <div><b>Project:</b> {project_name} ({project_code}) | <b>Framework:</b> {skill_name} | <b>Date:</b> {today_str}</div>
                </div>
                <div class="doc-body">
                    {rendered_markdown}
                </div>
            </body>
            </html>
            """

        # Render PDF
        render_html_to_pdf(html_body, pdf_file_path)

        # 6. Update DB with file_url (Excel), pdf_url (PDF), markdown_content
        cursor.execute("SELECT status FROM qa_generated_documents WHERE id = %s::uuid", (gen_id,))
        status_row = cursor.fetchone()
        if status_row and status_row[0] == 'Cancelled':
            logger.info(f"Document generation {gen_id} was cancelled by user. Discarding output.")
            return

        cursor.execute("""
            UPDATE qa_generated_documents 
            SET status = 'Completed', 
                file_url = %s, 
                pdf_url = %s, 
                markdown_content = %s, 
                is_saved_to_project = FALSE 
            WHERE id = %s::uuid AND status != 'Cancelled'
        """, (excel_file_path, pdf_file_path, doc_markdown, gen_id))
        conn.commit()
        logger.info(f"Successfully generated QA document (Excel: {excel_file_path}, PDF: {pdf_file_path})")

    except Exception as e:
        logger.error(f"Error in create_qa_document_async: {e}", exc_info=True)
        if conn and cursor:
            try:
                conn.rollback()
                cursor.execute("UPDATE qa_generated_documents SET status = 'Failed' WHERE id = %s::uuid AND status != 'Cancelled'", (gen_id,))
                conn.commit()
            except Exception as update_err:
                logger.error(f"Failed to update failed status in DB: {update_err}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    print("Script loaded successfully.")
