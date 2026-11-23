"""
excel_report.py - QA Report Excel Generator
สร้าง Excel Report จากผลการวิเคราะห์ QA ด้วย Gemini AI
"""

import os
import re
import json
import logging
import uuid
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Reports output directory
REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
    logger.warning("openpyxl not installed. Install with: pip install openpyxl")


def parse_qa_report_with_ai(report_text: str, filename: str) -> list[dict]:
    """
    Use Gemini AI to parse the QA report text into structured rows for Excel.
    Falls back to regex parsing if AI fails.
    """
    try:
        from ocr_engine import _get_gemini_client
        client = _get_gemini_client()
        gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

        prompt = f"""คุณคือผู้เชี่ยวชาญด้านการวิเคราะห์รายงาน QA (Quality Assurance)
กรุณาแปลงรายงานการตรวจสอบด้านล่างนี้ ให้เป็น JSON Array ที่แต่ละ Object มี Key ดังนี้:

- "page_number": หมายเลขหน้าเอกสารที่เป็นตัวเลขจำนวนเต็ม (เช่น 1, 2, 3) ตามที่ระบุในรายงาน เช่น "[หน้า 3]" หรือ "หน้า 3" (หากเป็นข้อมูลที่ขาดหายในส่วนหัว/Document Control ให้ใส่ 1; ใส่ null เฉพาะกรณีที่ไม่สามารถระบุหน้าได้จริงๆ เท่านั้น)
- "location": ตำแหน่งที่ชัดเจนภายในหน้า เช่น "หน้าปก — ตาราง Document Control", "หัวข้อ 2.1 — ตาราง Test Case แถว TC-004", "ย่อหน้าที่ 2" (ห้ามเขียนคลุมเครือว่า "ในเอกสาร" หรือ "-")
- "document_page": ชื่อเอกสาร / หน้าที่เกี่ยวข้องพร้อมตำแหน่ง (เช่น "หน้า 3 — หัวข้อ 2.1 ตาราง Test Case" ถ้าไม่ระบุให้ใส่ชื่อไฟล์ "{filename}")
- "issue": ประเด็นที่พบ (สรุปสั้นๆ ชัดเจน)
- "severity": ระดับความรุนแรง (Critical / High / Medium / Low / Info)
- "check_type": ประเภทการตรวจ (เช่น SRS Completeness, UI/UX, Security, Performance, Spelling)
- "found_incorrect": ข้อความที่ผิดพลาดในเอกสาร (คัดลอกข้อความ/วลีที่ผิดจากเอกสารให้ตรงตัวที่สุด เพื่อให้ระบบนำไปไฮไลต์บนหน้าเอกสารได้ตรงจุด หากเป็นข้อมูลที่ขาดหายให้ระบุหัวข้อที่เกี่ยวข้องหรือ "-")
- "correct_value": สิ่งที่ควรเป็น (ค่าที่ควรจะเป็น หรือแนวทางที่ถูก ถ้าไม่มีให้ใส่ "-")
- "recommendation": ข้อเสนอแนะ (คำแนะนำในการแก้ไข)

**สำคัญมาก**: ตอบเป็น JSON Array เท่านั้น ห้ามมี text อื่นนอกจาก JSON
**ข้อห้ามเด็ดขาด**: ห้ามนำรายการที่ระบุว่า "แก้ไขเรียบร้อยแล้ว", "ผ่านเกณฑ์", "ไม่มีข้อผิดพลาด", "Resolved", หรือ "Closed" จากหมวดการตรวจสอบการแก้ไขรอบก่อนหน้า มาใส่ใน JSON Array โดยเด็ดขาด ให้ใส่เฉพาะประเด็นข้อผิดพลาดหรือข้อบกพร่องที่ยังคงค้างอยู่จริงในเอกสารฉบับนี้เท่านั้น
ถ้าไม่มีประเด็นข้อผิดพลาดใดๆ ให้ตอบ []

=== รายงาน QA ===
{report_text}
"""

        from ocr_engine import get_all_api_keys, _get_gemini_client
        all_keys = get_all_api_keys()
        raw_fallback_models = [gemini_model, 'gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.5-flash-lite']
        seen = set()
        fallback_models = [m for m in raw_fallback_models if m not in ('gemini-3.1-pro', 'gemini-3.1-flash') and not (m in seen or seen.add(m))]
        gemini_res = None
        
        for k_idx in range(len(all_keys) if all_keys else 1):
            client = _get_gemini_client(k_idx)
            for current_model in fallback_models:
                for attempt in range(2):
                    try:
                        gemini_res = client.models.generate_content(
                            model=current_model,
                            contents=prompt,
                        )
                        break
                    except Exception as e:
                        error_msg = str(e)
                        if '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg or 'Quota' in error_msg:
                            import time
                            time.sleep(2)
                            continue
                        else:
                            break
                if gemini_res:
                    break
            if gemini_res:
                break

        if gemini_res and gemini_res.text:
            if hasattr(gemini_res, 'usage_metadata') and gemini_res.usage_metadata:
                try:
                    from db_ingestion import log_api_usage
                    log_api_usage("Excel_Report_Summary", current_model or "gemini-2.5-flash", gemini_res.usage_metadata)
                except Exception as log_err:
                    logger.warning(f"Failed to log API usage in Excel Report: {log_err}")

            # Extract JSON from response
            text = gemini_res.text.strip()
            # Remove markdown code block if present
            if text.startswith("```"):
                text = re.sub(r'^```(?:json)?\s*', '', text)
                text = re.sub(r'\s*```$', '', text)
            
            rows = json.loads(text)
            if isinstance(rows, list):
                return rows
    
    except Exception as e:
        logger.error(f"AI parsing failed, falling back to regex: {e}")

    # Fallback: basic regex parsing
    return parse_qa_report_regex(report_text, filename)


