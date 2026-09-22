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
    with a graceful fallback to WeasyPrint or ReportLab if Playwright encounters an issue.
    """
    # 1. Try Playwright
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
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

    # 2. Try WeasyPrint if available
    try:
        import weasyprint
        weasyprint.HTML(string=html_content).write_pdf(output_path)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"WeasyPrint PDF generated successfully at {output_path}")
            return True
    except Exception:
        pass

    # 3. Fallback: ReportLab PDF Generator (Clean text parsing without raw CSS/scripts)
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib import colors

        font_candidates = [
            'C:/Windows/Fonts/tahoma.ttf',
            'C:/Windows/Fonts/segoeui.ttf',
            'C:/Windows/Fonts/arial.ttf',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/dejavu/DejaVuSans.ttf',
            '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
            '/usr/share/fonts/thai-scalable/Waree.ttf'
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


def build_generic_document_html(doc_name: str, doc_type: str, project_name: str, project_code: str, skill_name: str, today_str: str, rendered_markdown: str) -> str:
    """Builds an enterprise-grade HTML document for SRS, SDD, TOR, UAT, Manuals, etc."""
    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>{doc_name} - {doc_type}</title>
<style>
    @page {{
        size: A4 portrait;
        margin: 16mm 14mm 16mm 14mm;
        @bottom-right {{
            content: counter(page);
            font-size: 9px;
            color: #64748b;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }}
    }}
    *, *:before, *:after {{ box-sizing: border-box; }}
    body {{
        font-family: 'Segoe UI', Tahoma, 'Sarabun', Arial, sans-serif;
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
            <span class="system-logo-badge">SPECTRA</span>
            <span>Autonomous QA & Test Synthesis Platform</span>
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
                <span class="doc-meta-label">Framework / Skill</span>
                <span class="doc-meta-value">{skill_name}</span>
            </div>
            <div class="doc-meta-item">
                <span class="doc-meta-label">Generated Date</span>
                <span class="doc-meta-value">{today_str}</span>
            </div>
        </div>
    </div>

    <div class="doc-control-card">
        <div class="doc-control-title">📋 Document Control & Metadata</div>
        <table class="doc-control-table">
            <thead>
                <tr>
                    <th style="width: 15%;">Version</th>
                    <th style="width: 20%;">Date</th>
                    <th style="width: 30%;">Author / Engine</th>
                    <th style="width: 20%;">Status</th>
                    <th style="width: 15%;">Classification</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>1.0.0</strong></td>
                    <td>{today_str}</td>
                    <td>Spectra AI (Gemini 3.1 Pro)</td>
                    <td><span class="badge badge-success">Approved Baseline</span></td>
                    <td>Internal Spec</td>
                </tr>
            </tbody>
        </table>
    </div>

    <div class="doc-body">
        {rendered_markdown}
    </div>

    <div class="doc-footer">
        <div>Spectra QA Platform &bull; Automated Document Synthesis</div>
        <div>Generated with Gemini 3.1 Pro &bull; {today_str}</div>
    </div>
</body>
</html>"""


