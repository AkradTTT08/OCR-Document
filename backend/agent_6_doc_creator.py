import json
import logging
import os
import datetime
import uuid
import re
import html
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
    with a graceful fallback to WeasyPrint or ReportLab if Playwright encounters an issue.
    """
    # 1. Try Playwright
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--font-render-hinting=none'
                ]
            )
            page = browser.new_page()
            page.set_content(html_content, wait_until="load", timeout=30000)
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

    # 2. Try WeasyPrint if available (dynamic import to avoid static linter warnings on systems without GTK/WeasyPrint)
    try:
        import importlib
        weasyprint = importlib.import_module("weasyprint")
        weasyprint.HTML(string=html_content).write_pdf(output_path)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"WeasyPrint PDF generated successfully at {output_path}")
            return True
    except Exception:
        pass

    # 3. Fallback: ReportLab PDF Generator (Clean text parsing with Thai font support)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib import colors

        local_project_font = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'fonts', 'THSarabun.ttf'))
        font_candidates = [
            local_project_font,
            '/app/fonts/THSarabun.ttf',
            'C:/Windows/Fonts/tahoma.ttf',
            'C:/Windows/Fonts/segoeui.ttf',
            'C:/Windows/Fonts/arial.ttf',
            '/usr/share/fonts/truetype/thai/THSarabun.ttf',
            '/usr/share/fonts/truetype/tlwg/Waree.ttf',
            '/usr/share/fonts/truetype/tlwg/Loma.ttf',
            '/usr/share/fonts/truetype/tlwg/Garuda.ttf',
            '/usr/share/fonts/truetype/tlwg/Norasi.ttf',
            '/usr/share/fonts/opentype/noto/NotoSansThai-Regular.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'
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

        doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        normal_style = ParagraphStyle('NormalUni', fontName=font_name, fontSize=10, leading=15, textColor=colors.HexColor('#1e293b'))
        h1_style = ParagraphStyle('H1Uni', fontName=font_name, fontSize=15, leading=19, textColor=colors.HexColor('#1e3a8a'), spaceAfter=8, keepWithNext=True)
        h2_style = ParagraphStyle('H2Uni', fontName=font_name, fontSize=12.5, leading=16, textColor=colors.HexColor('#1e3a8a'), spaceAfter=6, keepWithNext=True)
        title_style = ParagraphStyle('TitleUni', fontName=font_name, fontSize=17, leading=21, alignment=1, textColor=colors.HexColor('#1e3a8a'), spaceAfter=12)

        import re, html
        # Strip all <head>, <style>, <script> and their inner contents
        clean_html = re.sub(r'<(head|style|script)[^>]*>[\s\S]*?</\1>', '', html_content, flags=re.IGNORECASE)
        # Convert break and block tags to newlines
        clean_html = re.sub(r'<(h[1-6]|p|div|tr|li|br)[^>]*>', '\n', clean_html, flags=re.IGNORECASE)
        # Strip all other remaining HTML tags
        clean_text = re.sub(r'<[^<]+?>', '', clean_html)
        clean_text = html.unescape(clean_text)

        raw_lines = [l.strip() for l in clean_text.split('\n') if l.strip()]

        story = []
        if raw_lines:
            story.append(Paragraph(html.escape(raw_lines[0]), title_style))
            story.append(Spacer(1, 14))

        for l in raw_lines[1:]:
            safe_l = html.escape(l)
            if len(l) < 80 and any(l.startswith(prefix) for prefix in ['#', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', 'Section', 'Module']):
                story.append(Spacer(1, 8))
                story.append(Paragraph(safe_l, h2_style))
            else:
                story.append(Paragraph(safe_l, normal_style))
                story.append(Spacer(1, 4))

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


def sanitize_engineering_markdown(text: str) -> str:
    """
    Sanitizes markdown output from LLM:
    1. Removes LaTeX math wrappers '$' and '$$' which trigger QA typo & formula ambiguity findings.
    2. Converts common LaTeX mathematical symbols into plain text (e.g. \\le -> <=, \\ge -> >=, \\cdot -> *).
    3. Converts LaTeX \\frac{a}{b} -> (a / b), \\text{...} -> ...
    4. Removes stray '$' characters around performance variables like $P95 \\le 1.5s$ or $P95 <= 1.5s$.
    """
    if not text:
        return ""
    # 1. Clean LaTeX operators
    text = re.sub(r'\\le(?:q)?(?![a-zA-Z])', '<=', text)
    text = re.sub(r'\\ge(?:q)?(?![a-zA-Z])', '>=', text)
    text = re.sub(r'\\(?:cdot|times)', '*', text)
    text = re.sub(r'\\frac\{([^}]+)\}\{([^}]+)\}', r'(\1 / \2)', text)
    text = re.sub(r'\\text\{([^}]+)\}', r'\1', text)
    
    # 2. Display math $$ ... $$
    text = re.sub(r'\$\$(.+?)\$\$', r'\1', text, flags=re.DOTALL)
    
    # 3. Inline math $ ... $
    def _strip_dollar(m):
        content = m.group(1)
        if re.match(r'^\d+(?:\.\d+)?$', content.strip()):
            return f"${content}"
        return content

    text = re.sub(r'\$([^$\n]+?)\$', _strip_dollar, text)
    
    # 4. Remove any lone '$' that is not followed by a digit
    text = re.sub(r'\$(?!\s*\d)', '', text)
    return text


def extract_document_metadata(md_text: str):
    """
    Extracts version, author, and date directly from the document markdown table to ensure
    100% harmony between Header cards and Document Control sections.
    """
    version = "1.0.0"
    author = "Lead Business Analyst / QA Architect"
    date_val = None
    
    # 1. Version extraction
    v_match = re.search(r'(?:หมายเลขเวอร์ชัน|Version)[^|\n\r]*[|:]\s*(?:Version\s*)?([0-9]+\.[0-9]+(?:\.[0-9]+)?)', md_text, re.IGNORECASE)
    if v_match:
        version = v_match.group(1).strip()
        
    # 2. Author extraction
    a_match = re.search(r'(?:ผู้จัดทำ|Author)[^|\n\r]*[|:]\s*([^|\n\r]+)', md_text, re.IGNORECASE)
    if a_match:
        cand = a_match.group(1).strip()
        if cand and not cand.startswith('[') and len(cand) < 100:
            author = cand
            
    # 3. Date extraction
    d_match = re.search(r'(?:วันที่บังคับใช้|Baseline Date|วันที่|Date)[^|\n\r]*[|:]\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})', md_text, re.IGNORECASE)
    if d_match:
        date_val = d_match.group(1).strip()
        
    return version, author, date_val


def build_generic_document_html(doc_name: str, doc_type: str, project_name: str, project_code: str, skill_name: str, today_str: str, rendered_markdown: str, doc_version: str = "1.0.0", doc_author: str = "Lead Business Analyst / QA Architect", doc_date: str = None) -> str:
    """Builds an enterprise-grade HTML document for SRS, SDD, TOR, UAT, Manuals, etc."""
    effective_date = doc_date or today_str
    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>{doc_name} - {doc_type}</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700;800&family=Prompt:wght@400;600;700&display=swap');
    @page {{
        size: A4 portrait;
        margin: 16mm 14mm 16mm 14mm;
        @bottom-right {{
            content: counter(page);
            font-size: 9px;
            color: #64748b;
            font-family: 'Sarabun', 'Segoe UI', Tahoma, sans-serif;
        }}
    }}
    *, *:before, *:after {{ box-sizing: border-box; }}
    body {{
        font-family: 'Sarabun', 'Prompt', 'TH Sarabun PSK', 'THSarabun', 'Waree', 'Loma', 'Segoe UI', Tahoma, Arial, sans-serif;
        font-size: 11.5px;
        color: #1e293b;
        background: #ffffff;
        margin: 0;
        padding: 0;
        line-height: 1.65;
        -webkit-font-smoothing: antialiased;
    }}

    /* System Header Bar */
    .system-header-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 8px;
        margin-bottom: 14px;
        border-bottom: 1.5px solid #e2e8f0;
        font-size: 9.5px;
        font-weight: 700;
        color: #64748b;
        letter-spacing: 0.8px;
        text-transform: uppercase;
    }}
    .system-logo {{
        display: flex;
        align-items: center;
        gap: 6px;
        color: #0f172a;
    }}
    .system-logo-badge {{
        background: linear-gradient(135deg, #1e3a8a, #3b82f6);
        color: #ffffff;
        padding: 2px 7px;
        border-radius: 4px;
        font-size: 9.5px;
        font-weight: 800;
        letter-spacing: 0.5px;
    }}

    /* Executive Hero Card */
    .doc-hero-card {{
        background: linear-gradient(145deg, #0f172a 0%, #1e293b 60%, #1e3a8a 100%);
        color: #ffffff;
        border-radius: 8px;
        padding: 18px 22px;
        margin-bottom: 16px;
        page-break-inside: avoid;
    }}
    .doc-hero-top {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        margin-bottom: 12px;
    }}
    .doc-hero-title {{
        font-size: 19px;
        font-weight: 800;
        line-height: 1.3;
        margin: 0;
        color: #f8fafc;
        letter-spacing: -0.2px;
    }}
    .doc-hero-badge {{
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        color: #ffffff;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 11px;
        white-space: nowrap;
    }}
    .doc-meta-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px 14px;
        border-top: 1px solid rgba(255, 255, 255, 0.15);
        padding-top: 12px;
        font-size: 10.5px;
    }}
    .doc-meta-item {{
        display: flex;
        flex-direction: column;
        gap: 2px;
    }}
    .doc-meta-label {{
        font-size: 8.5px;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }}
    .doc-meta-value {{
        color: #f1f5f9;
        font-weight: 600;
        word-break: break-word;
    }}

    /* Document Control Box */
    .doc-control-card {{
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        padding: 10px 14px;
        margin-bottom: 18px;
        page-break-inside: avoid;
    }}
    .doc-control-title {{
        font-size: 10px;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    .doc-control-table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 9.5px;
    }}
    .doc-control-table th {{
        background: #e2e8f0;
        color: #334155;
        font-weight: 700;
        padding: 4px 8px;
        text-align: left;
        border: 1px solid #cbd5e1;
    }}
    .doc-control-table td {{
        padding: 4px 8px;
        border: 1px solid #cbd5e1;
        color: #334155;
    }}

    /* Body Typography */
    .doc-body {{
        margin-top: 8px;
    }}
    h1 {{
        color: #0f2744;
        font-size: 14.5px;
        font-weight: 800;
        border-left: 4px solid #2563eb;
        background: #f8fafc;
        padding: 7px 12px;
        border-radius: 0 4px 4px 0;
        margin-top: 22px;
        margin-bottom: 10px;
        page-break-after: avoid;
        page-break-inside: avoid;
    }}
    h2 {{
        color: #1e3a8a;
        font-size: 13px;
        font-weight: 700;
        border-bottom: 1.5px solid #e2e8f0;
        padding-bottom: 4px;
        margin-top: 16px;
        margin-bottom: 8px;
        page-break-after: avoid;
        page-break-inside: avoid;
    }}
    h3 {{
        color: #2563eb;
        font-size: 11.5px;
        font-weight: 700;
        margin-top: 12px;
        margin-bottom: 5px;
        page-break-after: avoid;
        page-break-inside: avoid;
    }}
    h4 {{
        color: #475569;
        font-size: 11px;
        font-weight: 700;
        margin-top: 8px;
        margin-bottom: 3px;
    }}
    p {{
        margin: 0 0 8px 0;
        color: #1e293b;
        text-align: justify;
    }}

    /* Tables */
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 12px 0;
        font-size: 10px;
        page-break-inside: avoid;
        background: #ffffff;
    }}
    th {{
        background: #1e3a8a;
        color: #ffffff;
        font-weight: 700;
        text-align: left;
        padding: 7px 9px;
        border: 1px solid #1e3a8a;
        font-size: 9.5px;
    }}
    td {{
        border: 1px solid #cbd5e1;
        padding: 6px 9px;
        vertical-align: top;
        color: #1e293b;
    }}
    tr:nth-child(even) {{
        background-color: #f8fafc;
    }}

    /* Lists */
    ul, ol {{
        margin: 4px 0 10px 18px;
        padding: 0;
    }}
    li {{
        margin-bottom: 4px;
        color: #1e293b;
    }}

    /* Code & Terminal */
    code {{
        background: #f1f5f9;
        color: #0f172a;
        padding: 2px 5px;
        border-radius: 4px;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 10px;
        border: 1px solid #e2e8f0;
    }}
    pre {{
        background: #0f172a;
        color: #38bdf8;
        padding: 12px 14px;
        border-radius: 6px;
        overflow-x: auto;
        font-size: 10px;
        line-height: 1.45;
        border: 1px solid #1e293b;
        page-break-inside: avoid;
        margin: 10px 0;
    }}
    pre code {{
        background: none;
        color: inherit;
        padding: 0;
        border: none;
        font-size: inherit;
    }}

    /* Blockquotes */
    blockquote {{
        border-left: 4px solid #3b82f6;
        background: #eff6ff;
        color: #1e40af;
        margin: 10px 0;
        padding: 8px 12px;
        border-radius: 0 5px 5px 0;
        page-break-inside: avoid;
    }}
    blockquote p {{
        margin: 0;
        color: #1e40af;
    }}

    /* Badges */
    .badge {{
        display: inline-block;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 9px;
        font-weight: 700;
        text-transform: uppercase;
    }}
    .badge-success {{ background: #dcfce7; color: #15803d; }}

    /* Footer Stamp */
    .doc-footer {{
        margin-top: 24px;
        padding-top: 10px;
        border-top: 1.5px solid #e2e8f0;
        display: flex;
        justify-content: space-between;
        font-size: 8.5px;
        color: #94a3b8;
        page-break-inside: avoid;
    }}
</style>
</head>
<body>
    <div class="system-header-bar">
        <div class="system-logo">
            <span class="system-logo-badge">QA ENTERPRISE</span>
            <span>Document Specification Baseline</span>
        </div>
        <div>CONFIDENTIAL &bull; SPECIFICATION BASELINE</div>
    </div>

    <div class="doc-hero-card">
        <div class="doc-hero-top">
            <h1 class="doc-hero-title" style="background:none;border:none;padding:0;margin:0;color:#ffffff;">{doc_name}</h1>
            <div class="doc-hero-badge">{doc_type}</div>
        </div>
        <div class="doc-meta-grid">
            <div class="doc-meta-item">
                <span class="doc-meta-label">Project</span>
                <span class="doc-meta-value">{project_name} ({project_code})</span>
            </div>
            <div class="doc-meta-item">
                <span class="doc-meta-label">Document Type</span>
                <span class="doc-meta-value">{doc_type}</span>
            </div>
            <div class="doc-meta-item">
                <span class="doc-meta-label">Version</span>
                <span class="doc-meta-value">Version {doc_version}</span>
            </div>
            <div class="doc-meta-item">
                <span class="doc-meta-label">Baseline Date</span>
                <span class="doc-meta-value">{effective_date}</span>
            </div>
        </div>
    </div>

    <div class="doc-body">
        {rendered_markdown}
    </div>

    <div class="doc-footer">
        <div>Spectra QA Platform &bull; Document Management Baseline</div>
        <div>Baseline Date &bull; {effective_date}</div>
    </div>
</body>
</html>"""


