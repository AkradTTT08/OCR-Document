"""Shared QA text parsing, Buddhist-Era date validation, and page attribution helpers."""
import logging
import re

logger = logging.getLogger(__name__)


def _is_false_future_be_date_claim(claim_text: str, doc_text: str = "") -> bool:
    """
    Detect false-positive 'future date' claims where the document actually uses valid past/present
    Thai Buddhist Era (พ.ศ. / B.E., e.g. 2566-2569) dates that AI mistakenly read as A.D. (ค.ศ.).
    """
    import re
    from datetime import date, datetime
    txt = str(claim_text or "").strip()
    if not txt:
        return False
    low = txt.lower()
    is_future_claim = any(kw in low for kw in [
        "อนาคต", "future date", "in the future", "ยังไม่ถึง", "ล่วงหน้า", "เป็นปีอนาคต", "วันที่ผิดปกติ"
    ])
    if not is_future_claim:
        return False

    today = datetime.now().date()
    cur_be_year = today.year + 543

    # Check explicit 4-digit BE years (2400-2700) in the claim text first
    be_years_in_claim = [int(y) for y in re.findall(r'\b(2[456]\d{2})\b', txt)]
    if be_years_in_claim:
        # If every mentioned BE year converts to <= today's AD year (and if exact DD/MM/YYYY BE date is <= today)
        all_valid_past_or_present = True
        for y in be_years_in_claim:
            if y > cur_be_year:
                all_valid_past_or_present = False
                break
        if not all_valid_past_or_present:
            return False
        # Verify exact DD/MM/YYYY or YYYY-MM-DD dates in claim if present
        dm_matches = re.findall(r'\b(\d{1,2})[/\-](\d{1,2})[/\-](2[456]\d{2})\b', txt)
        for d_s, m_s, y_s in dm_matches:
            try:
                ad_dt = date(int(y_s) - 543, int(m_s), int(d_s))
                if ad_dt > today:
                    return False
            except ValueError:
                pass
        return True

    # If the claim complains about Updated Date / Revision History being in the future without quoting the year,
    # check if the document itself uses valid past/present Thai BE years (25xx <= cur_be_year) and no true future AD years
    if doc_text and any(kw in low for kw in ["updated date", "revision history", "วันที่", "date", "เมตาเดตา", "metadata"]):
        doc_be_years = [int(y) for y in re.findall(r'\b(25\d{2})\b', doc_text[:15000])]
        if doc_be_years and all(y <= cur_be_year for y in doc_be_years):
            return True

    return False


def _filter_false_future_be_date_findings(qa_findings: list, doc_text: str = "") -> list:
    """Remove false-positive 'future date' findings caused by Thai Buddhist Era (พ.ศ.) dates."""
    if not qa_findings or not isinstance(qa_findings, list):
        return qa_findings or []
    filtered = []
    for f in qa_findings:
        if not isinstance(f, dict):
            filtered.append(f)
            continue
        combined = " ".join([
            str(f.get("issue") or ""),
            str(f.get("found_incorrect") or ""),
            str(f.get("recommendation") or ""),
            str(f.get("correct_value") or ""),
        ])
        if _is_false_future_be_date_claim(combined, doc_text=doc_text):
            logger.info(f"Filtered false-positive future-date finding for valid BE (พ.ศ.) date: {f.get('issue')}")
            continue
        filtered.append(f)
    return filtered


def _split_text_into_logical_pages(raw_text: str, filename: str = "", chunk_size: int = 2600) -> list[dict]:
    """Split extracted text into numbered pages so AI and Document Inspector can pinpoint locations."""
    import re
    text = (raw_text or "").replace("\r\n", "\n").strip()
    if not text:
        return []

    explicit_matches = list(re.finditer(r'(?m)^---\s*\[(?:หน้า|Page)\s+(\d+)(?:\s*:\s*([^\]]+))?\]\s*---\s*$', text))
    if explicit_matches:
        pages = []
        for idx, m in enumerate(explicit_matches):
            p_num = int(m.group(1))
            custom_lbl = (m.group(2) or "").strip()
            start = m.end()
            end = explicit_matches[idx + 1].start() if idx + 1 < len(explicit_matches) else len(text)
            pages.append({"page_number": p_num, "label": custom_lbl or f"หน้า {p_num}", "text": text[start:end].strip(), "has_image": False})
        return pages

    sheet_matches = list(re.finditer(r'(?m)^(?:===|#{1,3})\s*(?:Sheet|แผ่นงาน)\s*[:\-]?\s*([^\n=]+?)\s*(?:===)?\s*$', text, re.I))
    if sheet_matches:
        pages = []
        for idx, m in enumerate(sheet_matches):
            s_name = m.group(1).strip()
            start = m.start()
            end = sheet_matches[idx + 1].start() if idx + 1 < len(sheet_matches) else len(text)
            pages.append({"page_number": idx + 1, "label": f"Sheet: {s_name}", "text": text[start:end].strip(), "has_image": False})
        return pages

    paragraphs = re.split(r'\n{2,}', text)
    pages, buf, buf_len = [], [], 0
    for para in paragraphs:
        is_major_heading = bool(re.match(r'^#{1,2}\s+\S', para.strip()))
        if buf and (buf_len + len(para) > chunk_size or (is_major_heading and buf_len > chunk_size * 0.45)):
            p_num = len(pages) + 1
            pages.append({"page_number": p_num, "label": f"หน้า {p_num}", "text": "\n\n".join(buf).strip(), "has_image": False})
            buf, buf_len = [para], len(para)
        else:
            buf.append(para)
            buf_len += len(para) + 2
    if buf:
        p_num = len(pages) + 1
        pages.append({"page_number": p_num, "label": f"หน้า {p_num}", "text": "\n\n".join(buf).strip(), "has_image": False})
    return pages