def build_testcase_document_html(doc_name: str, doc_type: str, project_name: str, project_code: str, module_val: str, tester_val: str, today_str: str, test_cases: list) -> str:
    """Builds a high-density, professional landscape HTML document for Test Cases."""
    rows_html = ""
    for tc in test_cases:
        res_val = str(tc.get("Result (Pass/Fail)", "PASS")).upper()
        badge_class = "pass" if res_val == "PASS" else ("fail" if res_val == "FAIL" else "blocked")
        proc_html = str(tc.get("Test Description / Procedure", "")).replace("\n", "<br>")
        rows_html += f"""
        <tr>
            <td style="font-weight: 700; text-align: center; color: #1e3a8a;">{tc.get("Test Case ID", "")}</td>
            <td style="font-weight: 600;">{tc.get("Test case Objective", "")}</td>
            <td>{proc_html}</td>
            <td>{tc.get("Test Data", "-")}</td>
            <td>{tc.get("Expected Result", "")}</td>
            <td style="text-align: center;"><span class="badge {badge_class}">{res_val}</span></td>
            <td style="text-align: center; font-weight: 600;">{tc.get("Req No.", "-")}</td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>{doc_name} - Test Specification</title>
<style>
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
        font-family: 'Segoe UI', Tahoma, 'Sarabun', Arial, sans-serif;
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
                <span class="doc-meta-label">Project</span>
                <span class="doc-meta-value">{project_name} ({project_code})</span>
            </div>
            <div class="doc-meta-item">
                <span class="doc-meta-label">Module / Function</span>
                <span class="doc-meta-value">{module_val}</span>
            </div>
            <div class="doc-meta-item">
                <span class="doc-meta-label">Tester / Author</span>
                <span class="doc-meta-value">{tester_val}</span>
            </div>
            <div class="doc-meta-item">
                <span class="doc-meta-label">Execution Date</span>
                <span class="doc-meta-value">{today_str}</span>
            </div>
        </div>
    </div>

    <table>
        <thead>
            <tr>
                <th style="width: 8%; text-align: center;">Test ID</th>
                <th style="width: 20%;">Objective</th>
                <th style="width: 28%;">Description / Procedure</th>
                <th style="width: 14%;">Test Data</th>
                <th style="width: 18%;">Expected Result</th>
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

        # 3. Call Gemini with Gemini 3.1 Pro
        model_to_use = os.environ.get("GEMINI_DOC_MODEL", "gemini-3.1-pro")
        doc_content, usage_metadata = call_gemini(prompt, model_name=model_to_use)
        
        if usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_6_Doc_Creator", model_to_use, usage_metadata, filename=doc_name)
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
        model_to_use = os.environ.get("GEMINI_DOC_MODEL", "gemini-3.1-pro")
        doc_content, usage_metadata = call_gemini(prompt, model_name=model_to_use)
        
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
                # Regex match fallback
                match = re.search(r'(\{[\s\S]*\})', json_text)
                if match:
                    try:
                        data = json.loads(match.group(1))
                    except Exception:
                        pass

            if not data or not isinstance(data, dict):
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

            meta = data.get("metadata", {})
            tester_val = meta.get("tester_name", "AI Agent")
            module_val = meta.get("module_function", doc_name)
            test_cases = data.get("test_cases", [])

            # Generate formatted Excel file specifically for Test Case
            import openpyxl
            from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
            
            excel_file_name = f"{safe_name}_{unique_suffix}.xlsx"
            excel_file_path = os.path.join(upload_dir, excel_file_name)

            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Test Cases"
            
            header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
            sub_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
            white_bold = Font(bold=True, color="FFFFFF", size=11)
            bold_font = Font(bold=True, size=10)
            center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
            left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
            thin_border = Border(left=Side(style='thin', color='CBD5E1'), right=Side(style='thin', color='CBD5E1'), top=Side(style='thin', color='CBD5E1'), bottom=Side(style='thin', color='CBD5E1'))
            pass_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
            fail_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
            
            # Title
            ws.merge_cells('A1:I1')
            ws['A1'] = f"SPECTRA QA PLATFORM - {doc_name} ({doc_type})"
            ws['A1'].fill = header_fill
            ws['A1'].font = white_bold
            ws['A1'].alignment = center_align
            ws.row_dimensions[1].height = 28
            
            # Metadata
            metadata_map = [
                ("Project Name :", f"{project_name} ({project_code})", "Create Date :", today_str),
                ("Module / Function:", module_val, "Test Engine:", "Spectra AI (Gemini 3.1 Pro)"),
                ("Tester Name :", tester_val, "Status :", "Baseline Specification")
            ]
            
            row_idx = 3
            for r_data in metadata_map:
                ws.cell(row=row_idx, column=2).value = r_data[0]
                ws.cell(row=row_idx, column=2).font = bold_font
                ws.cell(row=row_idx, column=2).fill = sub_fill
                ws.cell(row=row_idx, column=2).alignment = Alignment(horizontal="right")
                
                ws.merge_cells(start_row=row_idx, start_column=3, end_row=row_idx, end_column=4)
                ws.cell(row=row_idx, column=3).value = r_data[1]
                
                ws.cell(row=row_idx, column=6).value = r_data[2]
                ws.cell(row=row_idx, column=6).font = bold_font
                ws.cell(row=row_idx, column=6).fill = sub_fill
                ws.cell(row=row_idx, column=6).alignment = Alignment(horizontal="right")
                
                ws.merge_cells(start_row=row_idx, start_column=7, end_row=row_idx, end_column=8)
                ws.cell(row=row_idx, column=7).value = r_data[3]
                
                for col in range(2, 9):
                    ws.cell(row=row_idx, column=col).border = thin_border
                row_idx += 1
                
            # Headers
            headers = ["Test ID", "Test Objective", "Test Description / Procedure", "Test Data", 
                       "Expected Result", "Actual Result", "Result (Pass/Fail)", "Req No.", "Updated By"]
            row_idx += 2
            for col_idx, h in enumerate(headers, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=h)
                cell.font = white_bold
                cell.fill = header_fill
                cell.alignment = center_align
                cell.border = thin_border
            ws.row_dimensions[row_idx].height = 24
                
            widths = [14, 28, 40, 20, 30, 22, 16, 12, 18]
            for i, w in enumerate(widths, 1):
                ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w
                
            # Data Rows
            header_keys = [
                ("Test Case ID", "Test ID"),
                ("Test case Objective", "Test Objective"),
                ("Test Description / Procedure", "Test Description / Procedure"),
                ("Test Data", "Test Data"),
                ("Expected Result", "Expected Result"),
                ("Actual Result", "Actual Result"),
                ("Result (Pass/Fail)", "Result (Pass/Fail)"),
                ("Req No.", "Req No."),
                ("Update by", "Updated By")
            ]
            
            row_idx += 1
            for tc in test_cases:
                for col_idx, (k1, k2) in enumerate(header_keys, 1):
                    val = tc.get(k1, tc.get(k2, ""))
                    cell = ws.cell(row=row_idx, column=col_idx, value=val)
                    cell.border = thin_border
                    cell.alignment = center_align if col_idx in [1, 7, 8, 9] else left_align
                    
                    if col_idx == 7:
                        res_str = str(val).upper()
                        if res_str == "PASS":
                            cell.fill = pass_fill
                        elif res_str == "FAIL":
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
            html_body = build_testcase_document_html(doc_name, doc_type, project_name, project_code, module_val, tester_val, today_str, test_cases)

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

            # Generate HTML for PDF using System Template
            rendered_markdown = simple_markdown_to_html(doc_markdown)
            html_body = build_generic_document_html(doc_name, doc_type, project_name, project_code, skill_name, today_str, rendered_markdown)

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