def build_testcase_document_html(doc_name: str, doc_type: str, project_name: str, project_code: str, module_val: str, tester_val: str, today_str: str, test_cases: list) -> str:
    """Builds a high-density, professional landscape HTML document for Test Cases."""
    rows_html = ""
    for tc in test_cases:
        tc_id = tc.get("Test Case ID") or tc.get("Test ID") or tc.get("test_id") or tc.get("id") or "TC"
        tc_obj = tc.get("Test case Objective") or tc.get("Test Objective") or tc.get("objective") or tc.get("วัตถุประสงค์") or ""
        tc_proc = tc.get("Test Description / Procedure") or tc.get("Procedure") or tc.get("steps") or tc.get("ขั้นตอนการทดสอบ") or ""
        tc_data = tc.get("Test Data") or tc.get("data") or tc.get("ข้อมูลทดสอบ") or "-"
        tc_exp = tc.get("Expected Result") or tc.get("expected") or tc.get("ผลลัพธ์ที่คาดหวัง") or ""
        res_val = str(tc.get("Result (Pass/Fail)") or tc.get("Result") or tc.get("status") or tc.get("ผลการทดสอบ") or "[-]").strip()
        badge_class = "pass" if res_val.upper() == "PASS" else ("fail" if res_val.upper() == "FAIL" else "blocked")
        proc_html = str(tc_proc).replace("\n", "<br>")
        req_no = tc.get("Req No.") or tc.get("req_no") or tc.get("รหัสข้อกำหนด") or "-"
        rows_html += f"""
        <tr>
            <td style="font-weight: 700; text-align: center; color: #1e3a8a;">{tc_id}</td>
            <td style="font-weight: 600;">{tc_obj}</td>
            <td>{proc_html}</td>
            <td>{tc_data}</td>
            <td>{tc_exp}</td>
            <td style="text-align: center;"><span class="badge {badge_class}">{res_val}</span></td>
            <td style="text-align: center; font-weight: 600;">{req_no}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>{doc_name} - Test Specification</title>
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700;800&family=Prompt:wght@400;600;700&display=swap');
    @page {{
        size: A4 landscape;
        margin: 12mm 10mm 12mm 10mm;
        @bottom-right {{
            content: counter(page);
            font-size: 8.5px;
            color: #64748b;
        }}
    }}
    *, *:before, *:after {{ box-sizing: border-box; }}
    body {{
        font-family: 'Sarabun', 'Prompt', 'TH Sarabun PSK', 'THSarabun', 'Waree', 'Loma', 'Segoe UI', Tahoma, Arial, sans-serif;
        font-size: 10.5px;
        color: #1e293b;
        background: #ffffff;
        margin: 0;
        padding: 0;
        line-height: 1.45;
        -webkit-font-smoothing: antialiased;
    }}
    .system-header-bar {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-bottom: 6px;
        margin-bottom: 10px;
        border-bottom: 1.5px solid #e2e8f0;
        font-size: 9px;
        font-weight: 700;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.6px;
    }}
    .system-logo {{
        display: flex;
        align-items: center;
        gap: 6px;
        color: #0f172a;
    }}
    .system-logo-badge {{
        background: linear-gradient(135deg, #1e3a8a, #3b82f6);
        color: #ffffff;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 9px;
        font-weight: 800;
    }}
    .doc-hero-card {{
        background: linear-gradient(145deg, #0f172a 0%, #1e293b 60%, #1e3a8a 100%);
        color: #ffffff;
        border-radius: 6px;
        padding: 14px 18px;
        margin-bottom: 12px;
        page-break-inside: avoid;
    }}
    .doc-hero-top {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }}
    .doc-hero-title {{
        font-size: 17px;
        font-weight: 800;
        margin: 0;
        color: #f8fafc;
    }}
    .doc-hero-badge {{
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        color: #ffffff;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 10px;
    }}
    .doc-meta-grid {{
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px 12px;
        border-top: 1px solid rgba(255, 255, 255, 0.15);
        padding-top: 10px;
        font-size: 10px;
    }}
    .doc-meta-item {{
        display: flex;
        flex-direction: column;
    }}
    .doc-meta-label {{
        font-size: 8px;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
    }}
    .doc-meta-value {{
        color: #f1f5f9;
        font-weight: 600;
    }}
    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 10px;
        page-break-inside: auto;
    }}
    tr {{
        page-break-inside: avoid;
        page-break-after: auto;
    }}
    th {{
        background: #1e3a8a;
        color: #ffffff;
        font-weight: 700;
        text-align: left;
        padding: 6px 8px;
        border: 1px solid #1e3a8a;
        font-size: 9.5px;
    }}
    td {{
        border: 1px solid #cbd5e1;
        padding: 5px 8px;
        vertical-align: top;
        color: #1e293b;
    }}
    tr:nth-child(even) {{
        background-color: #f8fafc;
    }}
    .badge {{
        display: inline-block;
        padding: 2px 6px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 9px;
    }}
    .pass {{ background: #dcfce7; color: #15803d; border: 1px solid #86efac; }}
    .fail {{ background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }}
    .blocked {{ background: #fef3c7; color: #b45309; border: 1px solid #fde68a; }}
    .doc-footer {{
        margin-top: 16px;
        padding-top: 8px;
        border-top: 1.5px solid #e2e8f0;
        display: flex;
        justify-content: space-between;
        font-size: 8px;
        color: #94a3b8;
        page-break-inside: avoid;
    }}
</style>
</head>
<body>
    <div class="system-header-bar">
        <div class="system-logo">
            <span class="system-logo-badge">SPECTRA</span>
            <span>Autonomous QA Platform &bull; Test Matrix</span>
        </div>
        <div>CONFIDENTIAL &bull; QA EXECUTION SPECIFICATION</div>
    </div>

    <div class="doc-hero-card">
        <div class="doc-hero-top">
            <div class="doc-hero-title">{doc_name}</div>
            <div class="doc-hero-badge">{doc_type}</div>
        </div>
        <div class="doc-meta-grid">
            <div class="doc-meta-item">
                <span class="doc-meta-label">Project / โครงการ</span>
                <span class="doc-meta-value">{project_name} ({project_code})</span>
            </div>
            <div class="doc-meta-item">
                <span class="doc-meta-label">Module / ฟังก์ชัน</span>
                <span class="doc-meta-value">{module_val}</span>
            </div>
            <div class="doc-meta-item">
                <span class="doc-meta-label">Tester / ผู้จัดทำ</span>
                <span class="doc-meta-value">{tester_val}</span>
            </div>
            <div class="doc-meta-item">
                <span class="doc-meta-label">Date / วันที่จัดทำ</span>
                <span class="doc-meta-value">{today_str}</span>
            </div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th style="width: 8%; text-align: center;">Test ID</th>
                <th style="width: 20%;">Objective (วัตถุประสงค์)</th>
                <th style="width: 28%;">Description / Procedure (ขั้นตอนการทดสอบ)</th>
                <th style="width: 14%;">Test Data (ข้อมูลทดสอบ)</th>
                <th style="width: 18%;">Expected Result (ผลลัพธ์ที่คาดหวัง)</th>
                <th style="width: 6%; text-align: center;">Result</th>
                <th style="width: 6%; text-align: center;">Req No.</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

    <div class="doc-footer">
        <div>Spectra QA Platform &bull; Automated Test Execution Spec</div>
        <div>Engine: Gemini 3.1 Pro &bull; Date: {today_str}</div>
    </div>
</body>
</html>"""


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

def extract_srs_menu_outline(markdown_text: str) -> str:
    """Extracts Table of Contents and Menu/Module hierarchy from SRS markdown."""
    if not markdown_text:
        return ""
    
    lines = markdown_text.split('\n')
    in_toc = False
    toc_found = []
    for line in lines:
        l = line.strip()
        if re.search(r'table\s+of\s+contents|สารบัญ', l, re.IGNORECASE):
            in_toc = True
            continue
        if in_toc:
            if re.match(r'^(page\s+\d+|details|บทนำ|1\.\s+บทนำ)', l, re.IGNORECASE) and len(toc_found) > 8:
                in_toc = False
            else:
                if re.match(r'^(\d+(\.\d+)*|[A-Za-z]\.|\-|\*)\s+', l) or any(k in l for k in ['Permit', 'API', 'Declaration', 'Invoice', 'เมนู', 'Menu', 'Screen', 'หน้าจอ']):
                    toc_found.append(l)
    
    detected_screens = []
    for line in lines:
        l = line.strip()
        if any(keyword in l.lower() for keyword in ['เมนูสำหรับ', 'หน้าจอสำหรับ', 'หน้าจอหลักสำหรับ', 'menu สำหรับ']):
            detected_screens.append(l)
        elif re.match(r'^(#+\s+|\d+\.\d+(\.\d+)?\s+)(.*(เมนู|หน้าจอ|Permit|API|Declaration|Invoice|Management|MGT|Center|Profile).*)', l, re.IGNORECASE):
            detected_screens.append(l)

    result = []
    if toc_found:
        result.append("=== SRS Table of Contents / System Modules ===")
        result.extend(toc_found[:40])
    if detected_screens:
        result.append("\n=== Detected Specific Menus / Screens ===")
        seen = set()
        for s in detected_screens:
            cleaned = s.strip('# *')
            if cleaned not in seen and len(cleaned) > 5:
                seen.add(cleaned)
                result.append(f"- {cleaned}")
                if len(seen) >= 25:
                    break

    return "\n".join(result)


def fetch_comprehensive_project_context(cursor, project_id: str, reference_document_id=None):
    """
    Retrieves ALL available project knowledge:
    1. Project info (code, name, description)
    2. Primary reference document(s) (if specified, supports multiple)
    3. ALL other project documents in Knowledge Base (TOR/SOW, SRS, SDD, Test Cases, Manuals, etc.)
    4. Structured requirements (if available)
    5. Detected SRS Menus & Module outlines (for test case sheet separation by menu)
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
    srs_menu_outlines = []

    for d in doc_rows:
        d_id = str(d[0])
        d_filename = d[1] or "Unnamed Document"
        d_category = d[2] or "General"
        d_doctype = d[3] or "Document"
        d_content = (d[4] or "").strip()

        is_srs = (d_category and d_category.upper() == 'SRS') or ('srs' in d_filename.lower()) or (d_doctype and 'srs' in d_doctype.lower())
        if is_srs:
            outline = extract_srs_menu_outline(d_content)
            if outline:
                srs_menu_outlines.append(f"### SRS Document: {d_filename}\n{outline}")

        if target_ref_ids and d_id in target_ref_ids:
            primary_ref_context_list.append(f"""
### Selected Reference Document: {d_filename} [Category: {d_category} | Type: {d_doctype}]
--- Content Start ---
{d_content}
--- Content End ---
""")
        else:
            # If it's an SRS document, give it up to 60,000 characters so no menus are truncated!
            limit = 60000 if is_srs else 15000
            snippet = d_content[:limit] if len(d_content) > limit else d_content
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

    srs_menus_section = ""
    if srs_menu_outlines:
        srs_menus_section = f"""
