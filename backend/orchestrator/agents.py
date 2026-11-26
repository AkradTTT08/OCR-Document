import os
import logging
from spell_checker import spellcheck_text
from format_checker import check_format_rules
from .state import DocumentState

logger = logging.getLogger(__name__)

class SpellCheckerAgent:
    @staticmethod
    def run(state: DocumentState) -> DocumentState:
        """Agent 1: Detects spelling and semantic errors."""
        logger.info("Running SpellCheckerAgent...")
        state.status = "spellcheck"
        result = spellcheck_text(state.original_text, include_suggestions=True, lang=getattr(state, 'lang', 'tha+eng'))
        state.spell_errors = result.get('errors', [])
        state.tokens = result.get('tokens', [])
        state.summary = result.get('summary', {})
        return state

class FormatCheckerAgent:
    @staticmethod
    def run(state: DocumentState) -> DocumentState:
        """Agent 2: Detects formatting errors using regex rules."""
        logger.info("Running FormatCheckerAgent...")
        state.status = "formatcheck"
        format_errors = check_format_rules(state.original_text)
        state.format_errors = format_errors
        return state

class FinalReviewerAgent:
    @staticmethod
    def run(state: DocumentState) -> DocumentState:
        """Agent 3: Evaluates the combined findings and produces a final review summary."""
        logger.info("Running FinalReviewerAgent...")
        state.status = "review"
        
        try:
            from ocr_engine import get_all_api_keys, _get_gemini_client
            from google.genai import types
            
            keys = get_all_api_keys()
            if not keys:
                state.final_review_summary = "No API keys available for final review."
                return state

            client = _get_gemini_client(0)
            model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
            
            system_prompt = """You are the Final Reviewer Agent in a multi-agent pipeline.
Your job is to read the original document text, along with the reported spelling and format errors.
Provide a very concise executive summary (1-3 sentences) in Thai evaluating the overall quality of the text based on these findings."""

            prompt_content = f"Original Text:\n{state.original_text}\n\n"
            
            # Summarize spell errors for the prompt
            if state.spell_errors:
                spell_err_str = ", ".join([e.get('token', '') for e in state.spell_errors])
                prompt_content += f"Spell Errors ({len(state.spell_errors)}): {spell_err_str}\n\n"
            else:
                prompt_content += "Spell Errors: None\n\n"
                
            # Summarize format errors for the prompt
            if state.format_errors:
                fmt_err_str = ", ".join([e.get('token', '') for e in state.format_errors])
                prompt_content += f"Format Errors ({len(state.format_errors)}): {fmt_err_str}\n\n"
            else:
                prompt_content += "Format Errors: None\n\n"

            prompt_content += "Please provide the final review summary."

            response = client.models.generate_content(
                model=model_name,
                contents=prompt_content,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                )
            )
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                try:
                    from db_ingestion import log_api_usage
                    log_api_usage("FinalReviewer_Agent", model_name, response.usage_metadata)
                except Exception as log_err:
                    logger.warning(f"Failed to log API usage in FinalReviewer: {log_err}")

            state.final_review_summary = response.text.strip()
            
        except Exception as e:
            logger.error(f"FinalReviewer error: {e}")
            state.final_review_summary = "Failed to generate final review summary."
            
        return state

