import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class MasterAgent:
    @staticmethod
    def run(messages: List[Dict[str, str]]) -> str:
        """
        Master Agent (Orchestrator) runner that synthesizes QA tools,
        security analysis, performance testing guidance, and general QA consulting.
        """
        if not messages:
            return "กรุณาพิมพ์ข้อความเพื่อเริ่มการสนทนากับ Master Agent"

        # Get last user message
        last_user_msg = ""
        for m in reversed(messages):
            if m.get('role') == 'user':
                last_user_msg = m.get('content', '')
                break

        if not last_user_msg.strip():
            return "กรุณาพิมพ์คำถามหรือคำสั่งที่ต้องการให้ Master Agent ช่วยเหลือครับ"

        try:
            from ocr_engine import get_all_api_keys, _get_gemini_client
            from google.genai import types

            keys = get_all_api_keys()
            if not keys:
                return MasterAgent._fallback_response(last_user_msg, "ระบบทำงานในโหมด Offline / ไม่พบ API Key")

            client = _get_gemini_client(0)
            model_name = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

            system_prompt = (
                "คุณคือ Master Agent (Orchestrator) ประจำแพลตฟอร์ม Spectra QA "
                "มีความเชี่ยวชาญระดับสูงในการทดสอบซอฟต์แวร์, การตรวจเช็ค Security & Vulnerabilities (OWASP Top 10), "
                "การวิเคราะห์ Performance & Load Testing (k6, JMeter), การสร้าง QA Test Cases, "
                "และการสแกนตรวจสอบเอกสาร SRS/Requirement\n\n"
                "คำแนะนำในการตอบ:\n"
                "1. ตอบเป็นภาษาไทยอย่างสุภาพ กระชับ ชัดเจน และมีโครงสร้างเรียบร้อย\n"
                "2. ใช้รูปแบบ Markdown ให้สวยงาม มีหัวข้อ (**ข้อความหนา**, - รายการสัญลักษณ์, `ตัวแปร/โค้ด`, ```โค้ดตัวอย่าง```)\n"
                "3. แนะนำ Tools และ Steps ที่เหมาะสม เช่น [QA Consult], [QA Security], [QA Performance], [Knowledge Base]\n"
                "4. สรุปคำแนะนำเชิงเทคนิคที่เป็นรูปธรรม และสามารถนำไปปฏิบัติจริงได้ทันที"
            )

            # Build chat history context for Gemini
            formatted_contents = []
            for msg in messages[-10:]: # keep last 10 messages for context
                role = "user" if msg.get('role') == 'user' else "model"
                formatted_contents.append(
                    types.Content(
                        role=role,
                        parts=[types.Part.from_text(text=msg.get('content', ''))]
                    )
                )

            response = client.models.generate_content(
                model=model_name,
                contents=formatted_contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.4,
                )
            )

            if response and response.text:
                return response.text.strip()
            else:
                return MasterAgent._fallback_response(last_user_msg, "ไม่ได้รับข้อมูลตอบกลับจาก AI Model")

        except Exception as e:
            logger.error(f"Error in MasterAgent.run: {e}", exc_info=True)
            return MasterAgent._fallback_response(last_user_msg, str(e))

    @staticmethod
    def _fallback_response(query: str, reason: str) -> str:
        q_lower = query.lower()
        if 'security' in q_lower or 'ความปลอดภัย' in q_lower:
            return (
                "🤖 **Master Agent (Security Mode)**\n\n"
                f"*หมายเหตุระบบ: ({reason})*\n\n"
                "ข้อแนะนำสำหรับการตรวจสอบความปลอดภัย (Security Audit):\n"
                "1. **Authentication & Authorization**: ตรวจสอบ JWT Expiry, Password Hashing (bcrypt/argon2)\n"
                "2. **Injection Defense**: ใช้ Parameterized SQL Query ป้องกัน SQL Injection\n"
                "3. **Data Protection**: เข้ารหัสข้อมูลที่สำคัญ (HTTPS / TLS 1.3)\n\n"
                "💡 คุณสามารถใช้เมนู **QA Security** ทางแถบซ้ายมือเพื่อรัน Security Scan อัตโนมัติได้ทันทีครับ"
            )
        elif 'performance' in q_lower or 'โหลด' in q_lower or 'ความเร็ว' in q_lower:
            return (
                "🤖 **Master Agent (Performance Mode)**\n\n"
                f"*หมายเหตุระบบ: ({reason})*\n\n"
                "ข้อแนะนำสำหรับการทดสอบประสิทธิภาพ (Performance Testing):\n"
                "1. **Load Test Target**: กำหนด Concurrent Users (เช่น 100 - 1,000 VUs)\n"
                "2. **Response Time SLA**: กำหนด P95 Response Time < 500ms\n"
                "3. **Tool Suggestion**: ใช้ k6 Script ร่วมกับ Spectra QA Dashboard\n\n"
                "💡 คุณสามารถเลือกเมนู **QA Performance** ทางแถบซ้ายเพื่อรัน Script k6 ได้ครับ"
            )
        else:
            return (
                "🤖 **Master Agent (Orchestrator)**\n\n"
                f"ฉันได้รับข้อความของคุณแล้ว: \"{query}\"\n\n"
                "ขณะนี้ระบบพร้อมให้บริการช่วยเหลือในด้านต่างๆ:\n"
                "- 🛡️ **QA Security**: ตรวจสอบช่องโหว่ความปลอดภัย\n"
                "- ⚡ **QA Performance**: วางแผนและทดสอบค่าน้ำหนักโหลด\n"
                "- 📋 **QA Consult**: วิเคราะห์ SRS & Requirement Gap Analysis\n"
                "- 🔗 **AI Workflow Builder**: ออกแบบ Pipeline การทำงานอัตโนมัติ"
            )