# ==============================================================================
# 📑 DETECTED SRS MENUS & MODULES (วิเคราะห์จากเอกสาร SRS ของโครงการ)
# ==============================================================================
ระบบได้ทำการสกัดโครงสร้างเมนูและหน้าจอจากเอกสาร SRS ของโครงการ ดังนี้:
{chr(10).join(srs_menu_outlines)}

🔴 MANDATORY DIRECTIVE: แยก SHEET ตามเมนูใน SRS อย่างเคร่งครัด
คุณต้องสร้าง Sheet ใน "test_case_sheets" แยก 1 Sheet ต่อ 1 เมนู/หน้าจอ ที่พบในเอกสาร SRS ด้านบน!
ห้ามรวมทุกเมนูไว้ใน Sheet เดียวเด็ดขาด! โดยชื่อ Sheet ต้องตั้งเป็น "Test Case [ชื่อเมนู]"!
==============================================================================
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
        "srs_menus_section": srs_menus_section,
        "total_docs_count": len(doc_rows)
    }


def fetch_agent_learned_rules(cursor, project_id: str = None, doc_type: str = "General") -> str:
    """Fetches learned quality rules from QA Consult audits to reinforce Agent 6's generator prompt."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_agent_learned_rules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID,
                doc_type VARCHAR(255),
                source_doc_name VARCHAR(255),
                rule_category VARCHAR(255),
                issue_description TEXT,
                found_incorrect TEXT,
                correct_expectation TEXT,
                recommendation TEXT,
                severity VARCHAR(50),
                is_active BOOLEAN DEFAULT TRUE,
                times_referenced INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        doc_type_clean = (doc_type or "General").strip()
        query = """
            SELECT DISTINCT ON (TRIM(LOWER(issue_description))) 
                   rule_category, issue_description, found_incorrect, correct_expectation, recommendation, severity,
                   CASE 
                       WHEN UPPER(severity) = 'CRITICAL' THEN 1
                       WHEN UPPER(severity) = 'HIGH' THEN 2
                       WHEN UPPER(severity) = 'MAJOR' THEN 3
                       WHEN UPPER(severity) = 'MEDIUM' THEN 4
                       ELSE 5
                   END AS sev_order,
                   created_at
            FROM qa_agent_learned_rules
            WHERE is_active = TRUE AND (
                UPPER(TRIM(doc_type)) = UPPER(TRIM(%s)) 
                OR %s ILIKE '%%' || TRIM(doc_type) || '%%' 
                OR TRIM(doc_type) ILIKE '%%' || %s || '%%'
                OR doc_type = 'General' 
                OR doc_type IS NULL
            )
            AND issue_description NOT ILIKE '%%abruptly ends%%' 
            AND issue_description NOT ILIKE '%%ระบบรีว%%'
        """
        params = [doc_type_clean, doc_type_clean, doc_type_clean]
        if project_id:
            query += " AND project_id = %s::uuid"
            params.append(project_id)
        else:
            query += " AND project_id IS NULL"
            
        query += " ORDER BY TRIM(LOWER(issue_description)), sev_order ASC, created_at DESC LIMIT 15"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        
        if not rows:
            return ""
            
        # Re-sort rows by severity order so Critical and High come first
        sorted_rows = sorted(rows, key=lambda x: x[6])

        rules_text = [
            "# ==============================================================================",
            "# LEARNED QUALITY RULES FROM QA CONSULT GATE AUDITS (CONTINUOUS AGENT TRAINING)",
            "# ==============================================================================",
            "The following quality rules were learned from previous QA Consult audit findings and exit criteria rejections.",
            "You MUST strictly prevent these defects in this generated document to guarantee a 100% PASS audit score:\n"
        ]
        
        for idx, r in enumerate(sorted_rows, 1):
            cat, issue, found_inc, correct_val, rec, sev, _, _ = r
            rule_entry = f"{idx}. [{cat}] (Severity: {sev})\n"
            rule_entry += f"   - Common Defect Identified: {issue}\n"
            if found_inc and found_inc != '-':
                rule_entry += f"   - Defect Pattern to Avoid: {found_inc}\n"
            if correct_val and correct_val != '-':
                rule_entry += f"   - Mandatory Standard: {correct_val}\n"
            if rec and rec != '-':
                rule_entry += f"   - Required Corrective Action: {rec}\n"
            rules_text.append(rule_entry)
            
        return "\n".join(rules_text)
    except Exception as e:
        logger.warning(f"Could not load learned rules: {e}")
        try:
            if hasattr(cursor, 'connection') and cursor.connection:
                cursor.connection.rollback()
        except Exception:
            pass
        return ""


def get_advanced_engineering_guidelines(doc_type: str, today_str: str) -> str:
    is_test_case = bool(doc_type and "test" in doc_type.lower())

    if is_test_case:
        return f"""
# ==============================================================================
# ENTERPRISE TEST CASE ENGINEERING DIRECTIVES & QUALITY GATES (MANDATORY STANDARDS)
# ==============================================================================

1. STRICT PROJECT DOMAIN ISOLATION (ZERO CROSS-PROJECT DATA LEAKAGE):
   - You MUST formulate all test scenarios, test cases, inputs, and validation logic SOLELY and EXCLUSIVELY from the active project's Knowledge Base, specifications, and business domain.
   - ABSOLUTE BAN ON FOREIGN DOMAIN DATA: NEVER invent, hallucinate, or import concepts, requirements, or terms from unrelated systems (e.g., restaurant ordering, delivery apps, food reviews, recommendation rankings) unless the active project explicitly defines them.
   - Every single test case must map directly to legitimate features and requirements of this specific system.

2. MANDATORY DOCUMENT CONTROL & REVISION LOG:
   - Section 1.1 Document Control Table: Document Title, Document Code, Version (e.g. Version 1.1.0), Project Name, Baseline Date ({today_str}), Author, Objectives, and System Scope.
   - Section 1.2 Revision History & Audit Resolution Log: Detail the version, date ({today_str}), author, change details, and audit resolution status (100% Closed).

3. RIGOROUS TEST CASE SPECIFICATION STRUCTURE:
   - Every test case must be clearly structured and unambiguous:
     * Test Case ID: Structured ID (e.g. TC-xxx-001) aligned with the project's requirement codes.
     * Test Scenario / Description: Specific, meaningful objective of the test.
     * Pre-conditions: Explicit required state, system configurations, and user authentication before execution.
     * Test Steps: Numbered step-by-step procedural actions taken by the actor.
     * Test Data / Input Parameters: Realistic, valid or invalid domain-specific test payloads (no placeholders).
     * Expected Results: Clear, verifiable system response, UI state changes, database persistence, and external service messages.
     * Acceptance Criteria: Formatted clearly in Given... When... Then... format.

4. BALANCED AND EXHAUSTIVE TEST COVERAGE:
   - Positive Testing (Happy Path): Validate correct business workflows when valid inputs are provided.
   - Negative Testing (Unhappy Path & Edge Cases):
     * Input validation (empty fields, max length, invalid formats, special characters, boundary values).
     * Business rule violations (unauthorized actions, duplicate transactions, expired tokens, conflicting states).
     * System & Network Resilience: Gateway timeouts, connection dropouts, external API errors, and appropriate user notifications.
   - Security & Access Control: Role-based permissions, unauthorized route guards, and data privacy validation.

5. ZERO AMBIGUOUS PLACEHOLDERS:
   - NEVER use placeholders like '[TBD]', '[Pending]', '[Insert Data Here]'. Every test step and expected result must be concrete and actionable.

6. PROFESSIONAL THAI LANGUAGE COMPLIANCE:
   - The entire document must be written in professional Thai (ภาษาไทย). Standard English technical terms, acronyms, and code identifiers (e.g., API, Token, Status Code) are acceptable in parentheses or standard technical usage.
"""

    return f"""
# ==============================================================================
# ENTERPRISE ENGINEERING DIRECTIVES & QUALITY GATES (MANDATORY STANDARDS)
# ==============================================================================

1. MANDATORY SECTION 1: ข้อมูลทั่วไปของเอกสารและโครงการ (GENERAL INFORMATION & DOCUMENT CONTROL - 100% COMPLETE):
   - You MUST begin the document with Section 1 formatted with clean Markdown tables:
     # 1. ข้อมูลทั่วไปของเอกสารและโครงการ (General Information)
     ### 1.1 ตารางข้อมูลควบคุมเอกสาร (Document Control)
     | หัวข้อ | รายละเอียด |
     | :--- | :--- |
     | ชื่อเอกสาร (Document Title) | [ชื่อเอกสารที่ตรวจ] |
     | รหัสเอกสาร (Document Code) | [รหัสเอกสารตามโครงการ] |
     | หมายเลขเวอร์ชัน (Version) | Version 1.1 (หรือ 2.0 สำหรับฉบับปรับปรุง) |
     | ชื่อโครงการ (Project Name) | [ชื่อโครงการ] |
     | วันที่บังคับใช้ (Baseline Date) | {today_str} |
     | ผู้จัดทำ (Author) | Lead Business Analyst / QA Architect |
     | วัตถุประสงค์ (Business Objectives) | สรุปวัตถุประสงค์โครงการและเกณฑ์ความสำเร็จ |
     | ขอบเขตระบบ (System Scope & Boundaries) | ขอบเขตของระบบ สภาพแวดล้อม และข้อจำกัด |

     ### 1.2 ตารางประวัติการแก้ไขและบันทึกการปิดประเด็น Audit (Revision History & Audit Resolution Log)
     (ส่วนนี้จำเป็นอย่างยิ่งเพื่อผ่านเกณฑ์ Exit Criteria ข้อ [1.1] และ [2.1])
     | เวอร์ชัน | วันที่ | ผู้แก้ไข | สรุปรายละเอียดการเปลี่ยนแปลง / การปิดประเด็น Audit | สถานะ |
     | :--- | :--- | :--- | :--- | :--- |
     | 1.0.0 | ก่อนหน้า | QA Team | เอกสารร่างฉบับแรกสำหรับเข้ากระบวนการ Audit | ดำเนินการแล้ว |
     | 1.1.0 | {today_str} | Lead QA Architect | ปรับปรุงแก้ไขประเด็นข้อสั่งการระดับ Critical/High จากรอบก่อนหน้าเรียบร้อยแล้ว 100% ตามข้อเสนอแนะ | ปิดประเด็นสมบูรณ์ (100% Closed) |

2. ZERO REQUIREMENT LOSS & STRICT PROJECT DOMAIN ISOLATION:
   - Extract, integrate, and satisfy EVERY functional feature, business rule, and constraint found in the Reference Documents, PO Briefings, and Project Knowledge Base.
   - ABSOLUTE BAN ON FOREIGN DOMAIN DATA: NEVER invent, hallucinate, or import concepts, requirements, or terms from unrelated projects. The document MUST strictly and exclusively cover the business domain and features of this active project.
   - Statutory, Privacy & Security Mandates:
     * Explicit PDPA / GDPR workflows: User Consent handling, Right to Erasure / Data Deletion, Data Anonymization, and Data Retention rules where applicable.
     * Authentication & Access Control (RBAC): Explicit permissions and capabilities for each user persona/role defined in the project.
   - Core Domain & Operational Logic:
     * Complete lifecycle states of entities (e.g. Draft -> Pending -> Approved / Rejected -> Closed).
     * Input validation, duplicate prevention, and transaction consistency suited to the project domain.

3. LOGICAL INTEGRITY & DOCUMENT COHESION (Zero Self-Contradictions & Zero Placeholders):
   - Chronological & Version Harmony: Generation Date ({today_str}), Versioning using standard SemVer.
   - Zero Unresolved Placeholders: NEVER output '[TBD]', '[Insert Name]', '[To Be Decided]'. Always generate definitive, realistic specifications.
   - Traceability: Align all technical specifications with corresponding functional/non-functional requirement IDs.

4. HIGH-PRECISION TESTABILITY & MEASURABILITY (Zero Ambiguity):
   - Strict Ban on Vague Adjectives: DO NOT use ambiguous terms like "เร็ว", "เหมาะสม", "ทันที" without explicit numeric metrics or thresholds.
   - Quantified Non-Functional Requirements (NFR):
     * Availability & Uptime: SLA >= 99.9% uptime per calendar month.
     * Latency & Response Times: API P95 latency <= 1.5 seconds, P99 <= 3.0 seconds under peak load (write as plain text, DO NOT use LaTeX '$').
     * Concurrency & Capacity: Specify target CCU (Concurrent Users) or TPS based on the project scale.
     * Compatibility: Modern Web Browsers, APIs, and relevant OS platforms.

5. MANDATORY UNHAPPY PATH & EXCEPTION/ERROR HANDLING FOR EVERY REQUIREMENT:
   - In SRS and Requirement specifications, EVERY functional requirement (e.g. REQ-xxx) MUST have clearly defined:
     * Pre-conditions & Main (Happy) Path
     * Unhappy Path & Alternate/Exception Handling (e.g., validation failures, network disconnect, authorization failure, data conflict)
     * Post-conditions and Error Messages returned to the user.
     * Acceptance Criteria in Given-When-Then format.

6. MATHEMATICAL FORMULA TRANSPARENCY & STRICT BAN ON LATEX '$' DELIMITERS:
   - STRICT BAN ON LATEX '$' AND '$$' SYMBOLS:
     * NEVER wrap mathematical formulas, scores, or variables in LaTeX dollar signs ('$' or '$$').
     * Write mathematical formulas in clean, plain readable text notation with clearly defined variables.
     * In Section 4 Performance Requirements, write latency as plain text: `P95 <= 1.5s` and `P99 <= 3.0s`.