def parse_qa_report_regex(report_text: str, filename: str) -> list[dict]:
    """
    Fallback regex-based parser for QA report text.
    Tries to extract bullet points and numbered items as issues.
    """
    rows = []
    lines = report_text.split('\n')
    current_section = ""
    item_count = 0
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        
        # Detect section headers (## or ### or bold **)
        if stripped.startswith('#'):
            current_section = re.sub(r'^#+\s*', '', stripped).strip()
            continue
        if stripped.startswith('**') and stripped.endswith('**'):
            current_section = stripped.strip('*').strip()
            continue
        
        # Detect bullet points or numbered items as issues
        issue_match = re.match(r'^[\-\*\•]\s+(.+)', stripped)
        num_match = re.match(r'^\d+[\.\)]\s+(.+)', stripped)
        
        if issue_match or num_match:
            content = (issue_match or num_match).group(1)
            item_count += 1
            
            # Determine severity based on keywords
            severity = "Low"
            if any(kw in content.lower() for kw in ['critical', 'ร้ายแรง', 'วิกฤต']):
                severity = "Critical"
            elif any(kw in content.lower() for kw in ['high', 'major', 'สำคัญ', 'ผิดพลาด', 'ขัดแย้ง']):
                severity = "High"
            elif any(kw in content.lower() for kw in ['medium', 'ปานกลาง']):
                severity = "Medium"
            elif any(kw in content.lower() for kw in ['ถูกต้อง', 'สอดคล้อง', 'ผ่าน', 'info']):
                severity = "Info"
            
            # Determine check type from section
            check_type = "ทั่วไป"
            if any(kw in current_section for kw in ['สอดคล้อง', 'Conformity', 'SRS']):
                check_type = "SRS Completeness"
            elif any(kw in current_section for kw in ['ขัดแย้ง', 'ผิดพลาด', 'Error']):
                check_type = "ข้อมูลขัดแย้ง"
            
            rows.append({
                "document_page": filename,
                "issue": content[:100],
                "severity": severity,
                "check_type": check_type,
                "found_incorrect": content,
                "correct_value": "-",
                "recommendation": "-"
            })
    
    # If nothing was parsed, create a single summary row
    if not rows:
        rows.append({
            "document_page": filename,
            "issue": "รายงานการตรวจสอบ QA",
            "severity": "Info",
            "check_type": "สรุปผล",
            "found_incorrect": report_text[:500],
            "correct_value": "-",
            "recommendation": "ดูรายละเอียดในรายงานฉบับเต็ม"
        })
    
    return rows


