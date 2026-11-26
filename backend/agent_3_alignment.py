import json
import logging
import os
import re
from db_ingestion import get_db_connection
from gemini_utils import call_gemini, get_actual_model_for_usage
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _extract_json_object(raw_text: str) -> dict:
    s = (raw_text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", s)
    if fence:
        s = fence.group(1).strip()
    else:
        first = s.find("{")
        last = s.rfind("}")
        if first != -1 and last != -1 and last > first:
            s = s[first:last + 1]
    return json.loads(s, strict=False)


def run_alignment_analysis(project_id: str, web_state_file: str = None):
    """
    Agent 3: STLC Flow & Discrepancy / Alignment Agent
    - Pre-MCP mode (web_state_file is None): Analyzes Structured Requirements & QA Analysis Diagrams
      to validate E2E business flows, uncover requirement gaps/ambiguities, and guide Test Case & MCP play.
    - Post-MCP mode (web_state_file exists): Compares Requirements & Diagrams directly against Live Web State.
    """
    try:
        # 1. Get Requirements from DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT req_code, title, description, steps, expected_results, ui_elements
            FROM structured_requirements
            WHERE project_id = %s::uuid
            ORDER BY req_code ASC
        """, (project_id,))

        reqs = cursor.fetchall()
        cursor.close()
        conn.close()

        if not reqs:
            return False, "ไม่พบ Structured Requirements ในโครงการนี้ กรุณาสกัด Requirement ใน Phase 1 ก่อน"

        formatted_reqs = []
        for req in reqs:
            formatted_reqs.append({
                "req_code": req[0],
                "title": req[1],
                "description": (req[2] or "")[:400],
                "steps": req[3],
                "expected_results": req[4],
                "ui_elements": req[5]
            })

        # 2. Optional Live Web State (if user already ran Playwright MCP)
        web_state = None
        has_live_web = bool(web_state_file and os.path.exists(web_state_file))
        if has_live_web:
            with open(web_state_file, 'r', encoding='utf-8') as f:
                web_state = json.load(f)

        # 3. Optional: Fetch QA Analysis Diagram / Flow Data if available
        diagram_context = ""
        try:
            from agent_7_flow_analyzer import get_project_flow_analysis
            flow_analysis = get_project_flow_analysis(project_id)
            if flow_analysis:
                diagram_parts = []
                if flow_analysis.get("sitemap"):
                    diagram_parts.append(f"- **Sitemap & Menu Structure:**\n{json.dumps(flow_analysis['sitemap'], ensure_ascii=False, indent=2)}")
                if flow_analysis.get("system_flowchart") or flow_analysis.get("activity_diagram"):
                    fc = flow_analysis.get("system_flowchart") or flow_analysis.get("activity_diagram")
                    diagram_parts.append(f"- **System Flowchart & Activity Decision Flow (Mermaid):**\n{fc}")
                if flow_analysis.get("usecase_diagram"):
                    diagram_parts.append(f"- **Use Case Architecture (Mermaid):**\n{flow_analysis['usecase_diagram']}")
                if flow_analysis.get("sequence_diagram"):
                    diagram_parts.append(f"- **Sequence Flow (Mermaid):**\n{flow_analysis['sequence_diagram']}")
                if flow_analysis.get("screen_mockups"):
                    screens = [
                        {"screen_name": s.get("screen_name"), "route": s.get("route"), "key_elements": s.get("key_elements", [])}
                        for s in flow_analysis["screen_mockups"] if isinstance(s, dict)
                    ]
                    if screens:
                        diagram_parts.append(f"- **Screen Mockups & Expected Components:**\n{json.dumps(screens, ensure_ascii=False, indent=2)}")

                if diagram_parts:
                    diagram_context = "\n\n### QA Analysis Diagram & Architecture Models:\n" + "\n\n".join(diagram_parts)
                    logger.info(f"Incorporated QA Analysis Diagram into Alignment for project {project_id}")
        except Exception as diagram_err:
            logger.warning(f"Optional QA Analysis Diagram fetch skipped: {diagram_err}")

        if has_live_web:
            mode_label = "live_web_alignment"
            task_intro = (
                "งานของคุณคือเปรียบเทียบ 'Structured Requirements' และ 'QA Analysis Diagram' "
                "กับ 'Live Web State' ที่สำรวจได้จากหน้าเว็บจริง เพื่อระบุจุดที่ตรงกันและจุดต่าง (Gap / Discrepancy)"
            )
            web_section = f"\n### Live Web State (Actual จาก Playwright MCP):\n{json.dumps(web_state, ensure_ascii=False, indent=2)[:25000]}"
            matched_desc = "รายการองค์ประกอบ UI หรือ Flow บนหน้าเว็บจริงที่ตรงกับ Requirement"
            issue_desc = "รายละเอียดจุดที่ไม่ตรงหรือขาดหายบนหน้าเว็บจริง (ภาษาไทย)"
        else:
            mode_label = "stlc_pre_test_analysis"
            task_intro = (
                "งานของคุณคือทำ **STLC Test Analysis (Flow & Gap Analysis)** จาก 'Structured Requirements' "
                "และ 'QA Analysis Diagram' ก่อนเข้าสู่ขั้นตอนออกแบบ Test Case และเล่นเว็บจริงด้วย Playwright MCP "
                "เพื่อสรุป Core End-to-End Business Flows ที่ครบถ้วน, ค้นหาช่องโหว่/เงื่อนไขที่คลุมเครือ/Edge Cases ที่ขาดหายใน Requirement, "
                "และแนะนำ Flow ลำดับการทำงานที่ต้องให้ Playwright MCP เข้าไปทดสอบจริง"
            )
            web_section = "\n### สถานะการสำรวจหน้าเว็บจริง (MCP): ยังไม่ได้รัน (กำลังวิเคราะห์ Flow & Gap ก่อนสร้าง Test Case ตามมาตรฐาน STLC)"
            matched_desc = "Core Business Flow หรือเงื่อนไขที่ชัดเจนพร้อมนำไปออกแบบ Test Case และรันผ่าน MCP"
            issue_desc = "ช่องว่าง (Gap), เงื่อนไขที่ยังไม่ชัดเจน, Edge Case หรือจุดเสี่ยงด้าน Business Rules ที่ควรระวังก่อนเขียน Test Case (ภาษาไทย)"

        prompt = f"""คุณคือ Expert QA Automation Architect และ Senior System Analyst
{task_intro}

กฎ: ตอบเป็นภาษาไทยที่กระชับชัดเจน (คงชื่อปุ่ม/ฟิลด์/รหัสหน้าจอ/รหัส REQ ตามจริง) และตอบกลับเป็น JSON เท่านั้น

### Structured Requirements ({len(formatted_reqs)} รายการ):
{json.dumps(formatted_reqs[:60], ensure_ascii=False, indent=2)}
{diagram_context}
{web_section}

ตอบกลับเป็น JSON ตามโครงสร้างนี้เท่านั้น:
{{
    "analysis_mode": "{mode_label}",
    "analysis_summary": "สรุปภาพรวมผลการวิเคราะห์ Flow และความพร้อมก่อนสร้าง Test Case/Automate (ภาษาไทย)",
    "matched_elements": [
        "{matched_desc}"
    ],
    "discrepancies": [
        {{
            "req_code": "รหัส Requirement เช่น FR-CL-01",
            "issue": "{issue_desc}",
            "severity": "High | Medium | Low"
        }}
    ],
    "recommendation": "แนวทางการออกแบบ Test Case และลำดับ Flow ที่ควรให้ Playwright MCP เข้าเล่นจริงใน Phase 3 (ภาษาไทย)"
}}
"""
        model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        text_response, usage_metadata = call_gemini(prompt, model_name=model_name)

        if usage_metadata:
            try:
                from db_ingestion import log_api_usage
                actual_model = get_actual_model_for_usage(model_name)
                log_api_usage("Agent_3_Alignment", actual_model, usage_metadata)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Agent 3: {log_err}")

        analysis_result = _extract_json_object(text_response)
        if isinstance(analysis_result, dict) and not analysis_result.get("analysis_mode"):
            analysis_result["analysis_mode"] = mode_label
        return True, analysis_result

    except Exception as e:
        logger.error(f"Error in Agent 3 Alignment: {e}", exc_info=True)
        return False, str(e)