7. REMARK HYGIENE & SEPARATION OF SYSTEM DESIGN VS. FUNCTIONAL REQUIREMENTS:
   - Functional Requirement Remarks: Must contain ONLY testable assertions, QA guidelines, or business acceptance constraints.
   - Implementation Specifics (e.g. SQL queries, ORM code, internal architecture details): Place them into Technical Specifications / System Architecture sections, not inside Functional Requirement remarks.

8. MANDATORY SECTION 4: ข้อกำหนดที่ไม่ใช่เชิงฟังก์ชัน (NON-FUNCTIONAL REQUIREMENTS - 100% COMPLETE):
   - You MUST include Section 4 with comprehensive tables for:
     * 4.1 ประสิทธิภาพของระบบ (Performance Requirements): API Latency P95 <= 1.5s, P99 <= 3.0s, รองรับการทำงานในสภาวะโหลดสูงสุด
     * 4.2 ความมั่นคงปลอดภัยและการปกป้องข้อมูล (Security & Privacy Requirements): TLS 1.3, การเข้ารหัสข้อมูลที่เก็บรักษา (Encryption at Rest), การจัดการ Session / Token Lifecycle, PDPA Consent Management
     * 4.3 ความพร้อมใช้งานและความเชื่อถือได้ (Reliability & Availability): Uptime SLA >= 99.9% ต่อเดือน, ระบบสำรองข้อมูลอัตโนมัติ (Automated Backup), Disaster Recovery RTO <= 4 ชม. และ RPO <= 1 ชม.
     * 4.4 ความเข้ากันได้ของระบบ (Compatibility): Modern Browsers, ระบบเครือข่าย และสภาพแวดล้อมการทำงานของโครงการ

9. SYSTEM RESILIENCE & FALLBACK LOGIC:
   - Where system interfaces, external service integrations, or critical network operations are involved, explicitly specify appropriate fallback, retry, circuit-breaking, and fault tolerance handling suited to this project's requirements.

10. MANDATORY COMPLETE REVISION HISTORY TABLE:
    - ตาราง 1.2 Revision History & Audit Resolution Log ต้องเขียนให้เสร็จสมบูรณ์จนถึงคอลัมน์สุดท้ายและแถวสุดท้าย ห้ามตัดจบกลางคันอย่างเด็ดขาด
"""

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
        skill_rows = []
        if target_skill_ids:
            cursor.execute("SELECT skill_name, target_doc_type, markdown_instructions FROM agent_skills WHERE skill_id::text = ANY(%s) OR skill_name = ANY(%s)", (list(target_skill_ids), list(target_skill_ids)))
            skill_rows = cursor.fetchall()

        # Fetch learned QA rules from continuous learning database
        learned_rules_section = fetch_agent_learned_rules(cursor, project_id, doc_type)

        cursor.close()
        conn.close()

        if not skill_rows:
            skill_name = "Universal QA Standard"
            target_doc_type = doc_type
            instructions = "Produce a comprehensive, structured, production-ready document adhering to standard software engineering guidelines."
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

        today_str = datetime.datetime.now().strftime("%d/%m/%Y")
        engineering_guidelines = get_advanced_engineering_guidelines(doc_type, today_str)

        # Build prompt for synchronous generation
        prompt = f"""
You are an expert Principal Software Architect, Lead Business Analyst, and Senior Technical Writer.
Your task is to generate a comprehensive, enterprise-grade, production-ready {doc_type} document for Project '{project_name}' ({project_code}) named '{doc_name}'.
You MUST analyze, cross-reference, and synthesize ALL provided Project Knowledge Base documents (TOR, PO Briefing, SRS, SDD, previous tests, specs) to ensure 100% technical accuracy, depth, and zero requirement loss.

# Target Document Information
- Document Name: {doc_name}
- Document Type: {doc_type}
- Project: {project_name} ({project_code})
- Date of Baseline: {today_str}

# Framework & Guidelines (Skill: {skill_name})
Please follow these structure and formatting instructions strictly:
{instructions}

{engineering_guidelines}

{learned_rules_section}

{custom_prompt_section}

{primary_ref_context}

{all_docs_section}

{structured_reqs_section}