def _format_finding_page_ref(row_data: dict) -> str:
    """Format a clear Thai page reference string for a QA finding row."""
    pn = row_data.get('page_number')
    p_lbl = str(row_data.get('page_label') or '').strip()
    doc_page = str(row_data.get('document_page') or '').strip()

    if pn is not None and str(pn).strip().isdigit():
        p_int = int(str(pn).strip())
        if p_lbl and p_lbl != f"หน้า {p_int}" and "ภาพรวม" not in p_lbl:
            return f"หน้า {p_int} ({p_lbl})"
        return f"หน้า {p_int}"
    if p_lbl:
        return p_lbl
    if doc_page:
        m = re.search(r'(?:หน้า|page|p\.)\s*[:#]?\s*(\d+)', doc_page, re.I)
        if m:
            return f"หน้า {m.group(1)}"
    return "ภาพรวมทั้งเอกสาร"


def _format_exit_item_page_ref(item: dict) -> str:
    """Format a clear Thai page reference string for an Exit Criteria item."""
    p_ref = str(item.get('page_ref') or '').strip()
    if p_ref:
        return p_ref
    p_nums = item.get('page_numbers')
    if isinstance(p_nums, list) and p_nums:
        clean_nums = sorted({int(x) for x in p_nums if str(x).isdigit()})
        if clean_nums:
            return "หน้า " + ", ".join(str(x) for x in clean_nums)
    pn = item.get('page_number')
    if pn is not None and str(pn).strip().isdigit():
        return f"หน้า {int(str(pn).strip())}"
    combined = f"{item.get('evidence_text', '')} {item.get('remarks', '')}"
    found = sorted({int(m) for m in re.findall(r'(?:หน้า|page|p\.)\s*[:#]?\s*(\d+)', combined, re.I)})
    if found:
        return "หน้า " + ", ".join(str(x) for x in found)
    return "ภาพรวมทั้งเอกสาร"