def _attach_finding_pages(qa_findings: list[dict], pages_list: list[dict]) -> list[dict]:
    """Deterministically resolve page_number, page_label, and highlight_snippet for every QA finding."""
    import re
    if not qa_findings or not isinstance(qa_findings, list):
        return []
    total = len(pages_list)
    page_by_num = {int(p["page_number"]): p for p in pages_list if p.get("page_number")}
    norm_pages = [
        (int(p["page_number"]), p.get("label") or f"หน้า {p['page_number']}", re.sub(r'\s+', ' ', (p.get("text") or "")).lower())
        for p in pages_list
    ]

    def _extract_page_num_from_text(val):
        if not val:
            return None
        m = re.search(r'(?:หน้า|page|p\.)\s*[:#]?\s*(\d+)', str(val), re.I)
        if m:
            n = int(m.group(1))
            if 1 <= n <= max(total, 1):
                return n
        return None

    enriched = []
    for idx, raw_f in enumerate(qa_findings):
        f = dict(raw_f) if isinstance(raw_f, dict) else {"issue": str(raw_f)}
        f["finding_index"] = idx

        resolved_page = None
        raw_pn = f.get("page_number")
        if isinstance(raw_pn, int) and 1 <= raw_pn <= total:
            resolved_page = raw_pn
        elif isinstance(raw_pn, str) and raw_pn.strip().isdigit():
            cand = int(raw_pn.strip())
            if 1 <= cand <= total:
                resolved_page = cand

        if resolved_page is None:
            resolved_page = _extract_page_num_from_text(f.get("document_page")) or _extract_page_num_from_text(f.get("issue"))

        if resolved_page is None and f.get("document_page"):
            dp_low = str(f.get("document_page")).lower()
            for pn, lbl, _ in norm_pages:
                clean_lbl = lbl.replace("Sheet:", "").strip().lower()
                if clean_lbl and len(clean_lbl) >= 2 and clean_lbl in dp_low:
                    resolved_page = pn
                    break

        snippet = str(f.get("found_incorrect") or "").strip()
        clean_snippet = re.sub(r'^[\"\'\`“”]+|[\"\'\`“”]+$', '', snippet).strip()
        if clean_snippet in ("-", "ไม่มี", "N/A", "n/a", "ไม่ระบุ"):
            clean_snippet = ""

        if resolved_page is None and clean_snippet and len(clean_snippet) >= 4:
            norm_snip = re.sub(r'\s+', ' ', clean_snippet).lower()
            for pn, _, ntext in norm_pages:
                if norm_snip in ntext:
                    resolved_page = pn
                    break
            if resolved_page is None and len(norm_snip) >= 12:
                parts = [pt.strip() for pt in re.split(r'[,;\n\|/()]+', norm_snip) if len(pt.strip()) >= 8]
                parts.sort(key=len, reverse=True)
                for pt in parts[:4]:
                    for pn, _, ntext in norm_pages:
                        if pt in ntext:
                            resolved_page = pn
                            break
                    if resolved_page is not None:
                        break
            if resolved_page is None:
                tokens = [t for t in re.findall(r'[a-zA-Z0-9\u0E00-\u0E7F]{3,}', norm_snip) if len(t) >= 3][:10]
                if len(tokens) >= 2:
                    best_pn, best_score = None, 0
                    for pn, _, ntext in norm_pages:
                        hits = sum(1 for t in tokens if t in ntext)
                        if hits > best_score and hits >= max(2, len(tokens) // 2):
                            best_score = hits
                            best_pn = pn
                    resolved_page = best_pn

        f["page_number"] = resolved_page
        if resolved_page and resolved_page in page_by_num:
            f["page_label"] = page_by_num[resolved_page].get("label") or f"หน้า {resolved_page}"
            if not f.get("document_page") or str(f.get("document_page")).strip().lower().endswith((".pdf", ".xlsx", ".md", ".txt")):
                f["document_page"] = f["page_label"]
        else:
            f["page_label"] = "ภาพรวมทั้งเอกสาร"

        f["highlight_snippet"] = clean_snippet
        enriched.append(f)
    return enriched


def _build_page_issue_summary(qa_findings: list[dict], pages_list: list[dict]) -> dict:
    """Build per-page error counters so the UI can focus the user directly on pages with issues."""
    by_page = {}
    for p in pages_list:
        pn = int(p["page_number"])
        by_page[pn] = {
            "page_number": pn,
            "label": p.get("label") or f"หน้า {pn}",
            "total_issues": 0,
            "critical_high": 0,
            "medium": 0,
            "low_info": 0,
            "has_image": bool(p.get("has_image"))
        }

    global_issues = 0
    for f in (qa_findings or []):
        pn = f.get("page_number")
        sev = str(f.get("severity") or "info").lower()
        if pn and int(pn) in by_page:
            slot = by_page[int(pn)]
            slot["total_issues"] += 1
            if sev in ("critical", "high"): slot["critical_high"] += 1
            elif sev == "medium": slot["medium"] += 1
            else: slot["low_info"] += 1
        else:
            global_issues += 1

    pages_ordered = [by_page[k] for k in sorted(by_page.keys())]
    error_pages = [p for p in pages_ordered if p["total_issues"] > 0]
    return {
        "total_pages": len(pages_ordered),
        "pages_with_issues_count": len(error_pages),
        "global_issues_count": global_issues,
        "pages": pages_ordered
    }

