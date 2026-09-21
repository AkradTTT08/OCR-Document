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
        # Use existing monolithic function (which will be orchestrated by us now)
        # Note: spellcheck_text returns tokens, errors, and summary.
        # We extract errors for the shared state.
        result = spellcheck_text(state.original_text, include_suggestions=True)
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
            model_name = os.environ.get('GEMINI_MODEL', 'gemini-3.1-flash')
            
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
            gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-3.1-pro')
            
            skill_section = f"--- คำสั่งพิเศษเพิ่มเติมจาก AI Skill ---\n{state.skill_instructions}\n" if state.skill_instructions else ""
            
            prompt = f"""คุณคือผู้เชี่ยวชาญด้านระบบสารสนเทศ และ System QA (Quality Assurance)
หน้าที่ของคุณคือตรวจสอบและเปรียบเทียบความถูกต้องของ 'เอกสารที่อัปโหลด' กับ 'ข้อมูลมาตรฐาน' ที่มีอยู่ในฐานข้อมูล (Knowledge Base ของโครงการ {state.project_name})

ประเภทของเอกสารที่กำลังตรวจสอบ: {state.doc_type}

{skill_section}

=== ข้อมูลมาตรฐานจากฐานข้อมูล {state.project_name} ===
{state.kb_context if state.kb_context else 'ไม่พบข้อมูลที่ตรงกันเป๊ะในระบบ (โปรดประเมินจากความรู้ทั่วไปหรือโครงสร้างเอกสาร)'}
{state.prev_report_context}
=== เอกสารที่ผู้ใช้อัปโหลด ===
{state.original_text[:8000]}

{state.instruction}
"""
            
            raw_fallback_models = [gemini_model, 'gemini-3.1-flash', 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
            seen = set()
            fallback_models = [m for m in raw_fallback_models if not (m in seen or seen.add(m))]
            
            response = None
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
                        logger.warning(f"QAConsultAgent error with {current_model}: {model_err}")
                        continue
                if response and response.text:
                    break
                    
            if not response or not response.text:
                raise Exception("All Gemini models failed in QAConsultAgent.")
                
            state.report = response.text
            state.status = "completed"
            
        except Exception as e:
            logger.error(f"QAConsultAgent error: {e}")
            state.error = str(e)
            state.status = "failed"
            
        return state

class QAResearchAgent:
    @staticmethod
    def _build_prompt_and_system(state: 'QAState'):
        system_instruction = f"""คุณคือ Rainbow 🌈 ผู้เชี่ยวชาญด้าน QA Research & Requirements Intelligence ประจำระบบ 'Spectra QA'
หน้าที่หลักของคุณคือ: ตอบคำถามและวิเคราะห์ข้อมูลเกี่ยวกับโครงการ "{state.project_name or 'N/A'}" (รหัสโครงการ: {state.project_code or state.project_id}) อย่างแม่นยำ ละเอียด ลึกซึ้ง และถูกต้อง 100% โดยอ้างอิงจากคลังข้อมูล (Knowledge Base), เอกสารความต้องการ (Requirements), SRS, Test Cases และเอกสารที่อัปโหลดทั้งหมด

กฎเหล็กในการค้นหาและตอบคำถาม (QA Accuracy & Grounding Rules):
1. ความแม่นยำและการอ้างอิง (Grounding & Citations):
   - ให้ยึดข้อมูลจาก CONTEXT FROM KNOWLEDGE BASE เป็นหลักความจริงสูงสุด ห้ามคาดเดาหรือสร้างข้อมูลขึ้นมาเอง (Zero Hallucination)
   - ระบุแหล่งที่มาของข้อมูลเสมอเมื่อกล่าวถึงข้อกำหนด เช่น `[อ้างอิง: ชื่อไฟล์]` หรือ `[ความต้องการ: REQ-XXX]`
2. รูปแบบคำตอบที่ชัดเจน (Structured Output):
   - ใช้ Markdown จัดโครงสร้างให้อ่านง่าย เช่น หัวข้อย่อย (###), รายการ Bullet Points, ตัวเลขขั้นตอน, ตารางเปรียบเทียบ (Table), และ Code blocks สำหรับ API/JSON
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
        
        gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-3.1-pro')
        raw_fallback_models = [gemini_model, 'gemini-3.1-flash', 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
        seen = set()
        fallback_models = [m for m in raw_fallback_models if not (m in seen or seen.add(m))]
        
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
                    for chunk in response_stream:
                        if chunk and chunk.text:
                            yield chunk.text
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
            
            gemini_model = os.environ.get('GEMINI_MODEL', 'gemini-3.1-pro')
            raw_fallback_models = [gemini_model, 'gemini-3.1-flash', 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
            seen = set()
            fallback_models = [m for m in raw_fallback_models if not (m in seen or seen.add(m))]
            
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
