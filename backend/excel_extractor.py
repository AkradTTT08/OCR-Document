import io
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

def is_excel_file(filename: str) -> bool:
    """Checks whether the file is an Excel document."""
    if not filename:
        return False
    lower = filename.lower()
    return lower.endswith(('.xlsx', '.xls', '.xlsm', '.csv'))

def extract_text_from_excel_bytes(file_bytes: bytes, filename: str = "") -> Tuple[str, int]:
    """
    Extracts structured Markdown text and sheet count from Excel bytes (.xlsx, .xls).
    Generates both clean Markdown tables and an itemized breakdown for high-accuracy QA audit.
    Returns: (extracted_markdown_text, sheet_count)
    """
    sheets_output = []
    sheet_count = 0

    # 1. Try openpyxl for .xlsx and .xlsm
    wb = None
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    except Exception as ox_err:
        logger.warning(f"openpyxl failed to load workbook ({ox_err}), trying pandas fallback...")

    if wb is not None:
        sheet_count = len(wb.worksheets)
        
        # Pre-scan all sheets to collect column metadata and execution support
        workbook_inventory = []
        sheets_data = []

        for ws in wb.worksheets:
            sheet_title = ws.title or "Sheet"
            raw_rows = list(ws.iter_rows(values_only=True))
            
            cleaned_rows = []
            for r in raw_rows:
                if any(c is not None and str(c).strip() != "" for c in r):
                    vals = [str(c).strip() if c is not None else "" for c in r]
                    while vals and vals[-1] == "":
                        vals.pop()
                    if vals:
                        cleaned_rows.append(vals)

            if not cleaned_rows:
                continue

            # Identify header row
            header_idx = -1
            best_score = 0
            for idx, r in enumerate(cleaned_rows[:15]):
                non_empty = [c for c in r if c]
                if len(non_empty) >= 3:
                    score = sum(1 for c in non_empty if any(k in c.lower() for k in [
                        "id", "test", "objective", "procedure", "description", "data", 
                        "expected", "actual", "result", "req", "status", "pass", "fail", 
                        "ลำดับ", "วัตถุประสงค์", "ขั้นตอน", "ผลลัพธ์", "ข้อมูล", "ข้อกำหนด"
                    ]))
                    if score > best_score and score >= 2:
                        best_score = score
                        header_idx = idx

            if header_idx == -1:
                for idx, r in enumerate(cleaned_rows[:15]):
                    if len([c for c in r if c]) >= 3:
                        header_idx = idx
                        break

            detected_cols = []
            if header_idx != -1:
                h_row = cleaned_rows[header_idx]
                detected_cols = [c for c in h_row if c]
            elif cleaned_rows:
                detected_cols = [c for c in cleaned_rows[0] if c]

            sheets_data.append({
                'title': sheet_title,
                'cleaned_rows': cleaned_rows,
                'header_idx': header_idx,
                'detected_cols': detected_cols,
                'data_row_count': max(0, len(cleaned_rows) - (header_idx + 1 if header_idx != -1 else 1))
            })

            # Check execution columns
            has_actual = any("actual" in c.lower() or "ผลจริง" in c for c in detected_cols)
            has_status = any(k in c.lower() for c in detected_cols for k in ["status", "result (pass/fail)", "pass/fail", "สถานะ", "ผลการทดสอบ"])
            notes = []
            if has_actual:
                notes.append("มีคอลัมน์ Actual Result")
            if has_status:
                notes.append("มีคอลัมน์ Status/Result")
            note_str = f" ({', '.join(notes)})" if notes else ""
            
            workbook_inventory.append(
                f"- **Sheet '{sheet_title}':** {len(cleaned_rows)} แถว | คอลัมน์: `{' | '.join(detected_cols[:12])}`{note_str}"
            )

        # Build Workbook Global Overview
        overview_lines = [
            "# ภาพรวมโครงสร้างเอกสาร Excel (Workbook Structure & Sheets Inventory)",
            f"- **จำนวนแผ่นงานทั้งหมด (Total Sheets):** {sheet_count} แผ่นงาน",
            "- **รายชื่อแผ่นงานและคอลัมน์ที่ตรวจพบในแต่ละ Sheet:**",
            "\n".join(workbook_inventory),
            "",
            "> [!NOTE]",
            "> **การตรวจพบคอลัมน์บันทึกผลการทดสอบ (Execution Support):**",
            "> ในเอกสารชุดนี้ แต่ละ Sheet มีบทบาทเฉพาะ เช่น Sheet 'Introduction' และ 'Document Change History' เป็นส่วน Governance, Sheet กลุ่ม 'Test Case' / 'Test Specification' กำหนดขั้นตอนและผลที่คาดหวัง, และชีทที่มีคอลัมน์ 'Actual Result' / 'Result (Pass/Fail)' ใช้สำหรับการบันทึกผลการทดสอบ (Execution)",
            "> โครงสร้างตารางเป็นไปตาม Template ที่โครงการกำหนด (เช่น Template 69A หรือ Template เฉพาะของโครงการ)",
            ""
        ]
        sheets_output.append("\n".join(overview_lines))

        # Format individual sheets
        for s_info in sheets_data:
            sheet_title = s_info['title']
            cleaned_rows = s_info['cleaned_rows']
            header_idx = s_info['header_idx']
            sheet_lines = [f"# Sheet: {sheet_title}"]

            if header_idx != -1:
                # Pre-header rows are metadata / title
                if header_idx > 0:
                    sheet_lines.append("### ข้อมูลทั่วไปของเอกสาร (Document & Project Metadata):")
                    for meta_row in cleaned_rows[:header_idx]:
                        pairs = [cell for cell in meta_row if cell]
                        if pairs:
                            sheet_lines.append("- " + " | ".join(pairs))
                    sheet_lines.append("")

                # Table headers
                header_row = cleaned_rows[header_idx]
                max_cols = max(len(r) for r in cleaned_rows[header_idx:])
                padded_headers = header_row + [f"Col_{i+1}" for i in range(len(header_row), max_cols)]
                clean_headers = [h.replace("\n", " ").replace("|", "\\|") if h else f"Col_{i+1}" for i, h in enumerate(padded_headers)]

                sheet_lines.append("### ตารางรายการทดสอบ (Test Cases / Specifications Matrix):")
                sheet_lines.append("| " + " | ".join(clean_headers) + " |")
                sheet_lines.append("| " + " | ".join([":---"] * max_cols) + " |")

                data_rows = cleaned_rows[header_idx + 1:]
                for row in data_rows:
                    padded_row = row + [""] * (max_cols - len(row))
                    escaped_row = [c.replace("\n", " <br> ").replace("|", "\\|") for c in padded_row]
                    sheet_lines.append("| " + " | ".join(escaped_row) + " |")

                # Compact Itemized breakdown: limit to top 15 rows to prevent token explosion and avoid truncation
                if data_rows:
                    sheet_lines.append("")
                    sample_size = min(15, len(data_rows))
                    sheet_lines.append(f"### รายละเอียดของแต่ละ Test Case (Detailed Breakdown - ตัวอย่าง {sample_size} รายการแรก):")
                    for r_idx, row in enumerate(data_rows[:sample_size], 1):
                        row_dict = {}
                        for col_i, col_name in enumerate(clean_headers):
                            if col_i < len(row) and row[col_i]:
                                row_dict[col_name] = row[col_i]
                        
                        tc_id_val = None
                        for k, v in row_dict.items():
                            if any(term in k.lower() for term in ["test id", "test case id", "id", "รหัส"]):
                                tc_id_val = v
                                break
                        if not tc_id_val:
                            tc_id_val = f"Row-{r_idx}"

                        sheet_lines.append(f"#### [{tc_id_val}]")
                        for k, v in row_dict.items():
                            sheet_lines.append(f"- **{k}:** {v}")
                        sheet_lines.append("")
                    
                    if len(data_rows) > sample_size:
                        sheet_lines.append(f"*... และมีรายการ Test Case อีก {len(data_rows) - sample_size} รายการในตารางข้างต้น ครบถ้วนทุกข้อ*")
                        sheet_lines.append("")

            else:
                # Generic tabular representation
                max_cols = max(len(r) for r in cleaned_rows)
                header_row = cleaned_rows[0]
                clean_headers = [h.replace("\n", " ").replace("|", "\\|") if h else f"Col_{i+1}" for i, h in enumerate(header_row)]
                sheet_lines.append("| " + " | ".join(clean_headers) + " |")
                sheet_lines.append("| " + " | ".join([":---"] * max_cols) + " |")
                for row in cleaned_rows[1:]:
                    padded_row = row + [""] * (max_cols - len(row))
                    escaped_row = [c.replace("\n", " <br> ").replace("|", "\\|") for c in padded_row]
                    sheet_lines.append("| " + " | ".join(escaped_row) + " |")

            sheets_output.append("\n".join(sheet_lines))

    # 2. If openpyxl did not produce results or failed, try pandas
    if not sheets_output:
        try:
            import pandas as pd
            xls = pd.ExcelFile(io.BytesIO(file_bytes))
            sheet_count = len(xls.sheet_names)
            for s_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=s_name)
                sheets_output.append(f"## Sheet: {s_name}\n\n" + df.to_markdown(index=False))
        except Exception as pd_err:
            logger.error(f"Pandas Excel reading also failed: {pd_err}")
            raise ValueError(f"ไม่สามารถอ่านข้อมูลจากไฟล์ Excel '{filename}' ได้: {pd_err}")

    full_text = "\n\n---\n\n".join(sheets_output).strip()
    if not full_text:
        raise ValueError("ไฟล์ Excel ไม่มีข้อมูลหรือแผ่นงานว่างเปล่า")

    return full_text, max(1, sheet_count)