class QAConsultAgent:
    @staticmethod
    def run(state: 'QAState') -> 'QAState':
        """Agent for QA Consult (Gap Analysis & SRS Check)"""
        logger.info("Running QAConsultAgent...")
        state.status = "running"
        
        try:
            from ocr_engine import get_all_api_keys, _get_gemini_client
            from google.genai import types
            
            keys = get_all_api_keys()
            if not keys:
                state.error = "No API keys available."
                state.status = "failed"
                return state
                
            client = _get_gemini_client(0)
            gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
            
            from datetime import datetime
            now_dt = datetime.now()
            cur_ad_year = now_dt.year
            cur_be_year = now_dt.year + 543
            cur_date_ad = now_dt.strftime('%d/%m/%Y')
            cur_date_be = f"{now_dt.day:02d}/{now_dt.month:02d}/{cur_be_year}"

            skill_section = f"--- คำสั่งพิเศษเพิ่มเติมจาก AI Skill ---\n{state.skill_instructions}\n" if state.skill_instructions else ""
            
            prompt = f"""คุณคือผู้เชี่ยวชาญด้านระบบสารสนเทศ และ System QA (Quality Assurance)
หน้าที่ของคุณคือตรวจสอบและเปรียบเทียบความถูกต้องของ 'เอกสารที่อัปโหลด' กับ 'ข้อมูลมาตรฐาน' ที่มีอยู่ในฐานข้อมูล (Knowledge Base ของโครงการ {state.project_name})

วันที่ปัจจุบันของระบบ (Current Reference Date): {cur_date_ad} (ค.ศ. {cur_ad_year}) / {cur_date_be} (พ.ศ. {cur_be_year})
ประเภทของเอกสารที่กำลังตรวจสอบ: {state.doc_type}

{skill_section}

=== ข้อมูลมาตรฐานจากฐานข้อมูล {state.project_name} ===
{state.kb_context if state.kb_context else 'ไม่พบข้อมูลที่ตรงกันเป๊ะในระบบ (โปรดประเมินจากความรู้ทั่วไปหรือโครงสร้างเอกสาร)'}
{state.prev_report_context}
=== เอกสารที่ผู้ใช้อัปโหลด ===
{state.original_text}

=== ข้อสั่งการในการตรวจสอบและรายงานผล (Audit Directives) ===
1. ให้ตรวจสอบเนื้อหาของ 'เอกสารที่ผู้ใช้อัปโหลด' อย่างละเอียดครบถ้วนทุกหน้า ทุก Section ตั้งแต่ต้นจนจบเอกสาร
2. หากเอกสารเป็นฉบับปรับปรุง (Revision/Refined Document): ให้ตรวจสอบว่าข้อบกพร่องเดิมจากรอบก่อนได้รับการแก้ไขแล้วหรือไม่ หากในเนื้อหาเอกสารที่ส่งตรวจมีข้อมูลครบถ้วนแล้ว (เช่น มีโครงสร้าง Acceptance Criteria Given/When/Then, มี Unhappy Path & Error Handling, หรือมีตารางตามมาตรฐานของเอกสารประเภทนั้นๆ) **ห้ามรายงานเป็นข้อผิดพลาดใหม่โดยเด็ดขาด** ให้ระบุในรายงานว่า "ปัญหาเดิมได้รับการปรับปรุงแก้ไขเรียบร้อยแล้ว (Resolved)"
3. จัดทำรายการข้อบกพร่องเฉพาะจุดที่ยังผิดพลาด ตกหล่น หรือขัดแย้งอยู่จริงในเนื้อหาเอกสารฉบับนี้เท่านั้น
4. การตรวจสอบ Metadata และความสอดคล้องของเอกสาร:
   - ตราประทับแพลตฟอร์มสังเคราะห์เอกสารอัตโนมัติ (เช่น 'QA ENTERPRISE' หรือ System Header/Footer) ถือเป็น System Template ทางเทคนิค ห้ามนำข้อความชื่อเครื่องมือ/ระบบ ไปตัดสินขัดแย้งกับข้อมูลทางการใน Section 1 (ตาราง Document Control) ที่ระบุผู้จัดทำ (Author) หรือ Version ของเอกสาร
   - หากใน Section 1 Document Control มี Document Title, Version Number, Baseline Date และชื่อผู้จัดทำ (Author) ครบถ้วนชัดเจน ให้ถือว่าสอดคล้องสมบูรณ์ตามมาตรฐาน Governance
5. การเขียนสูตรคณิตศาสตร์และตัวแปร:
   - หากสูตรคำนวณหรือสมการทางเทคนิค มีการเขียนสมการและระบุความหมายของตัวแปรไว้อย่างชัดเจนโดยไม่ใช้สัญลักษณ์ LaTeX '$' ถือว่ามีความชัดเจนและได้มาตรฐาน ให้ผ่านเกณฑ์
6. การตรวจสอบเอกสาร Test Case และแบบฟอร์มเฉพาะของโครงการ (Template Specifics):
   - หากเอกสารเป็น Test Case หรือมีการใช้แบบฟอร์มเฉพาะของโครงการ (เช่น Template 69A หรือตารางโครงสร้างที่มี Test Step, Expected Result ครบถ้วน):
     * ห้ามรายงานว่าขาดคอลัมน์ Actual Result หรือ Status เป็นข้อผิดพลาด (Defect) เนื่องจากในระยะการจัดทำ Test Case Specification หรือ Test Design เฟสแรก จะเน้นขั้นตอนการทดสอบ (Test Steps) และผลที่คาดหวัง (Expected Results) ส่วนผลการทดสอบจริง (Execution) จะถูกบันทึกเมื่อดำเนินการทดสอบระบบ
     * หากในบางชีทมีคอลัมน์ผลทดสอบ หรือบางชีทใช้โครงสร้างตาม Template ของโครงการที่ผู้ใช้/โครงการกำหนดไว้ ให้ยอมรับโครงสร้างดังกล่าว และห้ามตัดสินเป็น Defect ระดับ Critical/High/Medium
     * ห้ามนำข้อความใน Document Change History ที่บันทึกการตัดสินใจทางวิศวกรรม (เช่น การปฏิเสธคอลัมน์ที่ซ้ำซ้อนหรือไม่จำเป็นตามข้อตกลงของโครงการ) มาตัดสินว่าเป็นข้อผิดพลาดหรือข้อบกพร่องที่ต้องแก้ไข
7. การตรวจสอบความสอดคล้องกับขอบเขตโครงการ (Strict Project Scope & Domain Isolation):
   - ต้องตรวจสอบเนื้อหาเอกสารเทียบกับ Knowledge Base และข้อกำหนดของโครงการ {state.project_name} โดยตรงเท่านั้น
   - ห้ามเรียกร้องหรือกำหนดให้เอกสารต้องมีฟีเจอร์, ตรรกะ หรือระบบงานของโครงการอื่นที่ไม่เกี่ยวข้องกับขอบเขตงานของโครงการ {state.project_name} โดยเด็ดขาด
8. การตรวจสอบวันที่ระบบพุทธศักราช (พ.ศ. / B.E.) และคริสต์ศักราช (ค.ศ. / A.D.) — **สำคัญมาก**:
   - วันปัจจุบันคือ **{cur_date_ad} (ค.ศ. {cur_ad_year})** ซึ่งตรงกับ **{cur_date_be} (พ.ศ. {cur_be_year})**
   - เอกสารไทยสามารถใช้วันที่แบบ **พ.ศ.** (เช่น `2567`, `2568`, `2569` หรือรูปแบบย่อ 2 หลัก เช่น `67`, `68`, `69`) หรือ **ค.ศ.** (เช่น `2024`, `2025`, `2026`) ได้ทั้งคู่
   - **วิธีแปลง พ.ศ. → ค.ศ. ก่อนตรวจสอบเสมอ:** หากปีในเอกสารอยู่ช่วง `2400–2700` ให้ถือว่าเป็น **ปี พ.ศ.** และนำมาลบด้วย `543` เพื่อแปลงเป็น ค.ศ. (เช่น `พ.ศ. 2568 = ค.ศ. 2025`, `พ.ศ. 2569 = ค.ศ. 2026`)
   - **ห้ามแจ้งว่าวันที่ พ.ศ. ที่เป็นอดีตหรือวันปัจจุบัน (<= {cur_date_be} พ.ศ. {cur_be_year}) เป็น "วันที่ในอนาคต" โดยเด็ดขาด** ให้รายงานเป็นข้อผิดพลาดเรื่องวันที่ในอนาคตเฉพาะกรณีที่แปลงเป็น ค.ศ. แล้วมากกว่า `{cur_date_ad}` จริงๆ เท่านั้น
9. **ข้อบังคับการระบุหมายเลขหน้าและตำแหน่งที่ชัดเจน (Strict Page & Location Pinpointing — ห้ามคลุมเครือ):**
   - เนื้อหาเอกสารมีการแบ่งหน้าชัดเจนด้วย `--- [หน้า N] ---`
   - **ทุกข้อผิดพลาด ข้อขัดแย้ง คำผิด หรือข้อมูลที่ขาดหาย ต้องระบุ `[หน้า N]` และตำแหน่งที่ชัดเจนเสมอ** เช่น `[หน้า 1 | ตาราง Document Control]`, `[หน้า 4 | หัวข้อ 2.2 ตาราง Test Case แถว TC-005 คอลัมน์ Test Data]`
   - แม้เป็นข้อมูลที่ขาดหาย (Missing Information) ให้ระบุหน้าและหัวข้อที่ควรเพิ่มลงไปชัดเจน (เช่น ขาดชื่อผู้ทดสอบ/วันที่ → `[หน้า 1 | ส่วนหัวเอกสาร / Document Control]`) **ห้ามเขียนแบบคลุมเครือ** ว่า "ภาพรวมทั้งเอกสาร" หรือ "ในเอกสาร" โดยไม่ชี้จุดแก้ไข

{state.instruction}
"""
            
            # QA Consult uses Gemini 3.1 Pro Preview as primary model (other menus keep GEMINI_MODEL from config)
            qa_consult_primary = os.environ.get('QA_CONSULT_MODEL', 'gemini-3.1-pro-preview')
            raw_fallback_models = [qa_consult_primary, 'gemini-3.1-pro-preview', 'gemini-2.5-pro', gemini_model, 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
            seen = set()
            fallback_models = [m for m in raw_fallback_models if m and not (m in seen or seen.add(m))]
            
            response = None
            last_model_err = None
            for key_idx in range(len(keys)):
                client = _get_gemini_client(key_idx)
                for current_model in fallback_models:
                    try:
                        logger.info(f"QAConsultAgent: Calling model {current_model}...")
                        response = client.models.generate_content(
                            model=current_model,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                temperature=0.2,
                            )
                        )
                        if response and response.text:
                            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                                try:
                                    from db_ingestion import log_api_usage
                                    log_api_usage("QAConsult_Agent", current_model, response.usage_metadata)
                                except Exception as log_err:
                                    logger.warning(f"Failed to log API usage in QAConsult: {log_err}")
                            break
                    except Exception as model_err:
                        last_model_err = model_err
                        err_str = str(model_err)
                        logger.warning(f"QAConsultAgent error with {current_model}: {err_str}")
                        # Short-circuit futile model retries on the same key when billing/credits are depleted (402) or key is invalid
                        if '402' in err_str or 'prepayment credits are depleted' in err_str.lower() or 'API_KEY_INVALID' in err_str:
                            break
                        continue
                if response and response.text:
                    break
                    
            if not response or not response.text:
                detail = f" ({last_model_err})" if last_model_err else ""
                raise Exception(f"All Gemini models failed in QAConsultAgent.{detail}")
                
            state.report = response.text
            state.final_report = response.text
            state.status = "completed"
            
        except Exception as e:
            logger.error(f"QAConsultAgent error: {e}")
            state.error = str(e)
            state.status = "failed"
            
        return state