def _calc_row_height(values: list, col_widths: list, min_h: int = 34, max_h: int = 160) -> int:
    """Estimate wrapped row height so Thai/English multiline text is never clipped."""
    max_lines = 1
    for val, w in zip(values, col_widths):
        txt = str(val or "")
        if not txt:
            continue
        usable_w = max(8, int(w * 0.85))
        lines = 0
        for part in txt.split('\n'):
            lines += max(1, (len(part) + usable_w - 1) // usable_w)
        if lines > max_lines:
            max_lines = lines
    return max(min_h, min(max_h, max_lines * 16 + 14))


def generate_qa_excel(report_text: str, filename: str, doc_type: str = "Requirement", project_code: str = "", group_name: str = "", group_type: str = "", transaction_id: str = None, exit_criteria_eval: dict = None, qa_findings: list = None) -> str:
    """
    Generate Excel QA Report from report text, pre-parsed findings, and optional Exit Criteria evaluation.
    Includes explicit page numbers and erroneous quotes on every finding and Exit Criteria item,
    plus a Page Focus summary sheet.
    """
    if not HAS_OPENPYXL:
        raise ImportError("openpyxl is required to generate Excel reports.")
        
    if isinstance(qa_findings, list) and len(qa_findings) > 0:
        rows = qa_findings
    else:
        rows = parse_qa_report_with_ai(report_text, filename)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "QA Audit Summary"
    ws.views.sheetView[0].showGridLines = True
    
    header_font = Font(name='Tahoma', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='1F4E78', end_color='1F4E78', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    title_font = Font(name='Tahoma', bold=True, size=14, color='FFFFFF')
    title_fill = PatternFill(start_color='203864', end_color='203864', fill_type='solid')
    subtitle_font = Font(name='Tahoma', bold=False, italic=True, size=10, color='1F2937')
    subtitle_fill = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
    data_font = Font(name='Tahoma', size=10)
    data_alignment = Alignment(vertical='top', wrap_text=True)
    center_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    page_badge_fill = PatternFill(start_color='EEF2FF', end_color='EEF2FF', fill_type='solid')
    page_badge_font = Font(name='Tahoma', bold=True, size=10, color='3730A3')
    wrong_text_fill = PatternFill(start_color='FFF1F2', end_color='FFF1F2', fill_type='solid')
    wrong_text_font = Font(name='Tahoma', size=10, color='9F1239')
    
    severity_fills = {
        'Critical': PatternFill(start_color='DC2626', end_color='DC2626', fill_type='solid'),
        'High': PatternFill(start_color='EA580C', end_color='EA580C', fill_type='solid'),
        'Medium': PatternFill(start_color='FACC15', end_color='FACC15', fill_type='solid'),
        'Low': PatternFill(start_color='E0E7FF', end_color='E0E7FF', fill_type='solid'),
        'Info': PatternFill(start_color='F3F4F6', end_color='F3F4F6', fill_type='solid'),
    }
    severity_fonts = {
        'Critical': Font(name='Tahoma', bold=True, size=10, color='FFFFFF'),
        'High': Font(name='Tahoma', bold=True, size=10, color='FFFFFF'),
        'Medium': Font(name='Tahoma', bold=True, size=10, color='000000'),
        'Low': Font(name='Tahoma', bold=True, size=10, color='3730A3'),
        'Info': Font(name='Tahoma', bold=False, size=10, color='374151'),
    }
    thin_border = Border(
        left=Side(style='thin', color='D1D5DB'),
        right=Side(style='thin', color='D1D5DB'),
        top=Side(style='thin', color='D1D5DB'),
        bottom=Side(style='thin', color='D1D5DB')
    )

    page_counts = {}
    for r in rows:
        pn = r.get('page_number')
        if pn is not None and str(pn).strip().isdigit():
            k = int(str(pn).strip())
            page_counts[k] = page_counts.get(k, 0) + 1
    err_pages_str = ", ".join(f"หน้า {k} ({page_counts[k]} ข้อ)" for k in sorted(page_counts.keys())) if page_counts else "ดูรายละเอียดรายข้อด้านล่าง"
    
    ws.merge_cells('A1:I1')
    title_cell = ws['A1']
    title_cell.value = f"QA Audit Findings Report — {filename}"
    title_cell.font = title_font
    title_cell.fill = title_fill
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28
    
    ws.merge_cells('A2:I2')
    subtitle_cell = ws['A2']
    project_str = project_code if project_code else (group_name if group_name else "Spectra QA System")
    subtitle_cell.value = (
        f"โครงการ: {project_str} | วันที่ตรวจ: {datetime.now().strftime('%d/%m/%Y %H:%M')} | "
        f"พบทั้งหมด: {len(rows)} ประเด็น | หน้าที่พบข้อผิดพลาด: {err_pages_str}"
    )
    subtitle_cell.font = subtitle_font
    subtitle_cell.fill = subtitle_fill
    subtitle_cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[2].height = 24
    
    table_start_row = 3
    headers = [
        "ลำดับ", "หมายเลขหน้า (Page)", "เอกสาร / ตำแหน่ง", "ประเด็นที่พบ (Issue)",
        "ระดับความรุนแรง", "ประเภทการตรวจ", "ข้อความที่ผิดพลาดในเอกสาร", "สิ่งที่ควรเป็น", "ข้อเสนอแนะ"
    ]
    col_widths = [8, 18, 22, 36, 15, 22, 42, 40, 40]
    for col_idx, (header, width) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=table_start_row, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.row_dimensions[table_start_row].height = 30
    ws.freeze_panes = 'A4'
    
    for row_idx, row_data in enumerate(rows, 1):
        excel_row = table_start_row + row_idx
        severity = row_data.get('severity', 'Info')
        page_ref_str = _format_finding_page_ref(row_data)
        found_txt = row_data.get('found_incorrect', '-') or '-'
        values = [
            row_idx, page_ref_str,
            (row_data.get('location') or row_data.get('document_page') or filename),
            row_data.get('issue', '-') or '-', severity, row_data.get('check_type', '-') or '-',
            found_txt, row_data.get('correct_value', '-') or '-', row_data.get('recommendation', '-') or '-'
        ]
        for col_idx, value in enumerate(values, 1):
            cell = ws.cell(row=excel_row, column=col_idx, value=value)
            cell.font = data_font
            cell.alignment = center_alignment if col_idx in [1, 2, 5] else data_alignment
            cell.border = thin_border
            if col_idx == 2 and page_ref_str != "ภาพรวมทั้งเอกสาร":
                cell.fill = page_badge_fill
                cell.font = page_badge_font
            elif col_idx == 5:
                cell.fill = severity_fills.get(severity, PatternFill())
                cell.font = severity_fonts.get(severity, data_font)
            elif col_idx == 7 and found_txt != '-':
                cell.fill = wrong_text_fill
                cell.font = wrong_text_font
        ws.row_dimensions[excel_row].height = _calc_row_height(values, col_widths, min_h=42, max_h=150)
    
    footer_row = table_start_row + len(rows) + 2
    ws.merge_cells(start_row=footer_row, start_column=1, end_row=footer_row, end_column=9)
    footer_cell = ws.cell(row=footer_row, column=1, value="สร้างโดย Spectra QA Intelligent Analysis System | Powered by Gemini AI")
    footer_cell.font = Font(name='Tahoma', italic=True, size=9, color='999999')
    footer_cell.alignment = Alignment(horizontal='center')
    
    # === Sheet 2: Exit Criteria Checklist ===
    eval_items = []
    if exit_criteria_eval and isinstance(exit_criteria_eval, dict):
        ws_exit = wb.create_sheet(title="Exit Criteria Checklist")
        ws_exit.views.sheetView[0].showGridLines = True
        ws_exit.merge_cells('A1:I1')
        t_cell = ws_exit['A1']
        t_cell.value = f"Exit Criteria Gate Assessment Report - {exit_criteria_eval.get('template_title', 'Universal')}"
        t_cell.font = title_font
        t_cell.fill = PatternFill(start_color='1E293B', end_color='1E293B', fill_type='solid')
        t_cell.alignment = Alignment(horizontal='center', vertical='center')
        ws_exit.row_dimensions[1].height = 28

        ws_exit.merge_cells('A2:I2')
        sub_cell = ws_exit['A2']
        status_text = exit_criteria_eval.get('status', 'PENDING')
        score = exit_criteria_eval.get('score_percentage', 0)
        sub_cell.value = (
            f"Final Gate Result: {status_text} | Score: {score}% | "
            f"PASS: {exit_criteria_eval.get('passed_items',0)} | FAIL: {exit_criteria_eval.get('failed_items',0)} | N/A: {exit_criteria_eval.get('na_items',0)}"
        )
        sub_cell.font = Font(name='Tahoma', bold=True, size=11, color='FFFFFF')
        status_color = '059669' if status_text == 'PASSED' else ('D97706' if status_text == 'CONDITIONAL_PASSED' else 'DC2626')
        sub_cell.fill = PatternFill(start_color=status_color, end_color=status_color, fill_type='solid')
        sub_cell.alignment = Alignment(horizontal='center', vertical='center')
        ws_exit.row_dimensions[2].height = 24

        exit_headers = [
            "ข้อตรวจ", "หมวดหมู่", "รายการประเมิน (Checklist Item)", "ตัวชี้วัด (KPI Indicator)",
            "ความรุนแรง", "ผลการตรวจ", "หมายเลขหน้า (Page)", "เหตุผล / ข้อสังเกต", "ข้อความที่พบ / จุดที่ผิดพลาดในเอกสาร"
        ]
        exit_col_widths = [12, 24, 38, 24, 12, 12, 18, 38, 42]
        for col_idx, (hdr, width) in enumerate(zip(exit_headers, exit_col_widths), 1):
            c = ws_exit.cell(row=3, column=col_idx, value=hdr)
            c.font = header_font
            c.fill = header_fill
            c.alignment = header_alignment
            c.border = thin_border
            ws_exit.column_dimensions[get_column_letter(col_idx)].width = width
        ws_exit.row_dimensions[3].height = 28
        ws_exit.freeze_panes = 'A4'
        
        eval_items = exit_criteria_eval.get('items', [])
        for r_idx, item in enumerate(eval_items, 4):
            item_status = item.get('status', 'NA')
            item_page_ref = _format_exit_item_page_ref(item)
            ev_text = (item.get('evidence_text') or '').strip() or '-'
            vals = [
                item.get('item_code', '-'), item.get('category', '-'), item.get('question_text', '-'),
                item.get('target_metric', '100% (ผ่านบริบูรณ์)'), item.get('severity', 'Major'),
                item_status, item_page_ref, item.get('remarks', '-') or '-', ev_text
            ]
            for c_idx, val in enumerate(vals, 1):
                c = ws_exit.cell(row=r_idx, column=c_idx, value=val)
                c.font = data_font
                c.alignment = center_alignment if c_idx in [1, 5, 6, 7] else data_alignment
                c.border = thin_border
                if c_idx == 6:
                    if item_status == 'PASS':
                        c.fill = PatternFill(start_color='D1FAE5', end_color='D1FAE5', fill_type='solid')
                        c.font = Font(name='Tahoma', bold=True, color='065F46')
                    elif item_status == 'FAIL':
                        c.fill = PatternFill(start_color='FEE2E2', end_color='FEE2E2', fill_type='solid')
                        c.font = Font(name='Tahoma', bold=True, color='991B1B')
                    else:
                        c.fill = PatternFill(start_color='F3F4F6', end_color='F3F4F6', fill_type='solid')
                        c.font = Font(name='Tahoma', bold=False, color='4B5563')
                elif c_idx == 7 and item_page_ref != "ภาพรวมทั้งเอกสาร":
                    c.fill = wrong_text_fill if item_status == 'FAIL' else page_badge_fill
                    c.font = Font(name='Tahoma', bold=True, size=10, color='9F1239' if item_status == 'FAIL' else '3730A3')
                elif c_idx == 9 and item_status == 'FAIL' and ev_text != '-':
                    c.fill = wrong_text_fill
                    c.font = wrong_text_font
            ws_exit.row_dimensions[r_idx].height = _calc_row_height(vals, exit_col_widths, min_h=36, max_h=140)

    # === Sheet 3: Page Focus Summary ===
    page_bucket = {}
    def _ensure_bucket(p_key, p_label):
        if p_key not in page_bucket:
            page_bucket[p_key] = {'label': p_label, 'crit_high': 0, 'medium': 0, 'low_info': 0, 'failed_exit_codes': [], 'snippets': []}
        return page_bucket[p_key]

    for r in rows:
        pn = r.get('page_number')
        p_key = int(str(pn).strip()) if (pn is not None and str(pn).strip().isdigit()) else 999999
        p_lbl = _format_finding_page_ref(r) if p_key != 999999 else "ภาพรวมทั้งเอกสาร"
        b = _ensure_bucket(p_key, p_lbl)
        sev = str(r.get('severity') or 'Info').lower()
        if sev in ('critical', 'high'): b['crit_high'] += 1
        elif sev == 'medium': b['medium'] += 1
        else: b['low_info'] += 1
        iss = str(r.get('issue') or '').strip()
        bad = str(r.get('found_incorrect') or '').strip()
        if iss:
            line = f"[{r.get('severity', 'Info')}] {iss}" + (f" (พบ: \"{bad[:90]}\")" if bad and bad != '-' else "")
            b['snippets'].append(line)

    for item in eval_items:
        if str(item.get('status') or '').upper() != 'FAIL':
            continue
        code_tag = f"[{item.get('item_code', '-')}]"
        p_nums = item.get('page_numbers') if isinstance(item.get('page_numbers'), list) and item.get('page_numbers') else []
        if not p_nums and item.get('page_number') is not None and str(item.get('page_number')).strip().isdigit():
            p_nums = [int(str(item.get('page_number')).strip())]
        target_keys = sorted({int(x) for x in p_nums if str(x).isdigit()}) or [999999]
        for tk in target_keys:
            b = _ensure_bucket(tk, f"หน้า {tk}" if tk != 999999 else "ภาพรวมทั้งเอกสาร")
            if code_tag not in b['failed_exit_codes']:
                b['failed_exit_codes'].append(code_tag)
            ev = str(item.get('evidence_text') or '').strip()
            if ev and ev != '-':
                b['snippets'].append(f"Exit Criteria {code_tag} FAIL: {ev[:110]}")

    if page_bucket:
        ws_pages = wb.create_sheet(title="สรุปรายหน้า (Page Focus)")
        ws_pages.views.sheetView[0].showGridLines = True
        ws_pages.merge_cells('A1:G1')
        pt_cell = ws_pages['A1']
        pt_cell.value = f"สรุปหน้าที่พบข้อผิดพลาด & จุดที่ต้องแก้ไข (Page Focus Summary) — {filename}"
        pt_cell.font = title_font
        pt_cell.fill = title_fill
        pt_cell.alignment = Alignment(horizontal='center', vertical='center')
        ws_pages.row_dimensions[1].height = 28

        p_headers = ["หมายเลขหน้า (Page)", "จำนวนข้อผิดพลาดรวม", "Critical / High", "Medium", "Low / Info", "ข้อ Exit Criteria ที่ไม่ผ่าน", "รายละเอียดจุดที่ผิดพลาดในหน้านี้"]
        p_widths = [20, 18, 15, 12, 12, 24, 65]
        for c_idx, (hdr, w) in enumerate(zip(p_headers, p_widths), 1):
            c = ws_pages.cell(row=2, column=c_idx, value=hdr)
            c.font = header_font
            c.fill = header_fill
            c.alignment = header_alignment
            c.border = thin_border
            ws_pages.column_dimensions[get_column_letter(c_idx)].width = w
        ws_pages.row_dimensions[2].height = 28
        ws_pages.freeze_panes = 'A3'

        for r_i, p_key in enumerate(sorted(page_bucket.keys()), 3):
            b = page_bucket[p_key]
            tot = b['crit_high'] + b['medium'] + b['low_info']
            vals = [b['label'], tot, b['crit_high'], b['medium'], b['low_info'], ", ".join(b['failed_exit_codes']) if b['failed_exit_codes'] else "-", "\n".join(f"• {s}" for s in b['snippets'][:12]) if b['snippets'] else "-"]
            for c_idx, val in enumerate(vals, 1):
                c = ws_pages.cell(row=r_i, column=c_idx, value=val)
                c.font = data_font
                c.alignment = center_alignment if c_idx <= 5 else data_alignment
                c.border = thin_border
                if c_idx == 1:
                    c.fill = page_badge_fill
                    c.font = page_badge_font
                elif c_idx == 3 and b['crit_high'] > 0:
                    c.fill = PatternFill(start_color='FEE2E2', end_color='FEE2E2', fill_type='solid')
                    c.font = Font(name='Tahoma', bold=True, color='991B1B')
            ws_pages.row_dimensions[r_i].height = _calc_row_height(vals, p_widths, min_h=34, max_h=200)

    report_id = transaction_id or str(uuid.uuid4())[:8]
    safe_filename = re.sub(r'[^\w\-.]', '_', filename.rsplit('.', 1)[0])
    excel_filename = f"QA_Report_{safe_filename}_{report_id}.xlsx"
    filepath = REPORTS_DIR / excel_filename
    wb.save(str(filepath))
    logger.info(f"Excel QA Report saved: {filepath}")
    return str(filepath)