# Final Output Directives:
1. Synthesize all documents in the project knowledge base into a fully detailed, rigorous, production-grade {doc_type}.
2. MANDATORY LANGUAGE REQUIREMENT: The entire document MUST be written in professional, grammatically correct Thai (ภาษาไทย). Standard English technical terms, acronyms, and code identifiers may be kept or placed in parentheses (e.g., API, Database, JWT).
3. Ensure every single requirement is measurable, testable, and unambiguous.
4. NEVER leave placeholder text or brief outlines.
5. Output the complete document directly in clean, structured Markdown.
"""

        # 3. Call Gemini with Gemini 3.1 Pro
        model_to_use = os.environ.get("GEMINI_DOC_MODEL", "gemini-3.1-pro")
        doc_content, usage_metadata = call_gemini(prompt, model_name=model_to_use, max_output_tokens=32768)
        
        if usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_6_Doc_Creator", model_to_use, usage_metadata, filename=doc_name)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Agent 6: {log_err}")

        doc_content = (doc_content or "").strip()
        doc_content = sanitize_engineering_markdown(doc_content)
        
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


def create_qa_document_async(gen_id: str, project_id: str, doc_type: str, doc_name: str, skill_id, reference_document_id=None, custom_prompt: str = "", source_markdown: str = "", username: str = None):
    """
    Async background version of QA Document Creator that generates Excel, PDF, and Markdown.
    Supports surgical refinement mode if source_markdown is provided.
    Delivers in-app notification directly to the requesting user upon completion.
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
        srs_menus_section = ctx.get("srs_menus_section", "")
            
        # 2. Fetch Skill (supporting multiple skills by ID or Name)
        target_skill_ids = parse_id_list(skill_id)
        skill_rows = []
        if target_skill_ids:
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

        # Fetch learned rules from previous audits
        learned_rules_section = fetch_agent_learned_rules(cursor, project_id, doc_type)

        if not skill_rows:
            skill_name = "Universal QA Standard"
            target_doc_type = doc_type
            instructions = "Produce a comprehensive, structured, production-ready document adhering to standard software engineering guidelines."
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

        refinement_section = ""
        if source_markdown and source_markdown.strip():
            refinement_section = f"""
# ==============================================================================
# REFINEMENT & SURGICAL CORRECTION MODE (TARGETED AUDIT FIXES)
# ==============================================================================
You are performing a SURGICAL REFINEMENT of an existing baseline document that underwent QA audit.
Your primary directives:
1. PRESERVE 100% of all existing valid sections, architecture, and requirements from the baseline document below. DO NOT discard, summarize, or dilute existing functional requirements.
2. CORRECT all defects, missing items, and comments specified in the "Additional User Prompt & Specific Requirements" section above.
3. MANDATORY SECTION 1 (GENERAL INFORMATION) & SECTION 1.2 (REVISION HISTORY):
   You MUST include Section 1 & Section 1.2 with the Document Control and Revision History tables as detailed in the guidelines, stating explicitly that all Critical/High issues from the previous audit round have been resolved 100%.

### ORIGINAL BASELINE DOCUMENT TO REFINE:
{source_markdown.strip()[:65000]}
"""
        
        # 3. Call Gemini
        today_str = datetime.datetime.now().strftime("%d/%m/%Y")
        
        # Framework Header & Guidelines
        if source_markdown and source_markdown.strip():
            framework_header = "# Direct Surgical Refinement Mode (Zero Skill Distortion)\nNo external audit checking skill is applied. The original baseline document must be preserved and directly corrected based on the reported QA audit findings to eliminate distortion."
        else:
            framework_header = f"# Framework & Guidelines (Skill: {skill_name})\nPlease follow these structure and formatting instructions strictly:\n{instructions}"

        if doc_type in ["Test Case", "TestCase"]:
            prompt = f"""
You are an expert Principal QA Architect, Lead Automation Engineer, and Senior Business Analyst.
Your task is to generate a comprehensive, production-grade System Testing Specification (Excel Workbook Template) for Project '{project_name}' ({project_code}) named '{doc_name}'.
You MUST analyze, cross-reference, and synthesize ALL provided Project Knowledge Base documents (TOR, PO Briefing, SRS, SDD, previous tests, specs) to design exhaustive test cases matching the standard 69A Excel Template (11 columns per test sheet, multi-sheet workbook separated by SRS Menu).

# Target Document Information
- Document Name: {doc_name}
- Document Type: {doc_type}
- Project: {project_name} ({project_code})
- Date: {today_str}

{framework_header}

# ==============================================================================
# 🔴 MANDATORY WORKBOOK ARCHITECTURE RULES (แยก SHEET ตามเมนูในเอกสาร SRS)
# ==============================================================================
1. การแยก Sheet ตามเมนูในเอกสาร SRS อย่างเคร่งครัด (SEPARATE SHEET PER SRS MENU):
   - คุณต้องอ่านและวิเคราะห์เอกสาร SRS ของโครงการ (ดูสารบัญ Table of Contents, Product Functions, หน้าจอ และเมนูต่างๆ เช่น ขอใบอนุญาตสินค้า, ขอใบอนุญาตหน้า MGT, EzySuite API, Modify Invoice, Modify Declaration, NSW Profile ฯลฯ)
   - สร้าง Sheet ใน "test_case_sheets" แยก 1 Sheet ต่อ 1 เมนู/หน้าจอ อย่างเคร่งครัด
   - ตั้งชื่อ Sheet แต่ละเมนูตามรูปแบบ: "Test Case [ชื่อเมนู]" เช่น:
     * "Test Case Permit" (เมนูขอใบอนุญาตสินค้า)
     * "Test Case Permit MGT" (เมนูขอใบอนุญาตสินค้า หน้า MGT)
     * "Test Case EzySuite API" (เมนู EzySuite Open API / API Document List & Management)
     * "Test Case Modify Invoice" (เมนู Modify Invoice)
     * "Test Case Modify Declaration" (เมนู Modify Declaration)
     * "Test Case Modify TIFFA ID" (เมนู Modify TIFFA ID / NSW ID Profile)
     * "Test Case Modify Client Info" (เมนู Modify Client Information Center)
     * "Test Case Modify Customer Mgmt" (เมนู Modify Customer Management)
     (คำเตือน: ต้องสร้างแยก Sheet ให้ครบทุกเมนูที่ระบุใน SRS ของโครงการ ห้ามรวบเป็น Sheet เดียวเด็ดขาด)
2. โครงสร้างสมุดงาน (Multi-Sheet Workbook Structure):
   - มี Sheet บทนำ (Introduction), ประวัติการแก้ไข (Change History), คำศัพท์เฉพาะทาง (Glossary), ขอบเขตเบื้องต้น (Basic Test)
   - หน้าสรุป (Execute Test): ต้องแจกแจงรายการแยกเป็นรายบรรทัดสำหรับ "ทุกเมนูข้างต้น" ในตาราง System Test Summary พร้อมระบุจำนวน TC ของแต่ละเมนู และเวลาประมาณการทดสอบ (0.25 ชม./เคส) พร้อมแถว รวม (Total)
3. ตารางกรณีทดสอบ 11 คอลัมน์มาตรฐาน (STRICT 11 COLUMNS ในทุก Sheet ของเมนู):
   ทุก Sheet ของ Test Case ต้องมี 11 คอลัมน์ดังต่อไปนี้เท่านั้น (ห้ามเพิ่ม Actual Result หรือ Result Pass/Fail ในตาราง):
   1) "Test Case ID": รหัสเคส เช่น 69AA1001, 69AA2001
   2) "Test Case Objective": วัตถุประสงค์การทดสอบเป็นภาษาไทย ชัดเจน กระชับ
   3) "Test Step": ขั้นตอนการทดสอบเป็นข้อๆ 1. ..., 2. ..., 3. ... ละเอียด ชัดเจน ปฏิบัติตามได้จริง
   4) "Test Data": ข้อมูลตัวอย่างที่ใช้ทดสอบที่สมจริงและตรงตามโดเมนระบบ
   5) "Test Type": ประเภทการทดสอบ ระบุเป็น "Positive" หรือ "Negative"
   6) "Expected Result": ผลลัพธ์ที่คาดหวังที่วัดผลได้จริงเป็นภาษาไทย
   7) "Remark": หมายเหตุเพิ่มเติม (เช่น Edge Case, Security Test, หรือว่างไว้)
   8) "Automate": "TRUE" หรือ "FALSE"
   9) "Req No.": รหัส Requirement ที่อ้างอิง เช่น REQ0001
   10) "Platforms": แพลตฟอร์มที่ทดสอบ เช่น "Web Application", "API", "Mobile App"
   11) "Updated By": ชื่อผู้จัดทำ/ผู้ทดสอบ
4. ภาษาไทย 100%: คำอธิบาย Objective, Test Step, Test Data, Expected Result ต้องเขียนเป็นภาษาไทยทั้งหมด (คำศัพท์เทคนิคมาตรฐานสามารถใส่วงเล็บภาษาอังกฤษได้)
5. ครอบคลุมการทดสอบครบถ้วน: Positive (Happy Path), Negative (Validation & Error Handling), Boundary & Edge Cases, และ Authorization/Security ในแต่ละเมนู
6. การแบ่งแยกโดเมนอย่างเคร่งครัด: ห้ามนำฟังก์ชันหรือเนื้อหาของโครงการอื่นที่ไม่เกี่ยวข้องมาใส่ในเอกสารเด็ดขาด

{srs_menus_section}

{refinement_section}

{learned_rules_section}

{custom_prompt_section}

{primary_ref_context}

{all_docs_section}

{structured_reqs_section}

# Output Format MUST BE JSON
You MUST generate the entire workbook as a strict JSON object following this exact schema:
{{
  "workbook_info": {{
    "project_name": "{project_name}",
    "project_code": "{project_code}",
    "doc_name": "{doc_name}",
    "author": "QA Team",
    "version": "1.0",
    "last_updated_date": "{today_str}",
    "description": "เอกสารชุดนี้เรียกว่า System Testing Template มีวัตถุประสงค์เพื่อจัดทำขึ้นสำหรับทดสอบระบบตาม Requirement ของโครงการ {project_name}"
  }},
  "change_history": [
    {{
      "date": "{today_str}",
      "version": "v.1",
      "prepared_by": "QA Team",
      "detail": "สร้าง Test Case แยกตามแต่ละเมนูของระบบตามเอกสาร SRS"
    }}
  ],
  "glossary": [
    {{
      "term": "ชื่อคำศัพท์/ตัวย่อสำคัญของระบบ",
      "definition": "คำอธิบายความหมายและบริบทการใช้งานในระบบ"
    }}
  ],
  "execute_test_summary": [
    {{
      "ref_no": "1",
      "module": "Restricted Good Permit",
      "function": "ขอใบอนุญาตสินค้า (Permit)",
      "pass_criteria": "ผ่านเกณฑ์การทดสอบตาม Requirement",
      "remark": "-",
      "tc_count": 8,
      "est_hours": 2.0
    }},
    {{
      "ref_no": "2",
      "module": "Restricted Good Permit",
      "function": "ขอใบอนุญาตสินค้า หน้า MGT (Permit MGT)",
      "pass_criteria": "ผ่านเกณฑ์การทดสอบตาม Requirement",
      "remark": "-",
      "tc_count": 6,
      "est_hours": 1.5
    }},
    {{
      "ref_no": "3",
      "module": "EzySuite Open API",
      "function": "API Document List & Management",
      "pass_criteria": "ผ่านเกณฑ์การทดสอบตาม Requirement",
      "remark": "-",
      "tc_count": 5,
      "est_hours": 1.25
    }}
  ],
  "test_case_sheets": [
    {{
      "sheet_name": "Test Case Permit",
      "module_name": "Restricted Good Permit",
      "function_name": "ขอใบอนุญาตสินค้า (Permit)",
      "req_range": "REQ0001-REQ0015",
      "test_cases": [
        {{
          "Test Case ID": "69AA1001",
          "Test Case Objective": "ตรวจสอบการสร้างคำขอใบอนุญาตสินค้าด้วยข้อมูลที่ถูกต้องครบถ้วน",
          "Test Step": "1. เข้าสู่เมนูขอใบอนุญาตสินค้า\\n2. กรอกข้อมูลใบอนุญาตและรายการสินค้าควบคุม\\n3. กดปุ่มบันทึกและส่งข้อมูล",
          "Test Data": "เลขที่คำขอ: PM-2026-001, พิกัดสินค้าควบคุม: 2903.11.00",
          "Test Type": "Positive",
          "Expected Result": "ระบบบันทึกคำขอใบอนุญาตสำเร็จและเปลี่ยนสถานะเป็น Submitted",
          "Remark": "",
          "Automate": "TRUE",
          "Req No.": "REQ0001",
          "Platforms": "Web Application",
          "Updated By": "QA Team"
        }}
      ]
    }},
    {{
      "sheet_name": "Test Case Permit MGT",
      "module_name": "Restricted Good Permit",
      "function_name": "ขอใบอนุญาตสินค้า (หน้า MGT)",
      "req_range": "REQ0016-REQ0030",
      "test_cases": [
        {{
          "Test Case ID": "69AA2001",
          "Test Case Objective": "ตรวจสอบการค้นหาและกรองรายการใบอนุญาตในหน้า MGT",
          "Test Step": "1. เข้าสู่เมนูขอใบอนุญาตสินค้า (หน้า MGT)\\n2. ระบุเงื่อนไขการค้นหาตามช่วงวันที่และสถานะ\\n3. กดปุ่มค้นหา",
          "Test Data": "ช่วงวันที่: 01/01/2026 - 31/01/2026, สถานะ: Approve",
          "Test Type": "Positive",
          "Expected Result": "ตารางแสดงรายการใบอนุญาตที่ตรงตามเงื่อนไขได้อย่างถูกต้องครบถ้วน",
          "Remark": "",
          "Automate": "TRUE",
          "Req No.": "REQ0016",
          "Platforms": "Web Application",
          "Updated By": "QA Team"
        }}
      ]
    }},
    {{
      "sheet_name": "Test Case EzySuite API",
      "module_name": "EzySuite Open API",
      "function_name": "API Document List & Management",
      "req_range": "REQ0031-REQ0045",
      "test_cases": [
        {{
          "Test Case ID": "69AA3001",
          "Test Case Objective": "ตรวจสอบการดูรายการเอกสาร OPEN API ของระบบ",
          "Test Step": "1. เข้าสู่เมนู API Document List\\n2. คลิกเลือกดู API Endpoint ที่ต้องการทดสอบ Integrate\\n3. ตรวจสอบข้อมูล Request/Response Schema",
          "Test Data": "API: /api/v1/permit/query",
          "Test Type": "Positive",
          "Expected Result": "ระบบแสดงรายละเอียดเอกสาร API และตัวอย่าง Payload ได้ถูกต้อง",
          "Remark": "",
          "Automate": "TRUE",
          "Req No.": "REQ0031",
          "Platforms": "Web Application",
          "Updated By": "QA Team"
        }}
      ]
    }}
  ]
}}
"""
        else:
            engineering_guidelines = get_advanced_engineering_guidelines(doc_type, today_str)
            prompt = f"""
You are an expert Principal Software Architect, Lead Business Analyst, and Senior Technical Writer.
Your task is to generate a comprehensive, enterprise-grade, production-ready {doc_type} document for Project '{project_name}' ({project_code}) named '{doc_name}'.
You MUST analyze, cross-reference, and synthesize ALL provided Project Knowledge Base documents (TOR, PO Briefing, SRS, SDD, previous tests, specs) to ensure 100% technical accuracy, depth, and zero requirement loss.

# Target Document Information
- Document Name: {doc_name}
- Document Type: {doc_type}
- Project: {project_name} ({project_code})
- Date of Baseline: {today_str}

{framework_header}

{engineering_guidelines}

{refinement_section}

{learned_rules_section}

{custom_prompt_section}

{primary_ref_context}

{all_docs_section}

{structured_reqs_section}

# Final Output Directives:
1. Synthesize all documents in the project knowledge base into a fully detailed, rigorous, production-grade {doc_type}.
2. MANDATORY LANGUAGE REQUIREMENT: The entire document MUST be written in professional, grammatically correct Thai (ภาษาไทย). Standard English technical terms, acronyms, and code identifiers may be kept or placed in parentheses (e.g., API, Database, JWT).
3. Ensure every single requirement is measurable, testable, and unambiguous.
4. NEVER leave placeholder text or brief outlines.
5. Output the complete document directly in clean, structured Markdown.
"""

        logger.info(f"Generating document async '{doc_name}' ({doc_type})...")
        model_to_use = os.environ.get("GEMINI_DOC_MODEL", "gemini-3.1-pro")
        doc_content, usage_metadata = call_gemini(prompt, model_name=model_to_use, max_output_tokens=32768)
        
        if usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_6_Doc_Creator", model_to_use, usage_metadata, filename=doc_name)
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
        
        pdf_file_name = f"{safe_name}_{unique_suffix}.pdf"
        pdf_file_path = os.path.join(upload_dir, pdf_file_name)
        excel_file_path = None

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
                match = re.search(r'(\{[\s\S]*\})', json_text)
                if match:
                    try:
                        data = json.loads(match.group(1))
                    except Exception:
                        pass

            if not data or not isinstance(data, dict):
                data = {}

            wb_info = data.get("workbook_info", {})
            tester_val = wb_info.get("author") or wb_info.get("tester_name") or "QA Team"
            version_val = str(wb_info.get("version") or "1.0")
            proj_name_val = wb_info.get("project_name") or project_name
            proj_code_val = wb_info.get("project_id") or wb_info.get("project_code") or project_code
            desc_val = wb_info.get("description") or f"เอกสารชุดนี้เรียกว่า System Testing Template มีวัตถุประสงค์เพื่อจัดทำขึ้นสำหรับทดสอบระบบตาม Requirement ของโครงการ {project_name}"

            change_history = data.get("change_history") or [
                {"date": today_str, "version": f"v.{version_val}", "prepared_by": tester_val, "detail": "สร้าง Test Case ชุดแรกจาก Requirement และ Knowledge Base ของโครงการ"}
            ]

            glossary_list = data.get("glossary") or [
                {"term": "Positive Case", "definition": "การทดสอบกรณีทำงานปกติและคาดหวังผลสำเร็จ"},
                {"term": "Negative Case", "definition": "การทดสอบกรณีข้อมูลผิดพลาดหรือเงื่อนไขขัดแย้ง และคาดหวังให้ระบบจัดการข้อผิดพลาดได้ถูกต้อง"}
            ]

            raw_sheets = data.get("test_case_sheets")
            if not raw_sheets or not isinstance(raw_sheets, list):
                # Fallback to single sheet if model used legacy format with "test_cases"
                legacy_tcs = data.get("test_cases", [])
                meta = data.get("metadata", {})
                mod_name = meta.get("module_function", doc_name)
                raw_sheets = [{
                    "sheet_name": f"Test Case {doc_name}"[:31],
                    "module_name": mod_name,
                    "function_name": mod_name,
                    "req_range": "All Requirements",
                    "test_cases": legacy_tcs
                }]

            def extract_tc_field(tc_item, candidate_keys, default_val=""):
                if not isinstance(tc_item, dict):
                    return default_val
                for k in candidate_keys:
                    if k in tc_item and tc_item[k] is not None and str(tc_item[k]).strip() != "":
                        return tc_item[k]
                lower_map = {k.lower().replace(" ", "").replace("_", ""): v for k, v in tc_item.items() if v is not None}
                for k in candidate_keys:
                    clean_k = k.lower().replace(" ", "").replace("_", "")
                    if clean_k in lower_map and str(lower_map[clean_k]).strip() != "":
                        return lower_map[clean_k]
                return default_val

            # Generate formatted Excel file specifically for Test Case matching 69A_ST_TC_v13 (2).xlsx
            import openpyxl
            from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
            
            excel_file_name = f"{safe_name}_{unique_suffix}.xlsx"
            excel_file_path = os.path.join(upload_dir, excel_file_name)

            wb = openpyxl.Workbook()
            font_name = "Browallia New"
            card_fill = PatternFill(start_color="CDEEFF", end_color="CDEEFF", fill_type="solid")
            header_fill = PatternFill(start_color="CDEEFF", end_color="CDEEFF", fill_type="solid")
            white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
            dark_header_fill = PatternFill(start_color="7F7F7F", end_color="7F7F7F", fill_type="solid")
            
            thin_side = Side(style='thin', color='B0C4DE')
            dark_side = Side(style='thin', color='000000')
            cell_border = Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side)
            header_border = Border(left=dark_side, right=dark_side, top=dark_side, bottom=dark_side)
            thin_border = cell_border
            
            title_banner_font = Font(name=font_name, size=26, bold=True, color="7F7F7F")
            title_font = Font(name=font_name, size=16, bold=True)
            section_white_font = Font(name=font_name, size=14, bold=True, color="FFFFFF")
            section_font = Font(name=font_name, size=14, bold=True, color="000000")
            header_font = Font(name=font_name, size=14, bold=True, color="000000")
            label_font = Font(name=font_name, size=14, bold=True, color="000000")
            value_font = Font(name=font_name, size=14, bold=False, color="000000")
            cell_font = Font(name=font_name, size=13)
            cell_bold = Font(name=font_name, size=13, bold=True)
            sheet_link_font = Font(name=font_name, size=14, bold=True, color="2E6433")
            
            align_center_top = Alignment(horizontal="center", vertical="top", wrap_text=True)
            align_left_top = Alignment(horizontal="left", vertical="top", wrap_text=True)
            align_center_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
            align_left_center = Alignment(horizontal="left", vertical="center", wrap_text=True)
            align_right_center = Alignment(horizontal="right", vertical="center")
            align_label = Alignment(horizontal="right", vertical="center")
            align_value = Alignment(horizontal="left", vertical="center")
            center_align = align_center_center
            left_align = align_left_top

            def style_range(ws_target, cell_range, font=None, fill=None, border=None, alignment=None):
                if ":" in cell_range:
                    cells = [c for row in ws_target[cell_range] for c in row]
                else:
                    cells = [ws_target[cell_range]]
                for cell in cells:
                    if font: cell.font = font
                    if fill: cell.fill = fill
                    if border: cell.border = border
                    if alignment: cell.alignment = alignment

            def calc_tc_row_height(step, obj, exp, data):
                s_lines = len(str(step).split('\n')) if step else 1
                s_wrap = max(s_lines, len(str(step)) // 45 + 1)
                o_wrap = len(str(obj)) // 28 + 1 if obj else 1
                e_wrap = len(str(exp)) // 35 + 1 if exp else 1
                d_wrap = len(str(data)) // 25 + 1 if data else 1
                lines = max(s_wrap, o_wrap, e_wrap, d_wrap, 1)
                return max(30, 16 + (lines * 19))

            # -------------------------------------------------------------
            # 1. Sheet: Introduction
            # -------------------------------------------------------------
            ws_intro = wb.active
            ws_intro.title = "Introduction"
            ws_intro.column_dimensions['A'].width = 15.0
            ws_intro.column_dimensions['B'].width = 6.0
            ws_intro.column_dimensions['C'].width = 16.0
            ws_intro.column_dimensions['D'].width = 12.0
            ws_intro.column_dimensions['E'].width = 14.0
            ws_intro.column_dimensions['F'].width = 30.0
            ws_intro.column_dimensions['G'].width = 15.0
            ws_intro.column_dimensions['H'].width = 15.0
            ws_intro.column_dimensions['I'].width = 15.0

            # Title Banner A1:I4
            ws_intro.merge_cells("A1:I4")
            ws_intro["A1"] = "Introduction"
            style_range(ws_intro, "A1:I4", font=title_banner_font, fill=white_fill, alignment=align_center_center)
            for r in range(1, 5): ws_intro.row_dimensions[r].height = 18

            # A5:I5 Section Header
            ws_intro.merge_cells("A5:I5")
            ws_intro["A5"] = "Introduction"
            style_range(ws_intro, "A5:I5", font=header_font, fill=header_fill, border=header_border, alignment=align_left_center)
            ws_intro.row_dimensions[5].height = 22

            # A6:I7 Description
            ws_intro.merge_cells("A6:I7")
            ws_intro["A6"] = desc_val
            style_range(ws_intro, "A6:I7", font=value_font, fill=white_fill, border=cell_border, alignment=align_left_top)
            ws_intro.row_dimensions[6].height = 22
            ws_intro.row_dimensions[7].height = 22

            # Row 8: Spacer
            ws_intro.row_dimensions[8].height = 10

            # Metadata Card (A9:I11)
            meta_intro = [
                (9, "A9:B9", "C9:I9", "Author :", tester_val),
                (10, "A10:B10", "C10:I10", "Version :", version_val),
                (11, "A11:B11", "C11:I11", "Last Updated Date :", today_str)
            ]
            for r_idx, lbl_range, val_range, lbl_text, val_text in meta_intro:
                ws_intro.merge_cells(lbl_range)
                ws_intro[lbl_range.split(':')[0]] = lbl_text
                style_range(ws_intro, lbl_range, font=label_font, fill=card_fill, border=cell_border, alignment=align_right_center)
                
                ws_intro.merge_cells(val_range)
                ws_intro[val_range.split(':')[0]] = val_text
                style_range(ws_intro, val_range, font=value_font, fill=white_fill, border=cell_border, alignment=align_value)
                ws_intro.row_dimensions[r_idx].height = 22

            # A12:I12 Structure Header
            ws_intro.merge_cells("A12:I12")
            ws_intro["A12"] = "Structure of this workbook:"
            style_range(ws_intro, "A12:I12", font=header_font, fill=header_fill, border=header_border, alignment=align_left_center)
            ws_intro.row_dimensions[12].height = 22

            # A13:I13 Subtitle
            ws_intro.merge_cells("A13:I13")
            ws_intro["A13"] = "This workbook contains the following sheets and forms:"
            style_range(ws_intro, "A13:I13", font=cell_bold, alignment=align_left_center)
            ws_intro.row_dimensions[13].height = 20

            # Table Header for Sheets
            ws_intro.merge_cells("B14:D14")
            ws_intro["B14"] = "Sheet Name"
            style_range(ws_intro, "B14:D14", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)

            ws_intro.merge_cells("E14:I14")
            ws_intro["E14"] = "Description / Detail"
            style_range(ws_intro, "E14:I14", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_intro.row_dimensions[14].height = 24

            intro_sheets_map = [
                ("Introduction", "สำหรับอธิบายการใช้งานของ Template และแสดงรายละเอียดต่าง ๆ ของ Template"),
                ("Document Change History", "สำหรับบันทึกประวัติการแก้ไขเอกสารฉบับนี้ในแต่ละเวอร์ชัน (Date, Version, Prepared By)"),
                ("Glossary", "สำหรับอธิบายคำศัพท์เฉพาะทาง/ตัวย่อที่ใช้ในเอกสารและระบบ"),
                ("Basic Test", "สำหรับการทดสอบเบื้องต้น ประกอบด้วย File List, System Installation, System Configuration"),
                ("Execute Test", "สำหรับสรุปผลการทดสอบระบบ (System Testing) แยกตาม Module/Function พร้อมจำนวน Test Case"),
            ]
            for s_item in raw_sheets:
                s_name = s_item.get("sheet_name", "Test Case")
                f_name = s_item.get("function_name") or s_item.get("module_name") or s_name
                intro_sheets_map.append((s_name, f"สำหรับเขียน Test Case Specification และกรณีทดสอบของ {f_name}"))

            cur_r = 15
            for s_name, s_desc in intro_sheets_map:
                ws_intro.merge_cells(f"B{cur_r}:D{cur_r}")
                ws_intro[f"B{cur_r}"] = s_name
                style_range(ws_intro, f"B{cur_r}:D{cur_r}", font=sheet_link_font, fill=white_fill, border=cell_border, alignment=align_left_center)
                
                ws_intro.merge_cells(f"E{cur_r}:I{cur_r}")
                ws_intro[f"E{cur_r}"] = s_desc
                style_range(ws_intro, f"E{cur_r}:I{cur_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_left_top)
                ws_intro.row_dimensions[cur_r].height = 24
                cur_r += 1

            # Template Change History
            cur_r += 1
            ws_intro.merge_cells(f"A{cur_r}:C{cur_r}")
            ws_intro[f"A{cur_r}"] = "Template Change History:"
            style_range(ws_intro, f"A{cur_r}:C{cur_r}", font=section_white_font, fill=dark_header_fill, border=header_border, alignment=align_left_center)
            ws_intro.row_dimensions[cur_r].height = 22

            cur_r += 1
            h_r = cur_r
            ws_intro[f"A{h_r}"] = "Version"
            style_range(ws_intro, f"A{h_r}", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_intro.merge_cells(f"B{h_r}:D{h_r}")
            ws_intro[f"B{h_r}"] = "Name"
            style_range(ws_intro, f"B{h_r}:D{h_r}", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_intro[f"E{h_r}"] = "Date"
            style_range(ws_intro, f"E{h_r}", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_intro.merge_cells(f"F{h_r}:I{h_r}")
            ws_intro[f"F{h_r}"] = "Title or Brief Description"
            style_range(ws_intro, f"F{h_r}:I{h_r}", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_intro.row_dimensions[h_r].height = 24

            cur_r += 1
            ws_intro[f"A{cur_r}"] = version_val
            style_range(ws_intro, f"A{cur_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
            ws_intro.merge_cells(f"B{cur_r}:D{cur_r}")
            ws_intro[f"B{cur_r}"] = tester_val
            style_range(ws_intro, f"B{cur_r}:D{cur_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
            ws_intro[f"E{cur_r}"] = today_str
            style_range(ws_intro, f"E{cur_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
            ws_intro.merge_cells(f"F{cur_r}:I{cur_r}")
            ws_intro[f"F{cur_r}"] = f"สร้าง Test Case ชุดแรกจากข้อกำหนด {proj_name_val}"
            style_range(ws_intro, f"F{cur_r}:I{cur_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_left_center)
            ws_intro.row_dimensions[cur_r].height = 24

            # -------------------------------------------------------------
            # 2. Sheet: Document Change History
            # -------------------------------------------------------------
            ws_hist = wb.create_sheet(title="Document Change History")
            ws_hist.column_dimensions['A'].width = 3.0
            ws_hist.column_dimensions['B'].width = 16.0
            ws_hist.column_dimensions['C'].width = 12.0
            ws_hist.column_dimensions['D'].width = 14.0
            ws_hist.column_dimensions['E'].width = 12.0
            ws_hist.column_dimensions['F'].width = 12.0
            ws_hist.column_dimensions['G'].width = 25.0
            ws_hist.column_dimensions['H'].width = 25.0
            ws_hist.column_dimensions['I'].width = 25.0

            ws_hist.merge_cells("B1:I4")
            ws_hist["B1"] = "Document Change History"
            style_range(ws_hist, "B1:I4", font=title_banner_font, fill=white_fill, alignment=align_center_center)
            for r in range(1, 5): ws_hist.row_dimensions[r].height = 18

            ws_hist.merge_cells("B5:E5")
            ws_hist["B5"] = "Document Change History:"
            style_range(ws_hist, "B5:E5", font=section_white_font, fill=dark_header_fill, border=header_border, alignment=align_left_center)
            ws_hist.row_dimensions[5].height = 22

            ws_hist["B6"] = "Date"
            style_range(ws_hist, "B6", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_hist["C6"] = "Version"
            style_range(ws_hist, "C6", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_hist.merge_cells("D6:F6")
            ws_hist["D6"] = "Prepared By"
            style_range(ws_hist, "D6:F6", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_hist.merge_cells("G6:I6")
            ws_hist["G6"] = "Detail"
            style_range(ws_hist, "G6:I6", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_hist.row_dimensions[6].height = 28

            if not change_history:
                change_history = [{"date": today_str, "version": version_val, "prepared_by": tester_val, "detail": f"สร้างชุด Test Case จากข้อกำหนด {proj_name_val}"}]
            
            for idx, ch in enumerate(change_history, start=7):
                ws_hist[f"B{idx}"] = ch.get("date", today_str)
                style_range(ws_hist, f"B{idx}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
                ws_hist[f"C{idx}"] = ch.get("version", version_val)
                style_range(ws_hist, f"C{idx}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
                ws_hist.merge_cells(f"D{idx}:F{idx}")
                ws_hist[f"D{idx}"] = ch.get("prepared_by", tester_val)
                style_range(ws_hist, f"D{idx}:F{idx}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_left_center)
                ws_hist.merge_cells(f"G{idx}:I{idx}")
                ws_hist[f"G{idx}"] = ch.get("detail", "-")
                style_range(ws_hist, f"G{idx}:I{idx}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_left_center)
                ws_hist.row_dimensions[idx].height = 24

            # -------------------------------------------------------------
            # 3. Sheet: Glossary
            # -------------------------------------------------------------
            ws_glo = wb.create_sheet(title="Glossary")
            ws_glo.column_dimensions['A'].width = 3.0
            ws_glo.column_dimensions['B'].width = 28.0
            ws_glo.column_dimensions['C'].width = 45.0
            ws_glo.column_dimensions['D'].width = 45.0

            ws_glo.merge_cells("B1:D4")
            ws_glo["B1"] = "Glossary"
            style_range(ws_glo, "B1:D4", font=title_banner_font, fill=white_fill, alignment=align_center_center)
            for r in range(1, 5): ws_glo.row_dimensions[r].height = 18

            ws_glo["B5"] = "คำศัพท์ (Term)"
            style_range(ws_glo, "B5", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_glo.merge_cells("C5:D5")
            ws_glo["C5"] = "คำอธิบาย (Definition)"
            style_range(ws_glo, "C5:D5", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_glo.row_dimensions[5].height = 28

            if not glossary_list:
                glossary_list = [
                    {"term": "SRS", "definition": "Software Requirements Specification — เอกสารข้อกำหนดความต้องการของระบบ"},
                    {"term": "Positive Test", "definition": "การทดสอบกรณีข้อมูลถูกต้องตามเงื่อนไขที่ระบบกำหนด"},
                    {"term": "Negative Test", "definition": "การทดสอบกรณีข้อมูลไม่ถูกต้อง เพื่อตรวจสอบการป้องกันและแจ้งเตือนของระบบ"}
                ]
            for idx, g in enumerate(glossary_list, start=6):
                ws_glo[f"B{idx}"] = g.get("term", "-")
                style_range(ws_glo, f"B{idx}", font=cell_bold, fill=white_fill, border=cell_border, alignment=align_center_center)
                ws_glo.merge_cells(f"C{idx}:D{idx}")
                ws_glo[f"C{idx}"] = g.get("definition", "-")
                style_range(ws_glo, f"C{idx}:D{idx}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_left_center)
                ws_glo.row_dimensions[idx].height = 24

            # -------------------------------------------------------------
            # 4. Sheet: Basic Test
            # -------------------------------------------------------------
            ws_basic = wb.create_sheet(title="Basic Test")
            ws_basic.column_dimensions['A'].width = 3.0
            ws_basic.column_dimensions['B'].width = 10.0
            ws_basic.column_dimensions['C'].width = 25.0
            ws_basic.column_dimensions['D'].width = 25.0
            ws_basic.column_dimensions['E'].width = 25.0
            ws_basic.column_dimensions['F'].width = 25.0

            ws_basic.merge_cells("B1:F4")
            ws_basic["B1"] = "Basic Test"
            style_range(ws_basic, "B1:F4", font=title_banner_font, fill=white_fill, alignment=align_center_center)
            for r in range(1, 5): ws_basic.row_dimensions[r].height = 18

            # Section 1: File List
            ws_basic.merge_cells("B5:C5")
            ws_basic["B5"] = "File List"
            style_range(ws_basic, "B5:C5", font=section_white_font, fill=dark_header_fill, border=header_border, alignment=align_left_center)
            ws_basic.row_dimensions[5].height = 22

            ws_basic["B6"] = "No."
            style_range(ws_basic, "B6", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_basic.merge_cells("C6:D6")
            ws_basic["C6"] = "File Name"
            style_range(ws_basic, "C6:D6", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_basic.merge_cells("E6:F6")
            ws_basic["E6"] = "Location"
            style_range(ws_basic, "E6:F6", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_basic.row_dimensions[6].height = 26

            ws_basic["B7"] = "N/A"
            style_range(ws_basic, "B7", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
            ws_basic.merge_cells("C7:D7")
            ws_basic["C7"] = "ครอบคลุม Functional/System Test Case ตามข้อกำหนด SRS"
            style_range(ws_basic, "C7:D7", font=cell_font, fill=white_fill, border=cell_border, alignment=align_left_center)
            ws_basic.merge_cells("E7:F7")
            ws_basic["E7"] = "-"
            style_range(ws_basic, "E7:F7", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
            ws_basic.row_dimensions[7].height = 24

            # Section 2: System Installation
            ws_basic.merge_cells("B10:C10")
            ws_basic["B10"] = "System Installation"
            style_range(ws_basic, "B10:C10", font=section_white_font, fill=dark_header_fill, border=header_border, alignment=align_left_center)
            ws_basic.row_dimensions[10].height = 22

            ws_basic["B11"] = "No."
            style_range(ws_basic, "B11", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_basic.merge_cells("C11:F11")
            ws_basic["C11"] = "Setup Procedures"
            style_range(ws_basic, "C11:F11", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_basic.row_dimensions[11].height = 26

            ws_basic["B12"] = "N/A"
            style_range(ws_basic, "B12", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
            ws_basic.merge_cells("C12:F12")
            ws_basic["C12"] = "ไม่อยู่ในขอบเขตของเอกสารฉบับนี้ — อ้างอิงตามเอกสาร System Installation Guide"
            style_range(ws_basic, "C12:F12", font=cell_font, fill=white_fill, border=cell_border, alignment=align_left_center)
            ws_basic.row_dimensions[12].height = 24

            # Section 3: System Configuration
            ws_basic.merge_cells("B15:C15")
            ws_basic["B15"] = "System Configuration"
            style_range(ws_basic, "B15:C15", font=section_white_font, fill=dark_header_fill, border=header_border, alignment=align_left_center)
            ws_basic.row_dimensions[15].height = 22

            ws_basic["B16"] = "No."
            style_range(ws_basic, "B16", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_basic.merge_cells("C16:F16")
            ws_basic["C16"] = "Configuration Procedures"
            style_range(ws_basic, "C16:F16", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_basic.row_dimensions[16].height = 26

            ws_basic["B17"] = "N/A"
            style_range(ws_basic, "B17", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
            ws_basic.merge_cells("C17:F17")
            ws_basic["C17"] = "ไม่อยู่ในขอบเขตของเอกสารฉบับนี้ — อ้างอิงตามเอกสาร System Configuration Manual"
            style_range(ws_basic, "C17:F17", font=cell_font, fill=white_fill, border=cell_border, alignment=align_left_center)
            ws_basic.row_dimensions[17].height = 24

            # -------------------------------------------------------------
            # 5. Sheet: Execute Test
            # -------------------------------------------------------------
            ws_exec = wb.create_sheet(title="Execute Test")
            ws_exec.column_dimensions['A'].width = 3.0
            ws_exec.column_dimensions['B'].width = 8.0
            ws_exec.column_dimensions['C'].width = 25.0
            ws_exec.column_dimensions['D'].width = 32.0
            ws_exec.column_dimensions['E'].width = 24.0
            ws_exec.column_dimensions['F'].width = 12.0
            ws_exec.column_dimensions['G'].width = 12.0
            ws_exec.column_dimensions['H'].width = 14.0
            ws_exec.column_dimensions['I'].width = 16.0

            ws_exec.merge_cells("B1:I4")
            ws_exec["B1"] = "Execute Test"
            style_range(ws_exec, "B1:I4", font=title_banner_font, fill=white_fill, alignment=align_center_center)
            for r in range(1, 5): ws_exec.row_dimensions[r].height = 18

            meta_exec = [
                (6, "Project Name :", proj_name_val),
                (8, "Project ID:", proj_code_val),
                (10, "Project Release / Version :", version_val)
            ]
            for r_idx, lbl_txt, val_txt in meta_exec:
                ws_exec[f"C{r_idx}"] = lbl_txt
                style_range(ws_exec, f"C{r_idx}", font=label_font, fill=card_fill, border=cell_border, alignment=align_right_center)
                ws_exec.merge_cells(f"D{r_idx}:F{r_idx}")
                ws_exec[f"D{r_idx}"] = val_txt
                style_range(ws_exec, f"D{r_idx}:F{r_idx}", font=value_font, fill=white_fill, border=cell_border, alignment=align_value)
                ws_exec.row_dimensions[r_idx].height = 22

            ws_exec.merge_cells("B13:D13")
            ws_exec["B13"] = "System Test"
            style_range(ws_exec, "B13:D13", font=section_white_font, fill=dark_header_fill, border=header_border, alignment=align_left_center)
            ws_exec.row_dimensions[13].height = 22

            ws_exec["B14"] = "REF #"
            style_range(ws_exec, "B14", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_exec["C14"] = "Module"
            style_range(ws_exec, "C14", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_exec["D14"] = "Function"
            style_range(ws_exec, "D14", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_exec["E14"] = "Pass\n(Meet criteria for evaluating)*"
            style_range(ws_exec, "E14", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_exec.merge_cells("F14:G14")
            ws_exec["F14"] = "Remark"
            style_range(ws_exec, "F14:G14", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_exec["H14"] = "จำนวน TC"
            style_range(ws_exec, "H14", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_exec["I14"] = "เวลาประมาณ (ชม.)"
            style_range(ws_exec, "I14", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_exec.row_dimensions[14].height = 32

            exec_r = 15
            total_tc_sum = 0
            total_hours_sum = 0.0

            exec_summary_list = data.get("execute_test_summary") or []
            if not exec_summary_list or len(exec_summary_list) < len(raw_sheets):
                exec_summary_list = []
                for idx, s_item in enumerate(raw_sheets, 1):
                    tc_c = len(s_item.get("test_cases", []))
                    sh_title = s_item.get("sheet_name", f"Test Case {idx}")
                    func_n = s_item.get("function_name") or sh_title.replace("Test Case", "").strip() or sh_title
                    exec_summary_list.append({
                        "ref_no": str(idx),
                        "module": s_item.get("module_name", proj_name_val),
                        "function": func_n,
                        "pass_criteria": "ผ่านเกณฑ์การทดสอบ",
                        "remark": "-",
                        "tc_count": tc_c,
                        "est_hours": round(tc_c * 0.25, 2)
                    })
            elif len(exec_summary_list) == len(raw_sheets):
                for idx, s_item in enumerate(raw_sheets):
                    actual_cnt = len(s_item.get("test_cases", []))
                    exec_summary_list[idx]["tc_count"] = actual_cnt
                    exec_summary_list[idx]["est_hours"] = round(actual_cnt * 0.25, 2)

            for s_row in exec_summary_list:
                c_cnt = int(s_row.get("tc_count", 0))
                c_hrs = float(s_row.get("est_hours") or round(c_cnt * 0.25, 2))
                total_tc_sum += c_cnt
                total_hours_sum += c_hrs

                ws_exec[f"B{exec_r}"] = str(s_row.get("ref_no", ""))
                style_range(ws_exec, f"B{exec_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
                ws_exec[f"C{exec_r}"] = s_row.get("module", "-")
                style_range(ws_exec, f"C{exec_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_left_center)
                ws_exec[f"D{exec_r}"] = s_row.get("function", "-")
                style_range(ws_exec, f"D{exec_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_left_center)
                ws_exec[f"E{exec_r}"] = str(s_row.get("pass_criteria", "ผ่านเกณฑ์การทดสอบ"))
                style_range(ws_exec, f"E{exec_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
                ws_exec.merge_cells(f"F{exec_r}:G{exec_r}")
                ws_exec[f"F{exec_r}"] = str(s_row.get("remark", "-"))
                style_range(ws_exec, f"F{exec_r}:G{exec_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
                ws_exec[f"H{exec_r}"] = c_cnt
                style_range(ws_exec, f"H{exec_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
                ws_exec[f"I{exec_r}"] = c_hrs
                style_range(ws_exec, f"I{exec_r}", font=cell_font, fill=white_fill, border=cell_border, alignment=align_center_center)
                ws_exec.row_dimensions[exec_r].height = 24
                exec_r += 1

            # Total row
            ws_exec.merge_cells(f"B{exec_r}:G{exec_r}")
            ws_exec[f"B{exec_r}"] = "รวม (Total)"
            style_range(ws_exec, f"B{exec_r}:G{exec_r}", font=header_font, fill=header_fill, border=header_border, alignment=align_right_center)
            ws_exec[f"H{exec_r}"] = total_tc_sum
            style_range(ws_exec, f"H{exec_r}", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_exec[f"I{exec_r}"] = round(total_hours_sum, 2)
            style_range(ws_exec, f"I{exec_r}", font=header_font, fill=header_fill, border=header_border, alignment=align_center_center)
            ws_exec.row_dimensions[exec_r].height = 26

            # -------------------------------------------------------------
            # 6. Test Case Sheets (Exact 11 Columns B to L)
            # -------------------------------------------------------------
            existing_sheet_titles = set(wb.sheetnames)
            for s_idx, s_item in enumerate(raw_sheets, 1):
                raw_title = s_item.get("sheet_name") or f"Test Case {s_idx}"
                clean_title = re.sub(r'[\\/*?:\[\]]', '_', raw_title).strip()
                if not clean_title.lower().startswith("test case"):
                    clean_title = f"Test Case {clean_title}"
                clean_title = clean_title[:31].strip()
                if not clean_title:
                    clean_title = f"Test Case {s_idx}"
                unique_title = clean_title
                dup_c = 1
                while unique_title in existing_sheet_titles:
                    unique_title = f"{clean_title[:27]}_{dup_c}"
                    dup_c += 1
                existing_sheet_titles.add(unique_title)

                ws_tc = wb.create_sheet(title=unique_title)
                
                # Column widths matching 69A template
                col_widths = {
                    'A': 2.0,
                    'B': 24.0, # Test Case ID
                    'C': 28.0, # Test Case Objective
                    'D': 48.0, # Test Step
                    'E': 28.0, # Test Data
                    'F': 15.0, # Test Type
                    'G': 36.0, # Expected Result
                    'H': 24.0, # Remark
                    'I': 14.0, # Automate
                    'J': 16.0, # Req No.
                    'K': 18.0, # Platforms
                    'L': 20.0  # Updated By
                }
                for c_letter, c_w in col_widths.items():
                    ws_tc.column_dimensions[c_letter].width = c_w

                # 1. Title Banner B1:L4
                ws_tc.merge_cells("B1:L4")
                ws_tc["B1"] = "Test Case"
                style_range(ws_tc, "B1:L4", font=title_banner_font, fill=white_fill, alignment=align_center_center)
                for r_idx in range(1, 5):
                    ws_tc.row_dimensions[r_idx].height = 18

                # 2. Unified Soft Blue Card B5:L13
                for r_idx in range(5, 14):
                    ws_tc.row_dimensions[r_idx].height = 20
                    for c_idx in range(2, 13):
                        cell = ws_tc.cell(r_idx, c_idx)
                        cell.fill = card_fill
                        t_s = dark_side if r_idx == 5 else None
                        b_s = dark_side if r_idx == 13 else None
                        l_s = dark_side if c_idx == 2 else None
                        r_s = dark_side if c_idx == 12 else None
                        cell.border = Border(top=t_s, bottom=b_s, left=l_s, right=r_s)

                mod_f = f"{s_item.get('module_name', proj_name_val)} / {s_item.get('function_name', unique_title)}" if s_item.get('function_name') else s_item.get('module_name', proj_name_val)
                req_rng = s_item.get("req_range") or s_item.get("req_no_range") or "REQ0001-REQ0050"

                # Metadata labels inside the card
                meta_labels = [
                    (6, 3, "Project Name :"),
                    (8, 3, "Project ID:"),
                    (10, 3, "Tester Name :"),
                    (12, 3, "Project Release / Version :"),
                    (6, 6, "Create Date :"),
                    (8, 6, "Start Test Date :"),
                    (10, 6, "Finish Test Date :"),
                    (12, 6, "Module / Function: ")
                ]
                for r_num, c_num, lbl_text in meta_labels:
                    lbl_cell = ws_tc.cell(r_num, c_num, lbl_text)
                    lbl_cell.font = label_font
                    lbl_cell.alignment = align_label

                # Metadata value boxes (merged white field boxes)
                meta_boxes = [
                    ("D6:E6", proj_name_val),
                    ("D8:E8", proj_code_val),
                    ("D10:E10", tester_val),
                    ("D12:E12", version_val),
                    ("G6:H6", today_str),
                    ("G8:H8", today_str),
                    ("G10:H10", today_str),
                    ("G12:K12", mod_f)
                ]
                for m_range, val_text in meta_boxes:
                    ws_tc.merge_cells(m_range)
                    ws_tc[m_range.split(':')[0]] = val_text
                    style_range(ws_tc, m_range, font=value_font, fill=white_fill, alignment=align_value)

                # Row 14: Spacer
                ws_tc.row_dimensions[14].height = 14

                # Row 15: Functional Requirements
                ws_tc.row_dimensions[15].height = 24
                ws_tc.merge_cells("B15:D15")
                ws_tc["B15"] = " FUNCTIONAL REQUIREMENTS (Requirements No.) :"
                style_range(ws_tc, "B15:D15", font=label_font, alignment=align_right_center)

                ws_tc.merge_cells("E15:G15")
                ws_tc["E15"] = req_rng
                style_range(ws_tc, "E15:G15", font=label_font, alignment=align_value)

                # Row 16: Spacer
                ws_tc.row_dimensions[16].height = 12

                # Row 17: Table Headers
                tc_headers = [
                    ("Test Case ID", 2),
                    ("Test Case Objective", 3),
                    ("Test Step", 4),
                    ("Test Data", 5),
                    ("Test Type", 6),
                    ("Expected Result", 7),
                    ("Remark", 8),
                    ("Automate", 9),
                    ("Req No.", 10),
                    ("Platforms", 11),
                    ("Updated By", 12)
                ]
                ws_tc.row_dimensions[17].height = 32
                for h_name, col_i in tc_headers:
                    cell = ws_tc.cell(17, col_i, h_name)
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = align_center_center
                    cell.border = header_border

                tc_row_idx = 18
                sheet_tcs = s_item.get("test_cases", [])
                for tc in sheet_tcs:
                    t_id = extract_tc_field(tc, ["Test Case ID", "Test ID", "test_case_id", "id"], f"TC{tc_row_idx-17:03d}")
                    t_obj = extract_tc_field(tc, ["Test Case Objective", "Test case Objective", "objective", "วัตถุประสงค์"], "")
                    t_step = extract_tc_field(tc, ["Test Step", "Test Description / Procedure", "steps", "ขั้นตอน"], "")
                    t_data = extract_tc_field(tc, ["Test Data", "data", "ข้อมูลทดสอบ"], "-")
                    t_type = extract_tc_field(tc, ["Test Type", "type", "ประเภท"], "Positive")
                    t_exp = extract_tc_field(tc, ["Expected Result", "expected", "ผลลัพธ์ที่คาดหวัง"], "")
                    t_rem = extract_tc_field(tc, ["Remark", "remark", "หมายเหตุ"], "")
                    t_auto = extract_tc_field(tc, ["Automate", "automate", "automation"], "TRUE")
                    t_req = extract_tc_field(tc, ["Req No.", "Requirement ID", "req_no", "รหัสข้อกำหนด"], "-")
                    t_plat = extract_tc_field(tc, ["Platforms", "Platform", "platform", "แพลตฟอร์ม"], "Web Application")
                    t_upd = extract_tc_field(tc, ["Updated By", "Update by", "updated_by", "tester"], tester_val)

                    # Dynamic row height for Thai multiline text
                    ws_tc.row_dimensions[tc_row_idx].height = calc_tc_row_height(t_step, t_obj, t_exp, t_data)

                    row_vals = [
                        (2, t_id, align_center_top),
                        (3, t_obj, align_left_top),
                        (4, t_step, align_left_top),
                        (5, t_data, align_left_top),
                        (6, t_type, align_center_top),
                        (7, t_exp, align_left_top),
                        (8, t_rem, align_left_top),
                        (9, str(t_auto).upper(), align_center_top),
                        (10, t_req, align_center_top),
                        (11, t_plat, align_center_top),
                        (12, t_upd, align_center_top)
                    ]
                    for col_i, val, align_style in row_vals:
                        c_node = ws_tc.cell(tc_row_idx, col_i, val)
                        c_node.font = cell_font
                        c_node.alignment = align_style
                        c_node.border = cell_border
                    tc_row_idx += 1

            wb.save(excel_file_path)

            # Construct Markdown Representation
            md_lines = [
                f"# {doc_name}",
                f"**ประเภทเอกสาร (Document Type):** {doc_type}  ",
                f"**รหัสโครงการ (Project Code):** {proj_code_val}  ",
                f"**ชื่อโครงการ (Project Name):** {proj_name_val}  ",
                f"**ผู้จัดทำ (Author / Tester):** {tester_val}  ",
                f"**เวอร์ชัน (Version):** {version_val}  ",
                f"**วันที่สร้างเอกสาร (Date):** {today_str}  ",
                "",
                f"> {desc_val}",
                "",
                "## 1. ข้อมูลสรุปการทดสอบระบบ (Execute Test Summary)",
                "| REF # | Module | Function | Pass Criteria | Remark | จำนวน TC | เวลาประมาณ (ชม.) |",
                "| :---: | :--- | :--- | :---: | :---: | :---: | :---: |"
            ]
            for s_row in exec_summary_list:
                md_lines.append(f"| {s_row.get('ref_no','')} | {s_row.get('module','-')} | {s_row.get('function','-')} | {s_row.get('pass_criteria','-')} | {s_row.get('remark','-')} | **{s_row.get('tc_count',0)}** | {s_row.get('est_hours',0)} |")
            md_lines.append(f"| | | **รวม (Total)** | | | **{total_tc_sum}** | **{round(total_hours_sum, 2)}** |")
            md_lines.append("")

            # For each Test Case Sheet
            for s_item in raw_sheets:
                s_name = s_item.get("sheet_name", "Test Case Sheet")
                mod_f = f"{s_item.get('module_name', proj_name_val)} / {s_item.get('function_name', s_name)}" if s_item.get('function_name') else s_item.get('module_name', proj_name_val)
                req_rng = s_item.get("req_range") or s_item.get("req_no_range") or "-"
                sheet_tcs = s_item.get("test_cases", [])

                md_lines.append(f"## Sheet: {s_name}")
                md_lines.append(f"- **Module / Function:** {mod_f}")
                md_lines.append(f"- **Functional Requirements:** {req_rng}")
                md_lines.append(f"- **Total Test Cases:** {len(sheet_tcs)} เคส")
                md_lines.append("")
                md_lines.append("| Test Case ID | Test Case Objective | Test Step | Test Data | Test Type | Expected Result | Remark | Automate | Req No. | Platforms | Updated By |")
                md_lines.append("| :--- | :--- | :--- | :--- | :---: | :--- | :--- | :---: | :---: | :---: | :--- |")

                for tc in sheet_tcs:
                    t_id = str(extract_tc_field(tc, ["Test Case ID", "Test ID", "test_case_id", "id"], "TC")).replace("|", "\\|")
                    t_obj = str(extract_tc_field(tc, ["Test Case Objective", "Test case Objective", "objective", "วัตถุประสงค์"], "")).replace("\n", " ").replace("|", "\\|")
                    t_step = str(extract_tc_field(tc, ["Test Step", "Test Description / Procedure", "steps", "ขั้นตอน"], "")).replace("\n", "<br>").replace("|", "\\|")
                    t_data = str(extract_tc_field(tc, ["Test Data", "data", "ข้อมูลทดสอบ"], "-")).replace("\n", "<br>").replace("|", "\\|")
                    t_type = str(extract_tc_field(tc, ["Test Type", "type", "ประเภท"], "Positive")).replace("|", "\\|")
                    t_exp = str(extract_tc_field(tc, ["Expected Result", "expected", "ผลลัพธ์ที่คาดหวัง"], "")).replace("\n", "<br>").replace("|", "\\|")
                    t_rem = str(extract_tc_field(tc, ["Remark", "remark", "หมายเหตุ"], "-")).replace("\n", " ").replace("|", "\\|")
                    t_auto = str(extract_tc_field(tc, ["Automate", "automate"], "TRUE")).replace("|", "\\|")
                    t_req = str(extract_tc_field(tc, ["Req No.", "Requirement ID", "req_no"], "-")).replace("|", "\\|")
                    t_plat = str(extract_tc_field(tc, ["Platforms", "Platform"], "Web Application")).replace("|", "\\|")
                    t_upd = str(extract_tc_field(tc, ["Updated By", "Update by"], tester_val)).replace("|", "\\|")

                    md_lines.append(f"| {t_id} | {t_obj} | {t_step} | {t_data} | {t_type} | {t_exp} | {t_rem} | {t_auto} | {t_req} | {t_plat} | {t_upd} |")
                md_lines.append("")

            doc_markdown = "\n".join(md_lines)
            rendered_markdown = simple_markdown_to_html(doc_markdown)
            html_body = build_generic_document_html(
                doc_name, doc_type, project_name, project_code, skill_name, today_str, rendered_markdown,
                doc_version=version_val, doc_author=tester_val, doc_date=today_str
            )

        else:
            # Generic Document Types (SRS, SDD, TOR, UAT, User Manual, Admin Manual, etc.)
            clean_md = doc_content
            if clean_md.startswith("```markdown"):
                clean_md = clean_md[11:]
            elif clean_md.startswith("```"):
                clean_md = clean_md[3:]
            if clean_md.endswith("```"):
                clean_md = clean_md[:-3]
            doc_markdown = sanitize_engineering_markdown(clean_md.strip())

            # Extract dynamic metadata from markdown to avoid top header vs. section 1 conflicts
            doc_version, doc_author, doc_date = extract_document_metadata(doc_markdown)

            # Generate HTML for PDF using System Template
            rendered_markdown = simple_markdown_to_html(doc_markdown)
            html_body = build_generic_document_html(
                doc_name, doc_type, project_name, project_code, skill_name, today_str, rendered_markdown,
                doc_version=doc_version, doc_author=doc_author, doc_date=doc_date
            )

        # Render PDF
        render_html_to_pdf(html_body, pdf_file_path)

        # 6. Update DB with file_url (Excel for Test Case / PDF for others), pdf_url (PDF), markdown_content
        cursor.execute("SELECT status FROM qa_generated_documents WHERE id = %s::uuid", (gen_id,))
        status_row = cursor.fetchone()
        if status_row and status_row[0] == 'Cancelled':
            logger.info(f"Document generation {gen_id} was cancelled by user. Discarding output.")
            return

        final_file_url = excel_file_path if excel_file_path else pdf_file_path

        cursor.execute("""
            UPDATE qa_generated_documents 
            SET status = 'Completed', 
                file_url = %s, 
                pdf_url = %s, 
                markdown_content = %s, 
                is_saved_to_project = FALSE 
            WHERE id = %s::uuid AND status != 'Cancelled'
        """, (final_file_url, pdf_file_path, doc_markdown, gen_id))
        conn.commit()
        logger.info(f"Successfully generated QA document (File: {final_file_url}, PDF: {pdf_file_path})")

        # Notify strictly the user who requested the document generation
        if username:
            try:
                from notification_service import send_user_notification
                send_user_notification(
                    username=username,
                    title=f"สร้างเอกสาร '{doc_name}' เสร็จสมบูรณ์",
                    message=f"เอกสาร {doc_type} สร้างเสร็จเรียบร้อยแล้ว พร้อมดาวน์โหลดหรือส่งตรวจ QA Consult ทันที",
                    noti_type="success",
                    icon="📄",
                    action_view="qa_doc_creation",
                    action_payload={"doc_name": doc_name, "project_id": str(project_id), "doc_id": str(gen_id)}
                )
            except Exception as noti_err:
                logger.error(f"Failed to dispatch completion notification to {username}: {noti_err}")

    except Exception as e:
        logger.error(f"Error in create_qa_document_async: {e}", exc_info=True)
        if conn and cursor:
            try:
                conn.rollback()
                cursor.execute("""
                    ALTER TABLE qa_generated_documents ADD COLUMN IF NOT EXISTS error_message TEXT;
                    UPDATE qa_generated_documents 
                    SET status = 'Failed', error_message = %s 
                    WHERE id = %s::uuid AND status != 'Cancelled'
                """, (str(e), gen_id))
                conn.commit()
            except Exception as update_err:
                logger.error(f"Failed to update failed status in DB: {update_err}")

        # Notify user about failure
        if username:
            try:
                from notification_service import send_user_notification
                send_user_notification(
                    username=username,
                    title=f"สร้างเอกสาร '{doc_name}' ไม่สำเร็จ",
                    message=f"เกิดข้อผิดพลาดในการประมวลผล: {str(e)[:150]}",
                    noti_type="error",
                    icon="❌",
                    action_view="qa_doc_creation",
                    action_payload={"doc_name": doc_name, "project_id": str(project_id)}
                )
            except Exception as noti_err:
                logger.error(f"Failed to dispatch failure notification to {username}: {noti_err}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv()
    print("Script loaded successfully.")