class QAResearchAgent:
    RESEARCH_MODE_DIRECTIVES = {
        "deep_research": (
            "โหมด: 🔍 Deep QA Research (วิเคราะห์เจาะลึกทุกมิติ)\n"
            "- วิเคราะห์คำถามอย่างละเอียดครบถ้วนจากเอกสารทุกแหล่ง (SRS, Test Case, QA Consult Findings, Diagram, Automation)\n"
            "- สรุปเป็นโครงสร้างที่ชัดเจน มีตารางเปรียบเทียบ (Markdown Table) และระบุ Citation ทุกหัวข้อ"
        ),
        "gap_risk_audit": (
            "โหมด: ⚠️ Gap & Risk Audit (ตรวจหาช่องโหว่ ข้อขัดแย้ง และความเสี่ยง)\n"
            "- โฟกัสการเปรียบเทียบ Requirement vs Test Cases vs QA Consult Findings vs Sitemap/Flowchart\n"
            "- ชี้จุดที่ข้อมูลไม่ตรงกัน, Requirement ที่ยังไม่มี Test Case รองรับ, เงื่อนไข Error/Edge Case ที่ขาดหายไป พร้อมจัดระดับความเสี่ยง (High / Medium / Low) เป็นตาราง"
        ),
        "test_brainstorm": (
            "โหมด: 🧪 Test Scenario & Edge Case Brainstorm\n"
            "- ออกแบบชุดกรณีทดสอบ (Positive, Negative, Boundary, Security, Permission) โดยอ้างอิงจาก Business Rules จริงในเอกสาร\n"
            "- แสดงผลเป็นตาราง Markdown ที่มีคอลัมน์: TC-ID | ประเภท | ขั้นตอนย่อ | ข้อมูลทดสอบ | ผลลัพธ์ที่คาดหวัง | อ้างอิง REQ"
        ),
        "impact_analysis": (
            "โหมด: 🔄 Business & Change Impact Analysis\n"
            "- วิเคราะห์ผลกระทบหากมีการแก้ไขฟีเจอร์หรือเงื่อนไขที่ผู้ใช้ถาม ว่ากระทบหน้าจอ/Sitemap ใด, API ใด, Requirement ข้อใด และ Test Case ชุดใดที่ต้องรัน Regression ใหม่"
        ),
        "quick_lookup": (
            "โหมด: ⚡ Quick Fact Lookup (คำตอบกระชับตรงประเด็น)\n"
            "- ตอบสั้น กระชับ ตรงคำถามที่สุดเป็น Bullet Points หรือตารางสั้นๆ พร้อมระบุ `[อ้างอิง: ชื่อไฟล์]` ทันที"
        ),
    }

    @staticmethod
    def _build_prompt_and_system(state: 'QAState'):
        mode_key = (getattr(state, 'doc_type', None) or 'deep_research').strip().lower()
        mode_directive = QAResearchAgent.RESEARCH_MODE_DIRECTIVES.get(
            mode_key, QAResearchAgent.RESEARCH_MODE_DIRECTIVES["deep_research"]
        )

        system_instruction = f"""คุณคือ Rainbow 🌈 ผู้เชี่ยวชาญด้าน QA Research & Requirements Intelligence ประจำระบบ 'Spectra QA'
หน้าที่หลักของคุณคือ: ตอบคำถามและวิเคราะห์ข้อมูลเกี่ยวกับโครงการ "{state.project_name or 'N/A'}" (รหัสโครงการ: {state.project_code or state.project_id}) อย่างแม่นยำ ละเอียด ลึกซึ้ง และถูกต้อง 100% โดยอ้างอิงจากคลังข้อมูล (Knowledge Base), เอกสารความต้องการ (Requirements), SRS, Test Cases, ผลตรวจ QA Consult, ผัง QA Analysis Diagram และเอกสารที่อัปโหลดทั้งหมด

### คำสั่งเฉพาะสำหรับโหมดการค้นคว้าปัจจุบัน:
{mode_directive}

กฎเหล็กในการค้นหาและตอบคำถาม (QA Accuracy & Grounding Rules):
1. ความแม่นยำและการอ้างอิง (Grounding & Citations):
   - ให้ยึดข้อมูลจาก CONTEXT FROM KNOWLEDGE BASE เป็นหลักความจริงสูงสุด ห้ามคาดเดาหรือสร้างข้อมูลขึ้นมาเอง (Zero Hallucination)
   - ระบุแหล่งที่มาของข้อมูลเสมอเมื่อกล่าวถึงข้อกำหนด เช่น `[อ้างอิง: ชื่อไฟล์]` หรือ `[ความต้องการ: REQ-XXX]`
2. รูปแบบคำตอบที่ชัดเจน (Structured Output):
   - ใช้ Markdown จัดโครงสร้างให้อ่านง่าย เช่น หัวข้อย่อย (###), รายการ Bullet Points, ตัวเลขขั้นตอน, ตารางเปรียบเทียบ (Markdown Table), และ Code blocks สำหรับ API/JSON
   - สำหรับคำถามภาพรวม/สรุปโครงการ: ให้สรุปวัตถุประสงค์, ฟังก์ชันหลัก, กลุ่มผู้ใช้งาน, และรายการเอกสารที่เกี่ยวข้อง
   - สำหรับคำถามเชิงเทคนิค/Business Logic: ให้ระบุเงื่อนไข (Preconditions), กฎการตรวจสอบ (Validation Rules), กรณี Error, และผลลัพธ์ที่คาดหวัง (Expected Results)
3. ความซื่อสัตย์เมื่อไม่พบข้อมูล (Honesty on Gaps):
   - หากข้อมูลที่ผู้ใช้ถามไม่มีระบุไว้ในเอกสารของโครงการ ให้แจ้งอย่างตรงไปตรงมาว่า "ในเอกสารของโครงการปัจจุบันยังไม่มีการระบุข้อมูลในส่วนนี้..." พร้อมให้คำแนะนำในมุมมอง QA ว่าควรประสานงานขอข้อมูลเพิ่มในส่วนใด
4. ภาษาและบุคลิกภาพ (Tone):
   - ตอบเป็นภาษาไทยอย่างสุภาพ เป็นมืออาชีพ ชัดเจน มีชีวิตชีวาตามเอกลักษณ์ของ Rainbow 🌈
"""

        prompt = f"""
======================================================================
CONTEXT FROM PROJECT KNOWLEDGE BASE:
======================================================================
{state.kb_context if state.kb_context else 'ไม่พบข้อมูลใน Knowledge Base สำหรับคำถามนี้'}

======================================================================
CHAT HISTORY (บทสนทนาก่อนหน้า):
======================================================================
{state.original_text[-4000:] if state.original_text else 'ยังไม่มีประวัติการสนทนา'}

======================================================================
USER QUERY (คำถามของผู้ใช้):
======================================================================
{state.instruction}
"""
        return system_instruction, prompt

    @staticmethod
    def generate_stream(state: 'QAState'):
        """Streams QA Research responses token by token with Gemini."""
        logger.info("Running QAResearchAgent (Streaming)...")
        from ocr_engine import get_all_api_keys, _get_gemini_client
        from google.genai import types
        
        keys = get_all_api_keys()
        if not keys:
            yield "ขออภัยครับ ไม่พบคีย์ API สำหรับประมวลผลคำตอบ"
            return
            
        system_instruction, prompt = QAResearchAgent._build_prompt_and_system(state)
        
        gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
        raw_fallback_models = [gemini_model, 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-pro']
        seen = set()
        fallback_models = [m for m in raw_fallback_models if m not in ('gemini-3.1-pro', 'gemini-3.1-flash') and not (m in seen or seen.add(m))]
        
        success = False
        for key_idx in range(len(keys)):
            client = _get_gemini_client(key_idx)
            for current_model in fallback_models:
                try:
                    logger.info(f"QAResearchAgent Stream: Calling model {current_model}...")
                    response_stream = client.models.generate_content_stream(
                        model=current_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.2, # Lower temperature for higher accuracy and factual consistency
                        )
                    )
                    last_usage = None
                    total_output_chars = 0
                    for chunk in response_stream:
                        if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                            last_usage = chunk.usage_metadata
                        if chunk and chunk.text:
                            total_output_chars += len(chunk.text)
                            yield chunk.text
                            
                    if last_usage:
                        try:
                            from db_ingestion import log_api_usage
                            log_api_usage("QAResearch_Agent", current_model, last_usage)
                        except Exception as log_err:
                            logger.warning(f"Failed to log API usage in QAResearch Stream: {log_err}")
                    else:
                        try:
                            from db_ingestion import log_api_usage
                            prompt_toks = max(1, len(prompt + system_instruction) // 4)
                            comp_toks = max(1, total_output_chars // 4)
                            usage_meta = {
                                "prompt_token_count": prompt_toks,
                                "candidates_token_count": comp_toks,
                                "total_token_count": prompt_toks + comp_toks
                            }
                            log_api_usage("QAResearch_Agent", current_model, usage_meta)
                        except Exception as log_err:
                            logger.warning(f"Failed to log estimated stream API usage: {log_err}")
                            
                    success = True
                    break
                except Exception as model_err:
                    logger.warning(f"QAResearchAgent stream error with {current_model}: {model_err}")
                    continue
            if success:
                break
                
        if not success:
            yield "ขออภัยครับ เกิดข้อผิดพลาดในการประมวลผลคำตอบจาก AI กรุณาลองใหม่อีกครั้ง"

    @staticmethod
    def run(state: 'QAState') -> 'QAState':
        """Agent for QA Research (Project Knowledge Queries)"""
        logger.info("Running QAResearchAgent...")
        state.status = "running"
        
        try:
            from ocr_engine import get_all_api_keys, _get_gemini_client
            from google.genai import types
            
            keys = get_all_api_keys()
            if not keys:
                state.error = "No API keys available."
                state.status = "failed"
                return state
                
            system_instruction, prompt = QAResearchAgent._build_prompt_and_system(state)
            
            gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
            raw_fallback_models = [gemini_model, 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.5-pro']
            seen = set()
            fallback_models = [m for m in raw_fallback_models if m not in ('gemini-3.1-pro', 'gemini-3.1-flash') and not (m in seen or seen.add(m))]
            
            response = None
            for key_idx in range(len(keys)):
                client = _get_gemini_client(key_idx)
                for current_model in fallback_models:
                    try:
                        logger.info(f"QAResearchAgent: Calling model {current_model}...")
                        response = client.models.generate_content(
                            model=current_model,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                temperature=0.2,
                            )
                        )
                        if response and response.text:
                            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                                try:
                                    from db_ingestion import log_api_usage
                                    log_api_usage("QAResearch_Agent", current_model, response.usage_metadata)
                                except Exception as log_err:
                                    logger.warning(f"Failed to log API usage in QAResearch: {log_err}")
                            break
                    except Exception as model_err:
                        logger.warning(f"QAResearchAgent error with {current_model}: {model_err}")
                        continue
                if response and response.text:
                    break
                    
            if not response or not response.text:
                raise Exception("All Gemini models failed in QAResearchAgent.")
                
            state.report = response.text
            state.status = "completed"
            
        except Exception as e:
            logger.error(f"QAResearchAgent error: {e}")
            state.error = str(e)
            state.status = "failed"
            
        return state

class QASecurityAgent:
    @staticmethod
    def run(state: 'QASecurityState') -> 'QASecurityState':
        """Agent for QA Security (Code Vulnerability Scanning)"""
        logger.info("Running QASecurityAgent...")
        state.status = "running"
        
        try:
            from ocr_engine import get_all_api_keys, _get_gemini_client
            from google.genai import types
            
            keys = get_all_api_keys()
            if not keys:
                state.error = "No API keys available."
                state.status = "failed"
                return state
                
            client = _get_gemini_client(0)
            gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-3.1-pro')
            
            system_instruction = f"""You are an elite Application Security Engineer and Code Reviewer.
Your task is to analyze the provided source code for security vulnerabilities.
You MUST strictly evaluate the code against the following standard/framework: {state.standard}
If you find vulnerabilities:
1. Categorize them by severity (Critical, High, Medium, Low).
2. Explain exactly where the vulnerability is.
3. Provide a secure code snippet or remediation advice aligned with {state.standard}.
If the code is secure, state that no obvious vulnerabilities were found.
Always format your response cleanly using Markdown. Provide the report in Thai."""
            
            prompt = f"Standard to Check: {state.standard}\nLanguage: {state.language}\n\n=== SOURCE CODE ===\n{state.source_code}\n===================\n\nPlease scan for security vulnerabilities."
            
            raw_fallback_models = [gemini_model, 'gemini-3.1-flash', 'gemini-2.5-flash']
            seen = set()
            fallback_models = [m for m in raw_fallback_models if not (m in seen or seen.add(m))]
            
            response = None
            for key_idx in range(len(keys)):
                client = _get_gemini_client(key_idx)
                for current_model in fallback_models:
                    try:
                        logger.info(f"QASecurityAgent: Calling model {current_model}...")
                        response = client.models.generate_content(
                            model=current_model,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                temperature=0.1,
                            )
                        )
                        if response and response.text:
                            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                                try:
                                    from db_ingestion import log_api_usage
                                    log_api_usage("QASecurity_Agent", current_model, response.usage_metadata)
                                except Exception as log_err:
                                    logger.warning(f"Failed to log API usage in QASecurity: {log_err}")
                            break
                    except Exception as model_err:
                        logger.warning(f"QASecurityAgent error with {current_model}: {model_err}")
                        continue
                if response and response.text:
                    break
                    
            if not response or not response.text:
                raise Exception("All Gemini models failed in QASecurityAgent.")
                
            state.report = response.text
            
            # Simple heuristic to count vulnerabilities based on Markdown headings or severity keywords
            vuln_count = state.report.lower().count('critical') + state.report.lower().count('high') + state.report.lower().count('medium')
            state.vulnerability_count = vuln_count
            state.status = "completed"
            
        except Exception as e:
            logger.error(f"QASecurityAgent error: {e}")
            state.error = str(e)
            state.status = "failed"
            
        return state
