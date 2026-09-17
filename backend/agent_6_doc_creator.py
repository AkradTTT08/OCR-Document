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

import google.generativeai as genai
from db_ingestion import get_db_connection

logger = logging.getLogger(__name__)

def render_html_to_pdf(html_content: str, output_path: str):
    """
    Renders HTML content to a PDF file using Playwright (Chromium headless)
    with a fallback to ReportLab if Playwright encounters any issue.
    """
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
            logger.info(f"Playwright PDF generated successfully at {output_path}")
            return True
    except Exception as pw_err:
        logger.warning(f"Playwright PDF generation failed ({pw_err}), attempting ReportLab fallback...")
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.lib import colors

            font_registered = False
            for font_path in ['C:/Windows/Fonts/tahoma.ttf', 'C:/Windows/Fonts/arial.ttf']:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('ThaiFont', font_path))
                        font_registered = True
                        break
                    except Exception:
                        pass

            font_name = 'ThaiFont' if font_registered else 'Helvetica'

            doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
            styles = getSampleStyleSheet()
            normal_style = ParagraphStyle('NormalThai', fontName=font_name, fontSize=10, leading=14)
            title_style = ParagraphStyle('TitleThai', fontName=font_name, fontSize=16, leading=20, alignment=1)

            story = [
                Paragraph("QA Document", title_style),
                Spacer(1, 15),
                Paragraph("Document generated from QA Agent.", normal_style),
                Spacer(1, 15)
            ]
            doc.build(story)
            logger.info(f"ReportLab fallback PDF generated at {output_path}")
            return True
        except Exception as rl_err:
            logger.error(f"ReportLab PDF fallback failed: {rl_err}", exc_info=True)
            return False


def create_qa_document(project_id: str, doc_type: str, doc_name: str, skill_id: str, reference_document_id=None, custom_prompt: str = ""):
    """
    Agent 6: QA Document Creator (Synchronous version returning raw text)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Fetch Project Info
        cursor.execute("SELECT project_code FROM projects WHERE project_id = %s::uuid", (project_id,))
        project_res = cursor.fetchone()
        project_code = project_res[0] if project_res else "Unknown Project"

        # 2. Fetch Knowledge (Phase 1 Requirements)
        cursor.execute("""
            SELECT req_code, title, description, steps, expected_results
            FROM structured_requirements
            WHERE project_id = %s::uuid
        """, (project_id,))
        reqs = cursor.fetchall()
        
        formatted_reqs = []
        for req in reqs:
            formatted_reqs.append({
                "req_code": req[0],
                "title": req[1],
                "description": req[2],
                "steps": req[3],
                "expected_results": req[4]
            })

        if not formatted_reqs:
            logger.warning(f"No structured requirements found for project {project_id}.")
            
        # 3. Fetch Skill Instructions
        cursor.execute("SELECT skill_name, target_doc_type, markdown_instructions FROM agent_skills WHERE skill_id::text = %s::text", (str(skill_id),))
        skill_res = cursor.fetchone()
        
        # 3.5 Fetch Reference Document (if any)
        reference_context = ""
        if reference_document_id:
            cursor.execute("SELECT original_filename, full_markdown_content FROM documents WHERE doc_id = %s::uuid", (reference_document_id,))
            doc_res = cursor.fetchone()
            if doc_res:
                ref_filename, ref_content = doc_res
                reference_context = f"""
# Reference Document ({ref_filename})
You MUST use this document as the primary reference for your analysis and generation. Do not generate content outside the scope defined in this document.
{ref_content}
"""
            else:
                logger.warning(f"Reference document {reference_document_id} not found.")

        cursor.close()
        conn.close()

        if not skill_res:
            return False, "Selected skill not found in database."
            
        skill_name, target_doc_type, instructions = skill_res
        
        custom_prompt_section = ""
        if custom_prompt and custom_prompt.strip():
            custom_prompt_section = f"""
# Additional User Prompt & Specific Requirements (High Priority)
The user has provided the following specific guidelines, scenarios, or custom instructions. You MUST strictly follow and incorporate them into the generated document:
{custom_prompt.strip()}
"""

        # 4. Call Gemini
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return False, "GEMINI_API_KEY or GOOGLE_API_KEY is not configured in .env."
            
        genai.configure(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name)
        
        prompt = f"""
You are an expert QA Automation Engineer, Business Analyst, and Technical Writer.
Your task is to generate a formal QA Document based on the provided System Knowledge, Skill Instructions, Reference Documents, and User Custom Prompts.

# Target Document Information
- Document Name: {doc_name}
- Document Type: {doc_type}
- Project Code: {project_code}

# Framework & Instructions (Skill: {skill_name})
Please follow these instructions strictly to structure and generate the document:
{instructions}

{custom_prompt_section}

{reference_context}

# System Knowledge (Phase 1 Structured Requirements)
{json.dumps(formatted_reqs, ensure_ascii=False, indent=2)}

# Output Format
Generate the complete document in standard Markdown format. Use professional formatting, tables if necessary, and clear headings.
Do NOT wrap the entire response in ```markdown ... ``` blocks unless necessary, just output the raw markdown text directly.
"""
        logger.info(f"Generating document '{doc_name}' ({doc_type}) using skill '{skill_name}'...")
        resp = model.generate_content(prompt)
        doc_content = resp.text.strip()
        
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


def create_qa_document_async(gen_id: str, project_id: str, doc_type: str, doc_name: str, skill_id: str, reference_document_id=None, custom_prompt: str = ""):
    """
    Async background version of QA Document Creator that generates Excel, PDF, and Markdown.
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Fetch Project Info
        cursor.execute("SELECT project_code FROM projects WHERE project_id = %s::uuid", (project_id,))
        project_res = cursor.fetchone()
        project_code = project_res[0] if project_res else "Unknown Project"

        # 2. Fetch Knowledge
        cursor.execute("""
            SELECT req_code, title, description, steps, expected_results
            FROM structured_requirements
            WHERE project_id = %s::uuid
        """, (project_id,))
        reqs = cursor.fetchall()
        
        formatted_reqs = []
        for req in reqs:
            formatted_reqs.append({
                "req_code": req[0],
                "title": req[1],
                "description": req[2],
                "steps": req[3],
                "expected_results": req[4]
            })
            
        # 3. Fetch Skill
        cursor.execute("SELECT skill_name, target_doc_type, markdown_instructions FROM agent_skills WHERE skill_id::text = %s::text", (str(skill_id),))
        skill_res = cursor.fetchone()
        if not skill_res:
            raise ValueError(f"Skill '{skill_id}' not found.")
        skill_name, target_doc_type, instructions = skill_res
        
        # 3.5 Fetch Reference
        reference_context = ""
        if reference_document_id:
            cursor.execute("SELECT original_filename, full_markdown_content FROM documents WHERE doc_id = %s::uuid", (reference_document_id,))
            doc_res = cursor.fetchone()
            if doc_res:
                ref_filename, ref_content = doc_res
                reference_context = f"""
# Reference Document ({ref_filename})
You MUST use this document as the primary reference for your analysis and generation. Do not generate content outside the scope defined in this document.
{ref_content}
"""

        custom_prompt_section = ""
        if custom_prompt and custom_prompt.strip():
            custom_prompt_section = f"""
# Additional User Prompt & Specific Requirements (High Priority)
The user has provided the following specific guidelines, scenarios, or custom instructions. You MUST strictly follow and incorporate them into the generated document:
{custom_prompt.strip()}
"""
        
        # 4. Call Gemini
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is not configured in .env.")
            
        genai.configure(api_key=api_key)
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        model = genai.GenerativeModel(model_name)
        
        today_str = datetime.datetime.now().strftime("%d/%m/%Y")
        
        if doc_type == "Test Case":
            prompt = f"""
You are an expert QA Automation Engineer, Business Analyst, and Technical Writer.
Your task is to generate a formal QA Document based on the provided System Knowledge, Skill Instructions, Reference Documents, and User Custom Prompts.

# Target Document Information
- Document Name: {doc_name}
- Document Type: {doc_type}
- Project Code: {project_code}

# Framework & Instructions (Skill: {skill_name})
Please follow these instructions strictly to structure and generate the document:
{instructions}

{custom_prompt_section}

{reference_context}

# System Knowledge (Phase 1 Structured Requirements)
{json.dumps(formatted_reqs, ensure_ascii=False, indent=2)}

# Output Format MUST BE JSON
You MUST generate the entire document as a strict JSON object with two keys: "metadata" and "test_cases".
Do NOT include any text outside the JSON.
Format:
{{
  "metadata": {{
    "project_name": "{project_code} (Admin)",
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
You are an expert QA Automation Engineer, Business Analyst, and Technical Writer.
Your task is to generate a formal QA Document based on the provided System Knowledge, Skill Instructions, Reference Documents, and User Custom Prompts.

# Target Document Information
- Document Name: {doc_name}
- Document Type: {doc_type}
- Project Code: {project_code}

# Framework & Instructions (Skill: {skill_name})
Please follow these instructions strictly to structure and generate the document:
{instructions}

{custom_prompt_section}

{reference_context}

# System Knowledge (Phase 1 Structured Requirements)
{json.dumps(formatted_reqs, ensure_ascii=False, indent=2)}

# Output Format MUST BE JSON ARRAY
You MUST generate the entire document as a strict JSON Array of Objects.
Do NOT include any text outside the JSON array.
Each object in the array represents a single row or section.
The keys of the objects will become the headers. Make sure all objects use consistent keys.
"""

        logger.info(f"Generating document async '{doc_name}' ({doc_type})...")
        resp = model.generate_content(prompt)
        doc_content = resp.text.strip()
        
        # Clean JSON
        if doc_content.startswith("```json"): doc_content = doc_content[7:]
        elif doc_content.startswith("```"): doc_content = doc_content[3:]
        if doc_content.endswith("```"): doc_content = doc_content[:-3]
        doc_content = doc_content.strip()
        
        try:
            data = json.loads(doc_content)
        except json.JSONDecodeError:
            raise ValueError("AI did not return a valid JSON format.")
            
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

        if doc_type == "Test Case":
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
            
            ws.merge_cells(start_row=row_idx, start_column=6, end_row=row_idx, end_column=8)
            ws.cell(row=row_idx, column=6).value = "Site test UAT :"
            ws.cell(row=row_idx, column=6).font = bold_font
            ws.cell(row=row_idx, column=6).alignment = Alignment(horizontal="right")
            
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
            # Generic Document Types (SRS, UAT, Other)
            import pandas as pd
            if not isinstance(data, list):
                data_list = [data]
            else:
                data_list = data
                
            df = pd.DataFrame(data_list)
            df.to_excel(excel_file_path, index=False)

            # Generate Markdown
            md_lines = [
                f"# {doc_name}",
                f"**Document Type:** {doc_type}  ",
                f"**Project Code:** {project_code}  ",
                f"**Date:** {today_str}  ",
                "",
                "## Content",
                ""
            ]
            if len(data_list) > 0 and isinstance(data_list[0], dict):
                headers = list(data_list[0].keys())
                header_row = "| " + " | ".join(headers) + " |"
                sep_row = "| " + " | ".join([":---" for _ in headers]) + " |"
                md_lines.append(header_row)
                md_lines.append(sep_row)
                for item in data_list:
                    row_str = "| " + " | ".join([str(item.get(h, '')).replace('\n', ' ').replace('|', '\\|') for h in headers]) + " |"
                    md_lines.append(row_str)
            doc_markdown = "\n".join(md_lines)

            # Generate HTML
            headers = list(data_list[0].keys()) if data_list and isinstance(data_list[0], dict) else []
            th_html = "".join([f"<th>{h}</th>" for h in headers])
            tr_html = ""
            for item in data_list:
                tds = "".join([f"<td>{str(item.get(h, '')).replace(chr(10), '<br>')}</td>" for h in headers])
                tr_html += f"<tr>{tds}</tr>"

            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <meta charset="utf-8">
            <title>{doc_name}</title>
            <style>
                @page {{ size: A4; margin: 15mm; }}
                body {{ font-family: 'Segoe UI', Tahoma, sans-serif; font-size: 12px; color: #1e293b; margin: 0; padding: 0; line-height: 1.5; }}
                .header-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 20px; margin-bottom: 20px; }}
                .title-row {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #3b82f6; padding-bottom: 10px; margin-bottom: 12px; }}
                .doc-title {{ font-size: 20px; font-weight: bold; color: #1e3a8a; margin: 0; }}
                .type-badge {{ background: #dbeafe; color: #1d4ed8; padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 12px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ border: 1px solid #cbd5e1; padding: 8px 10px; vertical-align: top; font-size: 11.5px; }}
                th {{ background-color: #f1f5f9; color: #334155; font-weight: 600; text-align: left; }}
                tr:nth-child(even) {{ background-color: #f8fafc; }}
            </style>
            </head>
            <body>
                <div class="header-card">
                    <div class="title-row">
                        <div class="doc-title">{doc_name}</div>
                        <div class="type-badge">{doc_type}</div>
                    </div>
                    <div><b>Project:</b> {project_code} | <b>Date:</b> {today_str}</div>
                </div>
                <table>
                    <thead><tr>{th_html}</tr></thead>
                    <tbody>{tr_html}</tbody>
                </table>
            </body>
            </html>
            """

        # Render PDF
        render_html_to_pdf(html_body, pdf_file_path)

        # 6. Update DB with file_url (Excel), pdf_url (PDF), markdown_content
        cursor.execute("""
            UPDATE qa_generated_documents 
            SET status = 'Completed', 
                file_url = %s, 
                pdf_url = %s, 
                markdown_content = %s, 
                is_saved_to_project = FALSE 
            WHERE id = %s::uuid
        """, (excel_file_path, pdf_file_path, doc_markdown, gen_id))
        conn.commit()
        logger.info(f"Successfully generated QA document (Excel: {excel_file_path}, PDF: {pdf_file_path})")

    except Exception as e:
        logger.error(f"Error in create_qa_document_async: {e}", exc_info=True)
        if conn and cursor:
            try:
                cursor.execute("UPDATE qa_generated_documents SET status = 'Failed' WHERE id = %s::uuid", (gen_id,))
                conn.commit()
            except:
                pass
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    print("Script loaded successfully.")
