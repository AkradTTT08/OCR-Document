import json
import logging
import os
import datetime
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

def init_flow_diagrams_table():
    """Initializes the qa_analysis_diagrams table if it does not exist."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS qa_analysis_diagrams (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                project_id UUID REFERENCES projects(project_id) ON DELETE CASCADE,
                sitemap_data JSONB DEFAULT '[]'::jsonb,
                system_flowchart TEXT,
                usecase_diagram TEXT,
                activity_diagram TEXT,
                sequence_diagram TEXT,
                screen_mockups JSONB DEFAULT '[]'::jsonb,
                traceability_matrix JSONB DEFAULT '[]'::jsonb,
                summary_stats JSONB DEFAULT '{}'::jsonb,
                status VARCHAR(50) DEFAULT 'Completed',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE qa_analysis_diagrams ADD COLUMN IF NOT EXISTS system_flowchart TEXT;
            CREATE INDEX IF NOT EXISTS idx_qa_analysis_diagrams_project_id ON qa_analysis_diagrams(project_id);
        """)
        conn.commit()
        cursor.close()
        conn.close()
        logger.info("qa_analysis_diagrams table initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize qa_analysis_diagrams table: {e}")

def generate_mockup_for_node(node: dict, project_name: str = "System") -> dict:
    nid = node.get('id', 'page')
    title = node.get('title', 'Screen')
    path = node.get('path', '/')
    sid = node.get('screen_id') or f"SCR-{str(nid).upper().replace('-', '_')}"
    desc = node.get('description') or f"หน้าจอ {title} สำหรับระบบ {project_name}"
    category = node.get('category', 'Module')

    lower_title = title.lower()
    lower_path = path.lower()
    lower_sid = sid.lower()

    # 1. Login / Register
    if 'login' in lower_path or 'login' in lower_title or 'auth-login' in lower_sid:
        return {
            "screen_id": "SCR-AUTH-LOGIN",
            "screen_name": "Login / Register",
            "route": path if path != '/' else "/auth/login",
            "layout_type": "form",
            "description": "เข้าสู่ระบบสำหรับผู้ใช้งานทั่วไปและร้านค้า พร้อมช่องทางสมัครสมาชิกใหม่และ Social Login",
            "header": {
                "title": "เข้าสู่ระบบ / สมัครสมาชิก (Login & Register)",
                "badge": "Security & Auth",
                "badge_color": "blue",
                "actions": ["🚀 เข้าสู่ระบบ", "🔑 ลืมรหัสผ่าน", "📝 สมัครสมาชิกใหม่"]
            },
            "stats": [
                {"label": "ระบบความปลอดภัย", "value": "TLS 1.3 / OAuth 2.0", "sub": "มาตรฐานความปลอดภัยระดับสูง", "color": "emerald"},
                {"label": "ช่องทางเข้าสู่ระบบ", "value": "3 รูปแบบ", "sub": "Email, Google, LINE", "color": "blue"},
                {"label": "การยืนยันตัวตน 2FA", "value": "เปิดใช้งาน (OTP SMS)", "sub": "ป้องกันการเข้าถึงมิชอบ", "color": "purple"},
                {"label": "SLA เวลาตอบสนอง", "value": "< 180 ms", "sub": "Fast Auth API", "color": "amber"}
            ],
            "tabs": ["เข้าสู่ระบบ (Sign In)", "สมัครสมาชิกใหม่ (Register)", "ลืมรหัสผ่าน (Forgot Password)", "นโยบายความปลอดภัย & SSO"],
            "sections": [
                {
                    "section_name": "แบบฟอร์มเข้าสู่ระบบ (User Authentication)",
                    "type": "form",
                    "fields": [
                        {"label": "อีเมล หรือ หมายเลขโทรศัพท์ (Email / Phone)", "type": "text", "default_value": "user@foodsmile.app", "required": True},
                        {"label": "รหัสผ่าน (Password)", "type": "password", "default_value": "••••••••••••", "required": True},
                        {"label": "จดจำการเข้าสู่ระบบบนอุปกรณ์นี้ (Remember Me)", "type": "toggle", "default_value": True}
                    ],
                    "buttons": [
                        {"label": "🚀 เข้าสู่ระบบทันที (Sign In)", "variant": "primary", "icon": "🚀"},
                        {"label": "🔑 เข้าสู่ระบบด้วย Google", "variant": "secondary", "icon": "🔑"},
                        {"label": "💬 เข้าสู่ระบบด้วย LINE", "variant": "accent", "icon": "💬"}
                    ]
                },
                {
                    "section_name": "สถานะการตรวจสอบความปลอดภัยของเซสชัน (Active Session & Security)",
                    "type": "table",
                    "table_headers": ["อุปกรณ์ที่ใช้งาน", "ระบบปฏิบัติการ", "พิกัด IP / ที่ตั้ง", "สถานะเซสชัน", "การจัดการ"],
                    "table_rows": [
                        ["Chrome Browser", "Windows 11 (เครื่องนี้)", "192.168.1.155 (กทม.)", "🟢 กำลังออนไลน์", "เซสชันปัจจุบัน"],
                        ["FoodSmile Mobile App", "iOS 18 (iPhone 16 Pro)", "Cellular 5G (กทม.)", "🟢 ใช้งานเมื่อ 10 นาทีที่แล้ว", "ออกจากระบบ"],
                        ["Safari Mobile", "iPadOS 17.5", "Wi-Fi (นนทบุรี)", "⚪ ออกจากระบบแล้ว", "ลบประวัติ"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-001: เข้าสู่ระบบ", "UC-002: ยืนยันตัวตน 2FA"],
            "connected_req_codes": ["REQ-AUTH-001", "REQ-SEC-002"]
        }

    # 2. PDPA Consent
    elif 'pdpa' in lower_path or 'pdpa' in lower_title or 'pdpa' in lower_sid:
        return {
            "screen_id": "SCR-AUTH-PDPA",
            "screen_name": "PDPA Consent",
            "route": path if path != '/' else "/auth/pdpa-consent",
            "layout_type": "form",
            "description": "แบบฟอร์มขอความยินยอมในการประมวลผลข้อมูลส่วนบุคคลตาม พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล พ.ศ. 2562",
            "header": {
                "title": "หนังสือขอความยินยอมคุ้มครองข้อมูลส่วนบุคคล (PDPA Consent)",
                "badge": "Privacy Compliance",
                "badge_color": "emerald",
                "actions": ["✅ ยินยอมทั้งหมด", "❌ ปฏิเสธ", "📥 ดาวน์โหลดนโยบาย PDF"]
            },
            "stats": [
                {"label": "มาตรฐานกฎหมาย", "value": "พ.ร.บ. PDPA 2562", "sub": "มาตรฐาน ISO/IEC 27701", "color": "emerald"},
                {"label": "สถานะความยินยอม", "value": "รอดำเนินการ (Pending)", "sub": "ต้องยินยอมก่อนใช้งาน", "color": "amber"},
                {"label": "เวอร์ชันนโยบาย", "value": "v2.1 (อัปเดต 2026)", "sub": "ปรับปรุงเงื่อนไข Delivery", "color": "blue"},
                {"label": "สิทธิถอนความยินยอม", "value": "ถอนได้ 100%", "sub": "ผ่านหน้า Account Settings", "color": "purple"}
            ],
            "tabs": ["ข้อกำหนดและเงื่อนไขหลัก", "ความยินยอมด้านการตลาด", "การแบ่งปันข้อมูลกับพันธมิตร"],
            "sections": [
                {
                    "section_name": "รายการความยินยอมในการประมวลผลข้อมูลส่วนบุคคล (Consent Preferences)",
                    "type": "form",
                    "fields": [
                        {"label": "ยินยอมให้เก็บรวบรวมข้อมูลเพื่อการสั่งอาหารและการจัดส่ง (จำเป็น)", "type": "toggle", "default_value": True, "required": True},
                        {"label": "ยินยอมให้ประมวลผลพิกัด GPS เพื่อค้นหาร้านอาหารและคำนวณระยะทาง", "type": "toggle", "default_value": True},
                        {"label": "ยินยอมรับข่าวสาร สิทธิพิเศษ ส่วนลด และโปรโมชั่นจาก FoodSmile", "type": "toggle", "default_value": False},
                        {"label": "ยินยอมให้ใช้คุกกี้เพื่อวิเคราะห์และปรับปรุงประสบการณ์การใช้งาน", "type": "toggle", "default_value": True}
                    ],
                    "buttons": [
                        {"label": "✅ ยินยอมและดำเนินการต่อ (Accept & Continue)", "variant": "primary", "icon": "✅"},
                        {"label": "❌ ปฏิเสธและออกจากระบบ", "variant": "outline", "icon": "❌"}
                    ]
                },
                {
                    "section_name": "สรุปสิทธิของเจ้าของข้อมูลส่วนบุคคล (Data Subject Rights Summary)",
                    "type": "table",
                    "table_headers": ["สิทธิตามกฎหมาย PDPA", "รายละเอียดการใช้สิทธิ", "ช่องทางดำเนินการ", "ระยะเวลา SLA"],
                    "table_rows": [
                        ["สิทธิในการเข้าถึงและขอรับสำเนา (Right to Access)", "ขอรับไฟล์ข้อมูลประวัติการสั่งซื้อและบัญชี", "เมนู Account Settings", "ภายใน 24 ชม."],
                        ["สิทธิในการขอให้ลบหรือทำลาย (Right to Erasure)", "ลบบัญชีและทำลายข้อมูลถาวร", "เมนูขอลบบัญชี", "ภายใน 7 วัน"],
                        ["สิทธิในการถอนความยินยอม (Right to Withdraw)", "ยกเลิกการรับ SMS/Email การตลาด", "สลับ Toggle ในหน้านี้", "มีผลทันที"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-AUTH-003: บันทึกความยินยอม PDPA"],
            "connected_req_codes": ["REQ-PDPA-001", "REQ-PDPA-002"]
        }

    # 3. Account Settings & Deletion
    elif 'account' in lower_path or 'account' in lower_title or 'setting' in lower_path:
        return {
            "screen_id": "SCR-AUTH-ACCOUNT",
            "screen_name": "Account Settings & Deletion",
            "route": path if path != '/' else "/auth/account",
            "layout_type": "form",
            "description": "จัดการข้อมูลโปรไฟล์ผู้ใช้งาน ตั้งค่าความปลอดภัย 2FA การแจ้งเตือน และขอลบบัญชีถาวร",
            "header": {
                "title": "การตั้งค่าบัญชีและความปลอดภัย (Account & Security Settings)",
                "badge": "User Profile",
                "badge_color": "purple",
                "actions": ["💾 บันทึกข้อมูล", "🔒 เปลี่ยนรหัสผ่าน", "⚠️ ขอลบบัญชีถาวร"]
            },
            "stats": [
                {"label": "สถานะบัญชี", "value": "ยืนยันแล้ว (Verified)", "sub": "ระดับ FoodSmile Gold", "color": "emerald"},
                {"label": "ความปลอดภัย 2FA", "value": "เปิดใช้งาน (OTP)", "sub": "SMS เบอร์ 089-xxx-4567", "color": "blue"},
                {"label": "แต้มสะสมปัจจุบัน", "value": "1,240 แต้ม", "sub": "แลกส่วนลดได้ ฿120", "color": "amber"},
                {"label": "การเชื่อมต่อ Social", "value": "Google & LINE", "sub": "Linked Accounts", "color": "purple"}
            ],
            "tabs": ["ข้อมูลโปรไฟล์", "ความปลอดภัย & รหัสผ่าน", "การแจ้งเตือน", "ขอลบบัญชีถาวร (Danger Zone)"],
            "sections": [
                {
                    "section_name": "ข้อมูลผู้ใช้งาน (Profile Information)",
                    "type": "form",
                    "fields": [
                        {"label": "ชื่อ - นามสกุล (Full Name)", "type": "text", "default_value": "เอกรัฐ พัฒนาพาณิชย์", "required": True},
                        {"label": "อีเมลติดต่อ (Email Address)", "type": "text", "default_value": "ekkarat.p@example.com", "required": True},
                        {"label": "หมายเลขโทรศัพท์มือถือ", "type": "text", "default_value": "089-123-4567", "required": True},
                        {"label": "ที่อยู่จัดส่งอาหารหลัก (Default Address)", "type": "textarea", "default_value": "คอนโดเลต ซอยสุขุมวิท 71 แขวงพระโขนงเหนือ เขตวัฒนา กรุงเทพฯ 10110", "required": True},
                        {"label": "เปิดใช้งานการยืนยันตัวตน 2FA ทุกครั้งที่เข้าสู่ระบบ", "type": "toggle", "default_value": True}
                    ],
                    "buttons": [
                        {"label": "💾 บันทึกการเปลี่ยนแปลง (Save Profile)", "variant": "primary", "icon": "💾"},
                        {"label": "🔄 คืนค่าเดิม", "variant": "outline", "icon": "🔄"}
                    ]
                },
                {
                    "section_name": "ประวัติการใช้งานและการเข้าสู่ระบบล่าสุด (Login Audit Log)",
                    "type": "table",
                    "table_headers": ["เวลาเข้าสู่ระบบ", "อุปกรณ์ / บราวเซอร์", "ที่อยู่ IP", "ช่องทาง", "ผลลัพธ์"],
                    "table_rows": [
                        ["14 ต.ค. 2026, 13:45", "Chrome 129 / Windows 11", "192.168.1.155", "Email + Password", "✅ สำเร็จ"],
                        ["14 ต.ค. 2026, 11:20", "FoodSmile App / iOS 18", "171.96.120.4", "Google OAuth 2.0", "✅ สำเร็จ"],
                        ["13 ต.ค. 2026, 19:30", "Chrome 129 / Windows 11", "192.168.1.155", "LINE SSO", "✅ สำเร็จ"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-AUTH-004: แก้ไขข้อมูลบัญชี", "UC-AUTH-005: ขอลบบัญชี"],
            "connected_req_codes": ["REQ-AUTH-004", "REQ-SEC-005"]
        }

    # 4. Review & Rating Submission
    elif 'review' in lower_path or 'review' in lower_title or 'review-submit' in lower_sid:
        return {
            "screen_id": "SCR-REVIEW-SUBMIT",
            "screen_name": "Review & Rating Submission",
            "route": path if path != '/' else "/app/restaurant/:id/review",
            "layout_type": "form",
            "description": "แบบฟอร์มให้คะแนนดาว เขียนรีวิวความคิดเห็น แนบรูปภาพอาหาร และแชร์ประสบการณ์",
            "header": {
                "title": "เขียนรีวิวและให้คะแนนร้านอาหาร (Review & Rating)",
                "badge": "Customer Feedback",
                "badge_color": "amber",
                "actions": ["⭐ โพสต์รีวิว", "📷 แนบรูปภาพ", "ย้อนกลับ"]
            },
            "stats": [
                {"label": "คะแนนเฉลี่ยร้าน", "value": "4.85 ★", "sub": "จาก 342 รีวิว", "color": "amber"},
                {"label": "แต้มสะสมที่จะได้รับ", "value": "+50 Points", "sub": "เมื่อรีวิวพร้อมรูปถ่าย", "color": "emerald"},
                {"label": "สถานะรีวิว", "value": "แบบร่าง (Draft)", "sub": "ยังไม่ได้เผยแพร่", "color": "blue"},
                {"label": "ระดับผู้รีวิว", "value": "FoodSmile Foodie", "sub": "รีวิวแล้ว 14 ครั้ง", "color": "purple"}
            ],
            "tabs": ["เขียนรีวิวใหม่", "รีวิวของฉันในอดีต", "เงื่อนไขการรับแต้ม"],
            "sections": [
                {
                    "section_name": "แบบฟอร์มให้คะแนนและเขียนรีวิว (Rating & Feedback Form)",
                    "type": "form",
                    "fields": [
                        {"label": "คะแนนความพึงพอใจ (1-5 ดาว)", "type": "select", "options": ["⭐⭐⭐⭐⭐ (5 ดาว - ประทับใจมาก)", "⭐⭐⭐⭐ (4 ดาว - ดีมาก)", "⭐⭐⭐ (3 ดาว - ปานกลาง)", "⭐⭐ (2 ดาว - พอใช้)", "⭐ (1 ดาว - ต้องปรับปรุง)"], "default_value": "⭐⭐⭐⭐⭐ (5 ดาว - ประทับใจมาก)", "required": True},
                        {"label": "หัวข้อรีวิวสรุปสั้นๆ", "type": "text", "default_value": "อาหารรสเด็ด วัตถุดิบสดใหม่ บริการประทับใจมาก!", "required": True},
                        {"label": "รายละเอียดความคิดเห็น", "type": "textarea", "default_value": "สั่งส้มตำแซ่บเวอร์และไก่ย่างมารับประทาน รสชาติจัดจ้านกำลังดี วัตถุดิบสดใหม่ สะอาด พนักงานบริการดีมากครับ จะกลับมาอุดหนุนอีกแน่นอน", "required": True},
                        {"label": "ยินยอมให้แสดงชื่อและรูปโปรไฟล์บนรีวิวสาธารณะ", "type": "toggle", "default_value": True}
                    ],
                    "buttons": [
                        {"label": "🚀 โพสต์รีวิวทันที (Submit Review)", "variant": "accent", "icon": "⭐"},
                        {"label": "💾 บันทึกแบบร่าง", "variant": "outline", "icon": "💾"}
                    ]
                }
            ],
            "connected_use_cases": ["UC-C04: เขียนรีวิวร้านอาหาร"],
            "connected_req_codes": ["REQ-REV-001"]
        }

    # 5. Favorite Restaurants
    elif 'favorite' in lower_path or 'favorite' in lower_title or 'favorites' in lower_sid:
        return {
            "screen_id": "SCR-FAVORITES",
            "screen_name": "Favorite Restaurants",
            "route": path if path != '/' else "/app/favorites",
            "layout_type": "table",
            "description": "รายการร้านอาหารโปรดที่บันทึกไว้ จัดการหมวดหมู่ และสั่งอาหารด่วนในคลิกเดียว",
            "header": {
                "title": "ร้านอาหารโปรดของฉัน (My Favorite Restaurants)",
                "badge": "Saved Places",
                "badge_color": "amber",
                "actions": ["🔍 ค้นหาร้านโปรด", "🗺️ ดูบนแผนที่"]
            },
            "stats": [
                {"label": "ร้านอาหารโปรดทั้งหมด", "value": "12 ร้าน", "sub": "บันทึกใน 3 หมวดหมู่", "color": "amber"},
                {"label": "เปิดบริการตอนนี้", "value": "8 ร้าน", "sub": "พร้อมสั่งทันที", "color": "emerald"},
                {"label": "ร้านที่มีโปรโมชั่น", "value": "5 ร้าน", "sub": "ส่วนลดสูงสุด 30%", "color": "blue"},
                {"label": "ร้านที่ใกล้ที่สุด", "value": "450 ม.", "sub": "Zaap Ver พระโขนง", "color": "purple"}
            ],
            "tabs": ["ร้านโปรดทั้งหมด (12)", "ร้านเปิดบริการอยู่ (8)", "โปรโมชั่นพิเศษ (5)"],
            "sections": [
                {
                    "section_name": "รายการร้านอาหารที่บันทึกไว้ (Favorite Bookmarks)",
                    "type": "table",
                    "table_headers": ["ชื่อร้านอาหาร", "หมวดหมู่อาหาร", "คะแนนรีวิว", "ระยะทาง", "สถานะ", "การสั่งซื้อ"],
                    "table_rows": [
                        ["Zaap Ver ส้มตำพระโขนง", "อาหารอีสานรสเด็ด", "4.90 ★", "450 ม.", "🟢 เปิดบริการ", "สั่งอาหารทันที"],
                        ["FoodSmile Gourmet Cafe", "อาหารไทยฟิวชั่น", "4.85 ★", "1.2 กม.", "🟢 เปิดบริการ", "สั่งอาหารทันที"],
                        ["Tokyo Shokudo ราเมน", "อาหารญี่ปุ่น", "4.75 ★", "2.1 กม.", "🟢 เปิดบริการ", "สั่งอาหารทันที"],
                        ["Sweet Treats Cafe & Bakery", "ของหวานและเครื่องดื่ม", "4.60 ★", "3.4 กม.", "🔴 ปิดบริการ", "ดูเมนู"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-C05: จัดการร้านอาหารโปรด"],
            "connected_req_codes": ["REQ-FAV-001"]
        }

    # 6. Home & Map Search
    elif 'home' in lower_path or 'home' in lower_title or 'map' in lower_path or 'home-map' in lower_sid or (lower_path == '/app'):
        return {
            "screen_id": "SCR-HOME-MAP",
            "screen_name": "Home & Map Search",
            "route": path if path != '/' else "/app/home",
            "layout_type": "dashboard",
            "description": "หน้าแรกค้นหาร้านอาหารบนแผนที่แบบเรียลไทม์ ตัวกรองอาหาร หมวดหมู่ยอดนิยม และร้านใกล้ฉัน",
            "header": {
                "title": "ค้นหาร้านอาหารและแผนที่ใกล้ฉัน (Home & Map Discovery)",
                "badge": "Discovery & Map",
                "badge_color": "blue",
                "actions": ["📍 ปักหมุดพิกัดปัจจุบัน", "🔍 ค้นหาขั้นสูง", "🏷️ ดูโปรโมชั่น"]
            },
            "stats": [
                {"label": "ร้านอาหารในพื้นที่", "value": "142 ร้าน", "sub": "เปิดบริการอยู่ 118 ร้าน", "color": "emerald"},
                {"label": "พิกัดปัจจุบัน", "value": "สุขุมวิท 71, กทม.", "sub": "ความแม่นยำ GPS ±5 ม.", "color": "blue"},
                {"label": "รัศมีการค้นหา", "value": "5.0 กม.", "sub": "ปรับเพิ่มได้สูงสุด 15 กม.", "color": "purple"},
                {"label": "โปรโมชั่นวันนี้", "value": "38 ดีลพิเศษ", "sub": "ลดสูงสุด 50%", "color": "amber"}
            ],
            "tabs": ["ร้านอาหารแนะนำใกล้คุณ", "หมวดหมู่อาหารยอดนิยม", "ดีลและส่วนลดพิเศษ", "มุมมองแผนที่แบบเต็มจอ"],
            "sections": [
                {
                    "section_name": "ตัวกรองและค้นหาร้านอาหาร (Restaurant Search & Filters)",
                    "type": "form",
                    "fields": [
                        {"label": "คำค้นหา (ชื่อร้านอาหาร, เมนูเด็ด, หรือสถานที่)", "type": "text", "default_value": "ส้มตำแซ่บเวอร์ พระโขนง", "required": True},
                        {"label": "หมวดหมู่อาหาร", "type": "select", "options": ["ทั้งหมด", "อาหารไทยฟิวชั่น", "อาหารอีสานรสเด็ด", "อาหารญี่ปุ่น", "คาเฟ่ & เบเกอรี่", "เครื่องดื่ม"], "default_value": "อาหารอีสานรสเด็ด"},
                        {"label": "รัศมีการค้นหา", "type": "select", "options": ["1.0 กม. (เดินถึง)", "3.0 กม. (ใกล้เคียง)", "5.0 กม. (พื้นที่จัดส่ง)", "10.0 กม. (ทั้งเขต)"], "default_value": "5.0 กม. (พื้นที่จัดส่ง)"},
                        {"label": "แสดงเฉพาะร้านที่เปิดบริการอยู่ตอนนี้ (Open Now)", "type": "toggle", "default_value": True}
                    ],
                    "buttons": [
                        {"label": "🔍 ค้นหาร้านอาหารทันที", "variant": "primary", "icon": "🔍"},
                        {"label": "🗺️ สลับดูบนแผนที่ Live Map", "variant": "secondary", "icon": "🗺️"}
                    ]
                },
                {
                    "section_name": "ผลการค้นหาร้านอาหารยอดนิยม (Nearby Restaurant Results)",
                    "type": "table",
                    "table_headers": ["ชื่อร้านอาหาร", "หมวดหมู่", "คะแนนรีวิว", "ระยะทาง", "สถานะ", "การสั่งอาหาร"],
                    "table_rows": [
                        ["Zaap Ver ส้มตำพระโขนง", "อาหารอีสานรสเด็ด", "4.90 ★ (420 รีวิว)", "450 ม.", "🟢 เปิดบริการ", "สั่งอาหารทันที"],
                        ["FoodSmile Gourmet Cafe", "อาหารไทยฟิวชั่น", "4.85 ★ (342 รีวิว)", "1.2 กม.", "🟢 เปิดบริการ", "สั่งอาหารทันที"],
                        ["Tokyo Shokudo ราเมน", "อาหารญี่ปุ่น", "4.75 ★ (188 รีวิว)", "2.1 กม.", "🟢 เปิดบริการ", "สั่งอาหารทันที"],
                        ["Sweet Treats Cafe & Bakery", "ของหวานและเครื่องดื่ม", "4.60 ★ (95 รีวิว)", "3.4 กม.", "🔴 ปิดบริการ", "ดูรายละเอียด"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-C01: ค้นหาร้านอาหาร", "UC-C02: ดูพิกัดบนแผนที่"],
            "connected_req_codes": ["REQ-CUST-001", "REQ-MAP-002"]
        }

    # 7. Admin KYC Approval
    elif 'kyc' in lower_path or 'kyc' in lower_title or 'admin-kyc' in lower_sid:
        return {
            "screen_id": "SCR-ADMIN-KYC",
            "screen_name": "Merchant KYC Approval",
            "route": path if path != '/' else "/admin/kyc",
            "layout_type": "table",
            "description": "ระบบตรวจสอบและอนุมัติการเปิดร้านค้าของ Admin ตรวจสอบเอกสาร ภพ.20 บัตร ปชช. และผลประเมิน AI Fraud Score",
            "header": {
                "title": "คิวตรวจสอบและอนุมัติร้านค้า (Merchant KYC Approval Queue)",
                "badge": "Compliance Gate",
                "badge_color": "emerald",
                "actions": ["✅ อนุมัติรายการที่เลือก", "⛔ ปฏิเสธ / ขอเอกสารเพิ่ม", "🔄 รีเฟรช"]
            },
            "stats": [
                {"label": "รายการรอดำเนินการ", "value": "14 ร้าน", "sub": "SLA อนุมัติใน 24 ชม.", "color": "amber"},
                {"label": "อนุมัติแล้ววันนี้", "value": "42 ร้าน", "sub": "ผ่านเกณฑ์ 100%", "color": "emerald"},
                {"label": "ถูกปฏิเสธ / ส่งกลับ", "value": "3 ร้าน", "sub": "เอกสารไม่ชัดเจน", "color": "blue"},
                {"label": "AI Pre-screen แม่นยำ", "value": "98.4%", "sub": "ระบบตรวจจับเอกสารปลอม", "color": "purple"}
            ],
            "tabs": ["รอดำเนินการ (14)", "อนุมัติแล้ว (42)", "ถูกปฏิเสธ (3)", "บันทึกประวัติการตรวจสอบ"],
            "sections": [
                {
                    "section_name": "คิวคำขอลงทะเบียนเปิดร้านค้า (Merchant Onboarding Applications)",
                    "type": "table",
                    "table_headers": ["รหัสคำขอ", "ชื่อร้านค้า", "ผู้ยื่นคำขอ", "เอกสารที่แนบ", "คะแนนความเสี่ยง AI", "สถานะ", "การตัดสินใจ"],
                    "table_rows": [
                        ["#KYC-801", "ส้มตำแซ่บเวอร์ พระโขนง", "คุณเอกรัฐ พัฒนาพาณิชย์", "ภพ.20, บัตร ปชช., สมุดบัญชี", "🟢 ต่ำ (0.02)", "⏳ รอ Admin ยืนยัน", "กดอนุมัติ"],
                        ["#KYC-802", "Cafe De Bangkok สุขุมวิท", "คุณศิริพร บุญเสริม", "บัตร ปชช., หน้าร้าน", "🟢 ต่ำ (0.01)", "⏳ รอ Admin ยืนยัน", "กดอนุมัติ"],
                        ["#KYC-803", "ก๋วยเตี๋ยวเรืออยุธยา ลาดพร้าว", "คุณสมชาย สุขเกษม", "บัตร ปชช. (ภาพเบลอ)", "🟡 ปานกลาง (0.35)", "⚠️ ขอเอกสารเพิ่ม", "ส่งข้อความเตือน"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-A01: ตรวจสอบและอนุมัติร้านค้า"],
            "connected_req_codes": ["REQ-ADMIN-001", "REQ-KYC-001"]
        }

    # 8. Content Moderation
    elif 'moderation' in lower_path or 'moderation' in lower_title or 'admin-moderation' in lower_sid:
        return {
            "screen_id": "SCR-ADMIN-MODERATION",
            "screen_name": "Content Moderation",
            "route": path if path != '/' else "/admin/moderation",
            "layout_type": "table",
            "description": "ระบบคัดกรองเนื้อหา ตรวจสอบรีวิวที่ถูกแจ้งรายงาน ข้อความไม่สุภาพ และรูปภาพอาหารที่ไม่เหมาะสม",
            "header": {
                "title": "ระบบคัดกรองเนื้อหาและรีวิว (Content Moderation Queue)",
                "badge": "Content Safety",
                "badge_color": "amber",
                "actions": ["🛡️ ลบและตักเตือน", "✅ ปลดระงับ (ผ่านเกณฑ์)", "🔄 รีเฟรช"]
            },
            "stats": [
                {"label": "รีวิวรอดำเนินการ", "value": "9 รายการ", "sub": "ระบบ AI ตรวจจับคำหยาบ", "color": "amber"},
                {"label": "ตรวจสอบแล้ววันนี้", "value": "128 รายการ", "sub": "SLA 100% ภายใน 1 ชม.", "color": "emerald"},
                {"label": "สแปมที่ถูกบล็อก", "value": "24 รายการ", "sub": "Bot Traffic ป้องกันสำเร็จ", "color": "blue"},
                {"label": "ความแม่นยำ AI Safety", "value": "99.2%", "sub": "Gemini Content Guard", "color": "purple"}
            ],
            "tabs": ["ข้อความถูกรายงาน (9)", "ภาพถ่ายต้องสงสัย (4)", "ประวัติการจัดการย้อนหลัง"],
            "sections": [
                {
                    "section_name": "รายการรีวิวที่ถูกรายงาน (Flagged Content Queue)",
                    "type": "table",
                    "table_headers": ["รหัสรีวิว", "ร้านอาหารเป้าหมาย", "ผู้เขียนรีวิว", "ข้อความที่ถูก Flag", "คะแนน Toxicity", "สถานะ", "การดำเนินการ"],
                    "table_rows": [
                        ["#REV-991", "FoodSmile Gourmet", "User #9812", "อาหารรสชาติแย่มาก พนักงาน...", "🟡 0.42 (ถ้อยคำรุนแรง)", "⚠️ รอตัดสิน", "ตรวจสอบ"],
                        ["#REV-992", "ส้มตำแซ่บเวอร์", "User #4412", "คลิกลิงก์นี้รับเงินฟรี www.spam.xyz", "🔴 0.98 (Spam/Phishing)", "🚫 บล็อกแล้ว", "ลบถาวร"],
                        ["#REV-993", "Tokyo Shokudo", "User #1120", "อาหารอร่อยมาก แต่รอนานนิดหน่อย", "🟢 0.05 (Normal)", "✅ ปกติ", "ปลด Flag"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-A02: จัดการเนื้อหาไม่เหมาะสม"],
            "connected_req_codes": ["REQ-ADMIN-002", "REQ-SAFE-001"]
        }

    # 9. Master Data Management
    elif 'masterdata' in lower_path or 'masterdata' in lower_title or 'admin-masterdata' in lower_sid:
        return {
            "screen_id": "SCR-ADMIN-MASTERDATA",
            "screen_name": "Master Data Management",
            "route": path if path != '/' else "/admin/masterdata",
            "layout_type": "table",
            "description": "จัดการข้อมูลหลักของระบบ หมวดหมู่อาหาร อัตราค่า GP ส่วนแบ่ง และพื้นที่การจัดส่ง",
            "header": {
                "title": "การจัดการข้อมูลหลักของระบบ (Master Data Management)",
                "badge": "System Master Data",
                "badge_color": "blue",
                "actions": ["➕ สร้างหมวดหมู่ใหม่", "💾 บันทึก Master Data", "📥 Export CSV"]
            },
            "stats": [
                {"label": "หมวดหมู่อาหารทั้งหมด", "value": "24 หมวดหมู่", "sub": "เปิดใช้งาน 22 | ปิด 2", "color": "emerald"},
                {"label": "พื้นที่ให้บริการ", "value": "50 เขต", "sub": "กรุงเทพฯ และปริมณฑล", "color": "blue"},
                {"label": "อัตรา GP มาตรฐาน", "value": "15.0 - 20.0%", "sub": "ตามสัญญาความร่วมมือ", "color": "purple"},
                {"label": "อัปเดตล่าสุด", "value": "วันนี้ 11:30 น.", "sub": "โดย Admin System", "color": "amber"}
            ],
            "tabs": ["หมวดหมู่อาหาร (Categories)", "อัตราค่าบริการและ GP", "พื้นที่ให้บริการ (Delivery Zones)"],
            "sections": [
                {
                    "section_name": "ตารางหมวดหมู่อาหารหลัก (Food Categories Catalog)",
                    "type": "table",
                    "table_headers": ["รหัสหมวดหมู่", "ชื่อหมวดหมู่ (ภาษาไทย)", "ชื่อภาษาอังกฤษ", "จำนวนร้านค้า", "ลำดับการแสดงผล", "สถานะ", "จัดการ"],
                    "table_rows": [
                        ["#CAT-01", "อาหารไทยฟิวชั่น", "Thai Fusion Cuisine", "48 ร้าน", "1", "🟢 เปิดใช้งาน", "แก้ไข"],
                        ["#CAT-02", "อาหารอีสานรสเด็ด", "Isan Traditional Food", "64 ร้าน", "2", "🟢 เปิดใช้งาน", "แก้ไข"],
                        ["#CAT-03", "อาหารญี่ปุ่น", "Japanese Cuisine", "35 ร้าน", "3", "🟢 เปิดใช้งาน", "แก้ไข"],
                        ["#CAT-04", "คาเฟ่ & เบเกอรี่", "Cafe & Bakery", "52 ร้าน", "4", "🟢 เปิดใช้งาน", "แก้ไข"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-A03: จัดการ Master Data"],
            "connected_req_codes": ["REQ-ADMIN-003"]
        }

    # 10. Analytics Dashboard
    elif 'analytics' in lower_path or 'analytics' in lower_title or 'admin-analytics' in lower_sid:
        return {
            "screen_id": "SCR-ADMIN-ANALYTICS",
            "screen_name": "Analytics Dashboard",
            "route": path if path != '/' else "/admin/analytics",
            "layout_type": "dashboard",
            "description": "แดชบอร์ดสรุปสถิติภาพรวม แพลตฟอร์ม ยอดรวม GMV จำนวนผู้ใช้งาน และอัตราการเติบโต",
            "header": {
                "title": "แดชบอร์ดภาพรวมและสถิติแพลตฟอร์ม (Platform Analytics Dashboard)",
                "badge": "Business Intelligence",
                "badge_color": "blue",
                "actions": ["📥 ส่งออกรายงาน PDF/Excel", "🔄 รีเฟรชข้อมูลเรียลไทม์", "⚙️ ตั้งค่า KPI Alerts"]
            },
            "stats": [
                {"label": "ยอดใช้จ่ายรวมวันนี้ (GMV)", "value": "฿2,845,000", "sub": "+14.8% จากสัปดาห์ก่อน", "color": "emerald"},
                {"label": "ผู้ใช้งาน Active รายวัน (DAU)", "value": "18,450 คน", "sub": "สมาชิกใหม่ +420 คน", "color": "blue"},
                {"label": "ออเดอร์จัดส่งสำเร็จ", "value": "12,380 รายการ", "sub": "SLA จัดส่งสำเร็จ 99.4%", "color": "purple"},
                {"label": "คะแนนความพึงพอใจเฉลี่ย", "value": "4.88 ★", "sub": "จาก 1,850 รีวิวสัปดาห์นี้", "color": "amber"}
            ],
            "tabs": ["ภาพรวมยอดขาย & GMV", "พฤติกรรมผู้ใช้งาน (DAU/MAU)", "ประสิทธิภาพการจัดส่ง (Delivery SLA)", "ร้านอาหารยอดนิยม"],
            "sections": [
                {
                    "section_name": "สรุปสถิติการดำเนินงานรายชั่วโมง (Hourly Operations Breakdown)",
                    "type": "table",
                    "table_headers": ["ช่วงเวลา", "จำนวนออเดอร์", "ยอดขายรวม (GMV)", "เวลาจัดส่งเฉลี่ย", "สถานะไรเดอร์", "สถานะระบบ"],
                    "table_rows": [
                        ["11:00 - 12:00 (Peak Lunch)", "2,450 รายการ", "฿560,000", "26 นาที", "🟢 เพียงพอ (94%)", "🟢 ปกติ"],
                        ["12:00 - 13:00 (Peak Lunch)", "3,120 รายการ", "฿715,000", "28 นาที", "🟢 เพียงพอ (98%)", "🟢 ปกติ"],
                        ["13:00 - 14:00 (After Lunch)", "1,240 รายการ", "฿280,000", "22 นาที", "🟢 พร้อมให้บริการ", "🟢 ปกติ"],
                        ["17:00 - 18:00 (Peak Dinner)", "2,890 รายการ", "฿680,000", "25 นาที", "🟢 เพียงพอ (96%)", "🟢 ปกติ"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-A04: ดูสถิติและรายงานแพลตฟอร์ม"],
            "connected_req_codes": ["REQ-ADMIN-004", "REQ-RPT-001"]
        }

    # 11. Store Onboarding / Claim
    elif 'onboard' in lower_path or 'claim' in lower_title or 'onboarding' in lower_title or 'merch-onboard' in lower_sid:
        return {
            "screen_id": "SCR-MERCH-ONBOARD",
            "screen_name": "Store Onboarding / Claim",
            "route": path if path != '/' else "/merchant/onboarding",
            "layout_type": "form",
            "description": "พอร์ทัลลงทะเบียนร้านค้าใหม่ เคลมสิทธิ์เจ้าของร้าน และอัปโหลดเอกสารยืนยันตัวตน KYC",
            "header": {
                "title": "ลงทะเบียนร้านค้าและยืนยันสิทธิ์ (Merchant Onboarding & Claim)",
                "badge": "Merchant Verification",
                "badge_color": "emerald",
                "actions": ["💾 บันทึกแบบร่าง", "▶️ ส่งเอกสาร KYC", "📞 ช่วยเหลือ"]
            },
            "stats": [
                {"label": "สถานะการตรวจสอบ", "value": "รอส่งเอกสาร (Step 2/4)", "sub": "SLA: อนุมัติใน 24 ชม.", "color": "blue"},
                {"label": "เอกสารที่จำเป็น", "value": "4 รายการ", "sub": "บัตร ปชช., ภพ.20, สมุดบัญชี", "color": "amber"},
                {"label": "ค่าธรรมเนียมแรกเข้า", "value": "ฟรี 0 บาท", "sub": "ไม่มีค่าธรรมเนียมรายปี", "color": "emerald"},
                {"label": "ความสมบูรณ์ข้อมูล", "value": "65%", "sub": "กรอกข้อมูลร้านแล้ว", "color": "purple"}
            ],
            "tabs": ["1. ข้อมูลร้านค้า", "2. ข้อมูลเจ้าของ & นิติบุคคล", "3. อัปโหลดเอกสาร KYC", "4. สรุปและยืนยัน"],
            "sections": [
                {
                    "section_name": "ข้อมูลและรายละเอียดร้านค้า (Merchant Profile)",
                    "type": "form",
                    "fields": [
                        {"label": "ชื่อร้านอาหาร (ภาษาไทย)", "type": "text", "default_value": "ส้มตำแซ่บเวอร์ สาขาพระโขนง", "required": True},
                        {"label": "ชื่อร้านอาหาร (English)", "type": "text", "default_value": "Zaap Ver FoodSmile Cafe"},
                        {"label": "เลขทะเบียนพาณิชย์ / เลขประจำตัวผู้เสียภาษี", "type": "text", "default_value": "0105563012345", "required": True},
                        {"label": "ประเภทธุรกิจ", "type": "select", "options": ["บุคคลธรรมดา", "นิติบุคคล (บริษัทจำกัด/ห้างหุ้นส่วน)"], "default_value": "นิติบุคคล (บริษัทจำกัด/ห้างหุ้นส่วน)"},
                        {"label": "เบอร์โทรศัพท์เจ้าของร้าน", "type": "text", "default_value": "081-234-5678", "required": True},
                        {"label": "อีเมลสำหรับรับใบเสร็จและแจ้งเตือน", "type": "text", "default_value": "merchant.contact@foodsmile.app"},
                        {"label": "ที่อยู่ตั้งร้านค้า", "type": "textarea", "default_value": "เลขที่ 88/1 ถนนสุขุมวิท แขวงพระโขนง เขตคลองเตย กรุงเทพฯ 10110", "required": True},
                        {"label": "ยินยอมให้ทีมงานลงพื้นที่ตรวจสอบร้านจริง", "type": "toggle", "default_value": True}
                    ],
                    "buttons": [
                        {"label": "💾 บันทึกแบบร่าง", "variant": "outline", "icon": "💾"},
                        {"label": "ถัดไป: อัปโหลดเอกสาร KYC", "variant": "primary", "icon": "📄"}
                    ]
                },
                {
                    "section_name": "รายการเอกสารประกอบการเคลมและยืนยันสิทธิ์ (KYC Checklist)",
                    "type": "table",
                    "table_headers": ["ลำดับ", "รายการเอกสาร", "สถานะ", "ไฟล์ที่แนบ", "การดำเนินการ"],
                    "table_rows": [
                        ["1", "สำเนาบัตรประชาชนผู้มีอำนาจลงนาม", "✅ อัปโหลดแล้ว", "id_card_owner.jpg", "ดูไฟล์"],
                        ["2", "หนังสือรับรองบริษัท / ภพ.20", "✅ อัปโหลดแล้ว", "vat20_certificate.pdf", "ดูไฟล์"],
                        ["3", "หน้าสมุดบัญชีธนาคารสำหรับรับเงินโอน", "⏳ รอเอกสาร", "-", "อัปโหลด"],
                        ["4", "ภาพถ่ายหน้าร้านพร้อมป้ายชื่อร้านที่มองเห็นชัดเจน", "✅ อัปโหลดแล้ว", "storefront_photo.png", "ดูไฟล์"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-M01: สมัครเปิดร้านและเคลมสิทธิ์"],
            "connected_req_codes": ["REQ-MERCH-001", "REQ-KYC-002"]
        }

    # 12. Store Management
    elif 'manage' in lower_path or 'store management' in lower_title or 'merch-manage' in lower_sid:
        return {
            "screen_id": "SCR-MERCH-MANAGE",
            "screen_name": "Store Management",
            "route": path if path != '/' else "/merchant/manage/:id",
            "layout_type": "form",
            "description": "จัดการร้านค้า เมนูอาหาร ราคา เวลาเปิด-ปิด และสลับสถานะเปิดรับออเดอร์ Delivery",
            "header": {
                "title": "ระบบจัดการร้านค้าและเมนูอาหาร (Store Management Portal)",
                "badge": "Merchant Admin",
                "badge_color": "emerald",
                "actions": ["💾 บันทึกการตั้งค่าร้าน", "➕ เพิ่มเมนูใหม่", "📊 สรุปยอดขาย"]
            },
            "stats": [
                {"label": "สถานะเปิดร้าน", "value": "🟢 เปิดรับออเดอร์", "sub": "ปิดรับ 22:00 น.", "color": "emerald"},
                {"label": "ยอดขายวันนี้", "value": "฿14,250", "sub": "48 ออเดอร์สำเร็จ", "color": "blue"},
                {"label": "เมนูอาหารทั้งหมด", "value": "32 รายการ", "sub": "พร้อมขาย 28 | หมด 4", "color": "purple"},
                {"label": "คะแนนเฉลี่ยร้าน", "value": "4.85 ★", "sub": "จาก 342 รีวิว", "color": "amber"}
            ],
            "tabs": ["ข้อมูลร้านและการเปิด-ปิด", "จัดการรายการเมนูอาหาร", "จัดการโปรโมชั่น", "รีวิวจากลูกค้า"],
            "sections": [
                {
                    "section_name": "การตั้งค่าการเปิดบริการ (Operating Status & Timing)",
                    "type": "form",
                    "fields": [
                        {"label": "เปิดรับออเดอร์ Delivery ตอนนี้", "type": "toggle", "default_value": True},
                        {"label": "เวลาทำการประจำวัน", "type": "text", "default_value": "จันทร์ - อาทิตย์ 10:00 - 22:00 น.", "required": True},
                        {"label": "ระยะทางจัดส่งสูงสุด (กม.)", "type": "text", "default_value": "12 กม."},
                        {"label": "ข้อความแจ้งเตือนลูกค้าหน้าร้าน", "type": "textarea", "default_value": "ส้มตำแซ่บเวอร์ ยินดีต้อนรับ! วันนี้มีเมนูพิเศษ ส้มตำถาดทะเลเดือด"}
                    ],
                    "buttons": [
                        {"label": "💾 บันทึกสถานะร้าน", "variant": "primary", "icon": "💾"}
                    ]
                },
                {
                    "section_name": "รายการเมนูอาหารของร้าน (Store Menu Catalog)",
                    "type": "table",
                    "table_headers": ["รหัสเมนู", "ชื่อเมนูอาหาร", "หมวดหมู่", "ราคา (บาท)", "สถานะพร้อมขาย", "การจัดการ"],
                    "table_rows": [
                        ["#MN-001", "ส้มตำไทยแซ่บ + ไข่เค็ม", "อาหารอีสาน", "85.-", "🟢 พร้อมขาย", "แก้ไข"],
                        ["#MN-002", "ไก่ย่างสมุนไพรเขาสวนกวาง (ครึ่งตัว)", "จานหลัก", "140.-", "🟢 พร้อมขาย", "แก้ไข"],
                        ["#MN-003", "ต้มแซ่บกระดูกหมูอ่อน", "ต้ม/แกง", "150.-", "🟢 พร้อมขาย", "แก้ไข"],
                        ["#MN-004", "คอหมูย่างคลุกฝุ่น", "อาหารทานเล่น", "120.-", "🔴 สินค้าหมด", "เปิดขาย"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-M02: จัดการสถานะร้านและเมนู"],
            "connected_req_codes": ["REQ-MERCH-002", "REQ-MENU-001"]
        }

    # 13. Merchant Web Portal (Overview)
    elif 'merchant' in lower_path or 'merchant' in lower_title or 'merch-dash' in lower_sid or (lower_path == '/merchant'):
        return {
            "screen_id": "SCR-MERCH-DASH",
            "screen_name": "Merchant Web Portal",
            "route": path if path != '/' else "/merchant",
            "layout_type": "dashboard",
            "description": "ศูนย์ควบคุมร้านค้าสำหรับผู้ประกอบการ สรุปยอดขาย ออเดอร์เรียลไทม์ และคำขอเปิดร้าน",
            "header": {
                "title": "ศูนย์รวมร้านค้าและพอร์ทัลร้านอาหาร (Merchant Web Portal)",
                "badge": "Merchant Hub",
                "badge_color": "blue",
                "actions": ["🏪 จัดการร้านของฉัน", "📝 ยื่นคำขอเปิดร้าน (Claim)", "🔄 รีเฟรช"]
            },
            "stats": [
                {"label": "ร้านค้าที่คุณดูแล", "value": "1 ร้าน", "sub": "ส้มตำแซ่บเวอร์ พระโขนง", "color": "emerald"},
                {"label": "สถานะการตรวจสอบ KYC", "value": "✅ ผ่านการตรวจสอบ", "sub": "ยืนยันเมื่อ 1 ต.ค. 2026", "color": "blue"},
                {"label": "รายได้รอบจ่ายถัดไป", "value": "฿38,420", "sub": "โอนเข้าบัญชี 18 ต.ค.", "color": "purple"},
                {"label": "การแจ้งเตือนร้านค้า", "value": "3 ข้อความใหม่", "sub": "ออเดอร์ใหม่ & รีวิว", "color": "amber"}
            ],
            "tabs": ["ภาพรวมร้านค้าของฉัน", "คำขอ Onboarding & Claim", "รอบบัญชีและการรับเงิน"],
            "sections": [
                {
                    "section_name": "รายชื่อร้านอาหารที่คุณเป็นเจ้าของ (My Managed Stores)",
                    "type": "table",
                    "table_headers": ["ชื่อร้านอาหาร", "สาขา", "สถานะการเปิดร้าน", "ยอดขายสัปดาห์นี้", "คะแนนรีวิว", "การเข้าจัดการ"],
                    "table_rows": [
                        ["ส้มตำแซ่บเวอร์", "สาขาพระโขนง", "🟢 เปิดบริการอยู่", "฿62,100", "4.90 ★ (420)", "เข้าสู่ระบบร้าน"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-M01: Dashboard ร้านค้า"],
            "connected_req_codes": ["REQ-MERCH-001"]
        }

    # 14. Admin Dashboard (Overview)
    elif 'admin' in lower_path or 'admin' in lower_title or 'admin-dash' in lower_sid or (lower_path == '/admin'):
        return {
            "screen_id": "SCR-ADMIN-DASH",
            "screen_name": "Admin Dashboard",
            "route": path if path != '/' else "/admin",
            "layout_type": "dashboard",
            "description": "ศูนย์ควบคุมและบริหารระบบสำหรับผู้ดูแลระบบ (Admin) ควบคุมการทำงาน ภาพรวมเซิร์ฟเวอร์ และการแจ้งเตือนฉุกเฉิน",
            "header": {
                "title": "ศูนย์ควบคุมและบริหารระบบ (Admin Master Control Center)",
                "badge": "Super Admin",
                "badge_color": "blue",
                "actions": ["⚡ ตรวจสอบสุขภาพระบบ (Healthcheck)", "📥 ดู System Logs", "🔄 รีเฟรชสถานะ"]
            },
            "stats": [
                {"label": "สถานะระบบเซิร์ฟเวอร์", "value": "🟢 Healthy (99.98%)", "sub": "Cluster 4 Nodes Active", "color": "emerald"},
                {"label": "เวลารอตอบสนอง API (P95)", "value": "128 ms", "sub": "เกณฑ์มาตรฐาน < 300 ms", "color": "blue"},
                {"label": "คำขอ KYC รออนุมัติ", "value": "14 รายการ", "sub": "ต้องดำเนินการวันนี้", "color": "amber"},
                {"label": "การรักษาความปลอดภัย", "value": "TLS 1.3 / Zero Alerts", "sub": "ไม่มีการละเมิดข้อมูล", "color": "purple"}
            ],
            "tabs": ["ภาพรวมระบบ (Overview)", "จัดการผู้ใช้งาน & สิทธิ์", "บันทึกการทำงานของระบบ (Audit Logs)"],
            "sections": [
                {
                    "section_name": "บันทึกกิจกรรมระบบที่สำคัญล่าสุด (Recent System Audit Trails)",
                    "type": "table",
                    "table_headers": ["เวลา", "ผู้ดำเนินการ", "ประเภทกิจกรรม", "เป้าหมาย", "สถานะ", "รายละเอียด"],
                    "table_rows": [
                        ["14 ต.ค. 2026, 14:15", "admin@domain.com", "KYC Approval", "ส้มตำแซ่บเวอร์ พระโขนง", "✅ สำเร็จ", "อนุมัติเปิดร้าน"],
                        ["14 ต.ค. 2026, 13:50", "system-auto", "Daily Database Backup", "PostgreSQL Primary", "✅ สำเร็จ", "ขนาด Snapshot 4.2 GB"],
                        ["14 ต.ค. 2026, 12:30", "moderator@domain.com", "Content Review", "Review #REV-992", "✅ สำเร็จ", "ลบข้อความสแปม"]
                    ]
                }
            ],
            "connected_use_cases": ["UC-A01: ภาพรวม Admin"],
            "connected_req_codes": ["REQ-ADMIN-001"]
        }

    # 15. Default Detail (Restaurant Details)
    else:
        return {
            "screen_id": "SCR-REST-DETAIL",
            "screen_name": "Restaurant Details",
            "route": path if path != '/' else "/app/restaurant/:id",
            "layout_type": "detail",
            "description": "หน้ารายละเอียดร้านอาหาร เมนูแนะนำ รีวิวคะแนน แผนที่ และสั่งอาหาร Delivery",
            "header": {
                "title": "ร้านอาหารอร่อยเลิศ (FoodSmile Gourmet Cafe)",
                "badge": "Verified Merchant",
                "badge_color": "emerald",
                "actions": ["แชร์หน้าร้าน", "บันทึกร้านโปรด", "ย้อนกลับ"]
            },
            "stats": [
                {"label": "คะแนนเฉลี่ย", "value": "4.85 ★", "sub": "จาก 342 รีวิว", "color": "amber"},
                {"label": "สถานะปัจจุบัน", "value": "เปิดบริการอยู่", "sub": "ปิด 22:00 น.", "color": "emerald"},
                {"label": "เวลาจัดส่งเฉลี่ย", "value": "25-35 นาที", "sub": "ระยะทาง 1.8 กม.", "color": "blue"},
                {"label": "ระดับราคา", "value": "฿฿ (100-250 บาท)", "sub": "รับชำระ PromptPay/บัตร", "color": "purple"}
            ],
            "tabs": ["ข้อมูลทั่วไป", "รายการเมนูยอดนิยม", "รีวิว & คะแนน", "แผนที่และการเดินทาง"],
            "sections": [
                {
                    "section_name": "Image Gallery & Highlights",
                    "type": "gallery",
                    "banner_tag": "🔥 เมนูแนะนำประจำสัปดาห์: สเต๊กแซลมอนย่างเกลือหิมาลายัน",
                    "images": [
                        {"title": "บรรยากาศหน้าร้าน", "desc": "ตกแต่งสไตล์ Modern Cozy มีที่จอดรถสะดวกสบาย"},
                        {"title": "โซน Dining Room", "desc": "รองรับจัดเลี้ยงกลุ่ม 10-30 ท่าน มีห้อง VIP"},
                        {"title": "ครัวเปิด Open Kitchen", "desc": "ได้มาตรฐานความสะอาด SHA Plus+ และ HACCP"}
                    ]
                },
                {
                    "section_name": "ข้อมูลและรายละเอียดร้าน (Basic Info)",
                    "type": "form",
                    "fields": [
                        {"label": "ชื่อร้านอาหาร", "type": "text", "default_value": "FoodSmile Gourmet Cafe", "required": True},
                        {"label": "ประเภทอาหาร", "type": "select", "options": ["อาหารไทยฟิวชั่น", "อาหารญี่ปุ่น", "คาเฟ่ & เบเกอรี่", "เครื่องดื่ม"], "default_value": "อาหารไทยฟิวชั่น"},
                        {"label": "เวลาทำการ", "type": "text", "default_value": "จันทร์ - อาทิตย์: 10:00 - 22:00 น.", "required": True},
                        {"label": "เบอร์โทรศัพท์ติดต่อ", "type": "text", "default_value": "02-123-4567, 089-987-6543"},
                        {"label": "ที่อยู่ / สถานที่ตั้ง", "type": "textarea", "default_value": "123/45 ถนนสุขุมวิท 71 แขวงพระโขนงเหนือ เขตวัฒนา กรุงเทพฯ 10110", "required": True},
                        {"label": "เปิดรับออเดอร์ Delivery", "type": "toggle", "default_value": True}
                    ],
                    "buttons": [
                        {"label": "โทรออกหาร้าน", "variant": "outline", "icon": "📞"},
                        {"label": "นำทาง (Google Maps)", "variant": "secondary", "icon": "🧭"},
                        {"label": "สั่งอาหาร Delivery", "variant": "primary", "icon": "🛵"},
                        {"label": "เขียนรีวิวให้คะแนน", "variant": "accent", "icon": "⭐"}
                    ]
                },
                {
                    "section_name": "รายการเมนูอาหารยอดนิยม (Popular Menu Items)",
                    "type": "table",
                    "table_headers": ["รหัสเมนู", "ชื่อเมนูอาหาร", "หมวดหมู่", "ราคา (บาท)", "สถานะพร้อมเสิร์ฟ", "การสั่งซื้อ"],
                    "table_rows": [
                        ["#MN-001", "สเต๊กแซลมอนนอร์เวย์ซอสเลมอนเนยสด", "จานหลัก (Main Course)", "320.-", "พร้อมเสิร์ฟ", "สั่งซื้อเลย"],
                        ["#MN-002", "สปาเก็ตตี้คาโบนาร่าทรัฟเฟิล", "พาสต้า (Pasta)", "260.-", "พร้อมเสิร์ฟ", "สั่งซื้อเลย"],
                        ["#MN-003", "ยำแซลมอนแซ่บพริกสด", "อาหารทานเล่น (Appetizer)", "195.-", "พร้อมเสิร์ฟ", "สั่งซื้อเลย"],
                        ["#MN-004", "มัทฉะลาเต้เย็นเกรดพิธีการ", "เครื่องดื่ม (Beverage)", "110.-", "พร้อมเสิร์ฟ", "สั่งซื้อเลย"]
                    ]
                },
                {
                    "section_name": "รีวิวจากลูกค้าล่าสุด (Customer Reviews)",
                    "type": "reviews",
                    "reviews": [
                        {"user": "นันทนา กุลสวัสดิ์", "rating": 5, "comment": "อาหารอร่อยมาก โดยเฉพาะสเต๊กแซลมอน บริการดี บรรยากาศน่านั่ง แนะนำเลยค่ะ!", "time": "1 ชั่วโมงที่แล้ว"},
                        {"user": "เอกรัฐ พัฒนา", "rating": 5, "comment": "ที่จอดรถสะดวก อาหารเสิร์ฟไว พนักงานสุภาพมากครับ จะกลับมาอุดหนุนอีกแน่นอน", "time": "เมื่อวานนี้"}
                    ]
                }
            ],
            "connected_use_cases": ["UC-C01: ดูข้อมูลร้าน"],
            "connected_req_codes": ["REQ-001"]
        }


def ensure_all_screen_mockups(sitemap_data: list, screen_mockups: list, project_name: str = "System") -> list:
    """Ensures that every node (both root module and children) in sitemap_data has a matching screen mockup."""
    if not sitemap_data:
        return screen_mockups or []

    res_mockups = list(screen_mockups) if screen_mockups else []
    existing_ids = {m.get('screen_id') for m in res_mockups if m.get('screen_id')}
    existing_routes = {m.get('route') for m in res_mockups if m.get('route')}
    existing_names = {m.get('screen_name') for m in res_mockups if m.get('screen_name')}

    for node in sitemap_data:
        children = node.get('children', []) or []
        nodes_to_check = [node] + children
        for n in nodes_to_check:
            sid = n.get('screen_id')
            sroute = n.get('path')
            stitle = n.get('title')

            if (sid and sid in existing_ids) or (sroute and sroute in existing_routes) or (stitle and stitle in existing_names):
                continue

            new_m = generate_mockup_for_node(n, project_name)
            res_mockups.append(new_m)
            if new_m.get('screen_id'):
                existing_ids.add(new_m.get('screen_id'))
            if new_m.get('route'):
                existing_routes.add(new_m.get('route'))
            if new_m.get('screen_name'):
                existing_names.add(new_m.get('screen_name'))

    return res_mockups


def analyze_project_flow_and_diagrams(project_id: str, custom_instructions: str = ""):
    """
    Agent 7: QA Architecture, Flow & Diagram Analyzer
    Synthesizes project Markdown documents, RAG knowledge, and structured requirements into:
    1. Flow Sitemap (Hierarchical IA)
    2. UML & Flow Diagrams (Use Case, Activity, Sequence in Mermaid format)
    3. Interactive Screen Wireframes & UI Mockups
    4. Bidirectional Traceability Matrix
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Fetch Project Information
        cursor.execute("SELECT project_code, project_name, description FROM projects WHERE project_id = %s::uuid", (project_id,))
        proj_row = cursor.fetchone()
        project_code = proj_row[0] if proj_row else "PROJ"
        project_name = proj_row[1] if proj_row else "QA Project"
        project_desc = proj_row[2] if proj_row else ""

        # 2. Fetch all Markdown Documents stored in Project Knowledge Base
        cursor.execute("""
            SELECT doc_id, original_filename, doc_category, doc_type, full_markdown_content
            FROM documents
            WHERE project_id = %s::uuid AND status = 'Active'
            ORDER BY created_at DESC
        """, (project_id,))
        doc_rows = cursor.fetchall()

        docs_context = []
        for d in doc_rows:
            # Truncate very long documents if needed to fit token context
            content_snippet = (d[4] or "")[:6000]
            docs_context.append({
                "doc_id": str(d[0]),
                "filename": d[1],
                "category": d[2],
                "type": d[3],
                "content": content_snippet
            })

        # 3. Fetch Structured Requirements (Phase 1)
        cursor.execute("""
            SELECT req_code, title, description, steps, expected_results
            FROM structured_requirements
            WHERE project_id = %s::uuid
            ORDER BY req_code ASC
        """, (project_id,))
        req_rows = cursor.fetchall()
        reqs_context = []
        for r in req_rows:
            reqs_context.append({
                "req_code": r[0],
                "title": r[1],
                "description": r[2],
                "steps": r[3],
                "expected_results": r[4]
            })

        # 4. Fetch Generated QA Documents (Test Cases / SRS)
        cursor.execute("""
            SELECT doc_name, doc_type, markdown_content
            FROM qa_generated_documents
            WHERE project_id = %s::uuid AND status = 'Completed'
            ORDER BY created_at DESC LIMIT 5
        """, (project_id,))
        qa_doc_rows = cursor.fetchall()
        qa_docs_context = []
        for q in qa_doc_rows:
            qa_docs_context.append({
                "doc_name": q[0],
                "doc_type": q[1],
                "snippet": (q[2] or "")[:3000]
            })

        cursor.close()
        conn.close()
        conn = None


        user_instruction_section = ""
        if custom_instructions and custom_instructions.strip():
            user_instruction_section = f"""
# Additional Custom Instructions from User (High Priority)
{custom_instructions.strip()}
"""

        prompt = f"""
You are a Principal Software Architect, Senior QA Lead, and UX/System Analyst.
Your task is to analyze all the Markdown documents, knowledge base requirements, and workflows in project "{project_name}" ({project_code}) and construct a comprehensive, professional **System Flow & QA Architecture Model**.

# Project Context
- Project Code: {project_code}
- Project Name: {project_name}
- Description: {project_desc}

# Project Documents ({len(docs_context)} documents)
{json.dumps(docs_context, ensure_ascii=False, indent=2)}

# Structured Requirements ({len(reqs_context)} requirements)
{json.dumps(reqs_context, ensure_ascii=False, indent=2)}

# QA Generated Documents Context
{json.dumps(qa_docs_context, ensure_ascii=False, indent=2)}

{user_instruction_section}

---
# Output Format Requirements (MUST BE STRICT VALID JSON ONLY)
Generate a single, strict JSON object with the following keys and exact schema:

{{
  "sitemap": [
    {{
      "id": "node-1",
      "title": "Module / Page Title (e.g. Authentication / Login)",
      "path": "/login",
      "category": "Main / Admin / User / Service",
      "icon": "🔐 / 📊 / 📁 / ⚙️",
      "description": "Brief description of this page / module",
      "screen_id": "SCR-LOGIN",
      "use_case_ids": ["UC-001"],
      "children": [
        {{
          "id": "node-1-1",
          "title": "Forgot Password Modal",
          "path": "/forgot-password",
          "category": "Sub-page",
          "icon": "🔑",
          "description": "Password recovery flow",
          "screen_id": "SCR-FORGOT-PWD",
          "use_case_ids": ["UC-002"],
          "children": []
        }}
      ]
    }}
  ],

  "system_flowchart": "Mermaid syntax string for Complete End-to-End System Flowchart in Draw.io / Diagrams.net style e.g.
flowchart TD
  subgraph ClientLayer [🖥️ Client & Presentation Layer]
    Start([🏁 User Enters System]) --> SelectMenu[Select Module / Menu]
    SelectMenu --> FillForm[Fill Form / Upload File]
    FillForm --> ValidateClient{{Client Validation Passed?}}
    ValidateClient -->|No| ShowClientErr[⚠️ Display Form Error] --> FillForm
    ValidateClient -->|Yes| DispatchReq[🚀 Dispatch API Request]
  end

  subgraph GatewayLayer [🌐 API Gateway & Security Filter]
    DispatchReq --> CheckJWT{{JWT Token Valid & Authorized?}}
    CheckJWT -->|No 401| RejectAuth[⛔ Return 401 / 403 Error] --> Start
    CheckJWT -->|Yes| RateLimitCheck{{Rate Limit OK?}}
    RateLimitCheck -->|Exceeded| ThrottleResp[⏳ 429 Too Many Requests]
    RateLimitCheck -->|Pass| RouteService[🔀 Route to Target Service]
  end

  subgraph EngineLayer [🧠 Core Logic & AI Agents Execution]
    RouteService --> ExecuteLogic[⚙️ Process Business Transaction]
    ExecuteLogic --> AICheck{{Requires AI Agent / QA Ingestion?}}
    AICheck -->|Yes| InvokeLLM[🤖 Call Gemini / Embedding Agent]
    InvokeLLM --> AIEval{{Agent Quality Gate Passed?}}
    AIEval -->|Needs Healing| SelfHealLoop[🔄 Trigger Self-Healing] --> InvokeLLM
    AIEval -->|Passed| AggregateResult[📊 Build QA & Execution Result]
    AICheck -->|No| AggregateResult
  end

  subgraph DataLayer [💾 Persistence & External Systems]
    AggregateResult --> SavePostgres[('🗄️ Save to PostgreSQL / Vector DB')]
    SavePostgres --> AuditLog[📝 Write Audit Log & Event]
    AuditLog --> NotifyClient[🔔 Notify Client & Update Dashboard]
    NotifyClient --> EndFlow([🏁 End: Process Succeeded])
  end
",

  "usecase_diagram": "Mermaid syntax string for Use Case Diagram (flowchart LR). NOTE: Always wrap labels in double quotes. Do NOT use `actor X as ...`, instead declare actors as nodes like ActorID[\"👤 Actor Name\"]. Example:
flowchart LR
  subgraph SystemBoundary [\"System: {project_name}\"]
    UC1([\"UC-001: เข้าสู่ระบบ\"])
    UC2([\"UC-002: อัปโหลดเอกสาร\"])
    UC3([\"UC-003: ตรวจสอบผลลัพธ์\"])
  end
  User[\"👤 ผู้ใช้งานทั่วไป\"] --> UC1
  User --> UC2
  Admin[\"🛡️ ผู้ดูแลระบบ\"] --> UC1
  Admin --> UC3
  UC2 -.->|<<include>>| UC3
",

  "activity_diagram": "Mermaid syntax string for Activity / Decision Flow Diagram (flowchart TD). NOTE: Always wrap node text and decision conditions in double quotes and use `-->|condition|` for branches. Example:
flowchart TD
  Start([\"🏁 เริ่มต้น\"]) --> Login[\"เข้าสู่ระบบ\"]
  Login --> CheckAuth{{\"รหัสผ่านถูกต้อง?\"}}
  CheckAuth -->|ใช่| SelectProject[\"เลือกโครงการ\"]
  CheckAuth -->|ไม่ใช่| ShowError[\"แสดงข้อความแจ้งเตือนข้อผิดพลาด\"] --> Login
  SelectProject --> UploadDoc[\"อัปโหลดเอกสาร / Markdown\"]
  UploadDoc --> ProcessOCR[\"ประมวลผล OCR & QA Engine\"]
  ProcessOCR --> Verify[\"ตรวจสอบความถูกต้องของข้อมูล\"]
  Verify --> SaveKB[\"บันทึกลงฐานข้อมูล Knowledge Base\"]
  SaveKB --> EndFlow([\"🏁 เสร็จสิ้น\"])
",

  "sequence_diagram": "Mermaid syntax string for System Request-Response flow e.g.
sequenceDiagram
  autonumber
  actor User as Standard User
  participant UI as Svelte Frontend
  participant API as Backend API (Flask)
  participant AI as Gemini QA Agent
  participant DB as PostgreSQL / Vector DB

  User->>UI: Select Project & Upload Doc
  UI->>API: POST /api/kb/ingest
  API->>DB: Store Document Chunks & Embeddings
  API->>AI: Trigger Requirement Extraction
  AI-->>API: Return Structured Reqs
  API->>DB: Save Structured Reqs
  API-->>UI: Return Success Response
  UI-->>User: Display Ingested Confirmation
",

  "screen_mockups": [
    {{
      "screen_id": "SCR-REST-DETAIL",
      "screen_name": "Restaurant Details & Review",
      "route": "/restaurant/:id",
      "layout_type": "detail",
      "description": "Comprehensive detail page showing restaurant information, live operating status, interactive menu, reviews, and location.",
      "header": {{
        "title": "ร้านอาหารอร่อยเลิศ (FoodSmile Gourmet)",
        "badge": "Verified Merchant",
        "badge_color": "emerald",
        "actions": ["แชร์หน้าร้าน", "บันทึกร้านโปรด", "ย้อนกลับ"]
      }},
      "stats": [
        {{ "label": "คะแนนเฉลี่ย", "value": "4.85 ★", "sub": "จาก 342 รีวิว", "color": "amber" }},
        {{ "label": "สถานะปัจจุบัน", "value": "เปิดบริการอยู่", "sub": "ปิด 22:00 น.", "color": "emerald" }},
        {{ "label": "เวลาจัดส่งเฉลี่ย", "value": "25-35 นาที", "sub": "ระยะทาง 1.8 กม.", "color": "blue" }},
        {{ "label": "ระดับราคา", "value": "฿฿ (100-250 บาท)", "sub": "รับชำระ PromptPay/บัตร", "color": "purple" }}
      ],
      "tabs": ["ข้อมูลทั่วไป", "รายการเมนูยอดนิยม", "รีวิว & คะแนน", "แผนที่และการเดินทาง"],
      "sections": [
        {{
          "section_name": "Image Gallery & Highlights",
          "type": "gallery",
          "banner_tag": "🔥 เมนูแนะนำประจำสัปดาห์: สเต๊กแซลมอนย่างเกลือหิมาลายัน",
          "images": [
            {{ "title": "บรรยากาศหน้าร้าน", "desc": "ตกแต่งสไตล์ Modern Cozy มีที่จอดรถสะดวกสบาย" }},
            {{ "title": "โซน Dining Room", "desc": "รองรับจัดเลี้ยงกลุ่ม 10-30 ท่าน มีห้อง VIP" }},
            {{ "title": "ครัวเปิด Open Kitchen", "desc": "ได้มาตรฐานความสะอาด SHA Plus+ และ HACCP" }}
          ]
        }},
        {{
          "section_name": "ข้อมูลและรายละเอียดร้าน (Basic Info)",
          "type": "form",
          "fields": [
            {{ "label": "ชื่อร้านอาหาร", "type": "text", "default_value": "FoodSmile Gourmet Cafe", "required": true }},
            {{ "label": "ประเภทอาหาร", "type": "select", "options": ["อาหารไทยฟิวชั่น", "อาหารญี่ปุ่น", "คาเฟ่ & เบเกอรี่", "เครื่องดื่ม"], "default_value": "อาหารไทยฟิวชั่น" }},
            {{ "label": "เวลาทำการ", "type": "text", "default_value": "จันทร์ - อาทิตย์: 10:00 - 22:00 น.", "required": true }},
            {{ "label": "เบอร์โทรศัพท์ติดต่อ", "type": "text", "default_value": "02-123-4567, 089-987-6543" }},
            {{ "label": "ที่อยู่ / สถานที่ตั้ง", "type": "textarea", "default_value": "123/45 ถนนสุขุมวิท 71 แขวงพระโขนงเหนือ เขตวัฒนา กรุงเทพฯ 10110", "required": true }},
            {{ "label": "เปิดรับออเดอร์ Delivery", "type": "toggle", "default_value": true }}
          ],
          "buttons": [
            {{ "label": "โทรออกหาร้าน", "variant": "outline", "icon": "📞" }},
            {{ "label": "นำทาง (Google Maps)", "variant": "secondary", "icon": "🧭" }},
            {{ "label": "สั่งอาหาร Delivery", "variant": "primary", "icon": "🛵" }},
            {{ "label": "เขียนรีวิวให้คะแนน", "variant": "accent", "icon": "⭐" }}
          ]
        }},
        {{
          "section_name": "รายการเมนูอาหารยอดนิยม (Popular Menu Items)",
          "type": "table",
          "table_headers": ["รหัสเมนู", "ชื่อเมนูอาหาร", "หมวดหมู่", "ราคา (บาท)", "สถานะพร้อมเสิร์ฟ", "การสั่งซื้อ"],
          "table_rows": [
            ["#MN-001", "สเต๊กแซลมอนนอร์เวย์ซอสเลมอนเนยสด", "จานหลัก (Main Course)", "320.-", "พร้อมเสิร์ฟ", "สั่งซื้อเลย"],
            ["#MN-002", "สปาเก็ตตี้คาโบนาร่าทรัฟเฟิล", "พาสต้า (Pasta)", "260.-", "พร้อมเสิร์ฟ", "สั่งซื้อเลย"],
            ["#MN-003", "ยำแซลมอนแซ่บพริกสด", "อาหารทานเล่น (Appetizer)", "195.-", "พร้อมเสิร์ฟ", "สั่งซื้อเลย"],
            ["#MN-004", "มัทฉะลาเต้เย็นเกรดพิธีการ", "เครื่องดื่ม (Beverage)", "110.-", "พร้อมเสิร์ฟ", "สั่งซื้อเลย"]
          ]
        }},
        {{
          "section_name": "รีวิวจากลูกค้าล่าสุด (Customer Reviews)",
          "type": "reviews",
          "reviews": [
            {{ "user": "นันทนา กุลสวัสดิ์", "rating": 5, "comment": "อาหารอร่อยมาก โดยเฉพาะสเต๊กแซลมอน บริการดี บรรยากาศน่านั่ง แนะนำเลยค่ะ!", "time": "1 ชั่วโมงที่แล้ว" }},
            {{ "user": "เอกรัฐ พัฒนา", "rating": 5, "comment": "ที่จอดรถสะดวก อาหารเสิร์ฟไว พนักงานสุภาพมากครับ จะกลับมาอุดหนุนอีกแน่นอน", "time": "เมื่อวานนี้" }}
          ]
        }}
      ],
      "connected_use_cases": ["UC-001: ค้นหาร้านค้า", "UC-002: สั่งอาหารและชำระเงิน"],
      "connected_req_codes": ["REQ-001", "REQ-002"]
    }}
  ],

  "traceability_matrix": [
    {{
      "req_code": "REQ-001",
      "req_title": "Requirement Title",
      "doc_name": "Original_Document.md",
      "doc_type": "SRS / Card / OCR",
      "sitemap_node_title": "Login Page",
      "use_case_id": "UC-001: User Login",
      "screen_id": "SCR-LOGIN",
      "screen_name": "Login & Authentication Page",
      "test_cases": ["TC-001: Valid Login", "TC-002: Invalid Password"],
      "defect_log": ["DEF-001: Token expiry on refresh (Resolved)"],
      "uat_item": "UAT-001: ตรวจสอบการเข้าสู่ระบบและบันทึก Session",
      "uat_ref": "ข้อ UAT 1.1 / Acceptance Criteria 1",
      "uat_status": "Ready for UAT / Sign-off",
      "status": "Covered"
    }}
  ],

  "summary_stats": {{
    "total_modules": 4,
    "total_screens": 6,
    "total_use_cases": 8,
    "total_requirements": 12,
    "coverage_percentage": 95,
    "executive_summary": "Comprehensive architecture synthesis summarizing core capabilities, user journeys, and QA coverage."
  }}
}}

Make sure:
1. All Sitemap nodes, Diagrams, Screen Mockups, and Traceability Matrix are deeply interconnected with matching IDs.
2. In 'traceability_matrix', specify the exact linked UAT document item / clause reference in 'uat_item' (e.g., 'UAT-001: ตรวจสอบการทำงาน...', 'ข้อ UAT 1.1: ...') matching the requirement and test cases.
3. The Mermaid syntax MUST be valid and strictly compatible with Mermaid 10+. Avoid HTML tags inside Mermaid node text; use plain text with parenthesis/brackets.
4. The system_flowchart MUST be a rich Draw.io styled workflow diagram displaying tier subgraphs, decision branches, processes, and data stores.
5. Every screen mockup has realistic, detailed UI sections (cards, form fields, mock table headers/rows, badges, buttons) that reflect the true requirements.
6. Do NOT output markdown code blocks around the JSON (no ```json ... ```), output raw JSON only.
"""

        logger.info(f"Agent 7: Generating flow analysis & diagrams for project {project_name} ({project_id})...")
        raw_text, usage_metadata = call_gemini(prompt)
        
        if usage_metadata:
            try:
                from db_ingestion import log_api_usage
                log_api_usage("Agent_7_Flow_Analyzer", os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"), usage_metadata)
            except Exception as log_err:
                logger.warning(f"Failed to log API usage in Agent 7: {log_err}")

        # Robust JSON parsing (supports multi-line Mermaid strings and unescaped control chars)
        def robust_json_loads(text: str) -> dict:
            if not text:
                return {}
            clean = text.strip()
            if "```json" in clean:
                clean = clean.split("```json", 1)[1].split("```", 1)[0]
            elif "```" in clean:
                clean = clean.split("```", 1)[1].split("```", 1)[0]
            clean = clean.strip()

            # Try direct load with strict=False (allows raw newlines/tabs inside strings)
            try:
                return json.loads(clean, strict=False)
            except Exception:
                pass

            import re
            # Try finding the outermost JSON object
            match = re.search(r'(\{[\s\S]*\})', clean)
            if match:
                try:
                    return json.loads(match.group(1), strict=False)
                except Exception:
                    pass

            # Try removing trailing commas
            cleaned_trailing = re.sub(r',\s*([\]}])', r'\1', clean)
            try:
                return json.loads(cleaned_trailing, strict=False)
            except Exception:
                pass

            match = re.search(r'(\{[\s\S]*\})', cleaned_trailing)
            if match:
                return json.loads(match.group(1), strict=False)

            return json.loads(clean, strict=False)

        # Mermaid Sanitizer on backend
        def clean_mermaid_code(raw_code: str) -> str:
            if not raw_code:
                return ""
            txt = raw_code.strip()
            if txt.startswith("```mermaid"):
                txt = txt[10:].strip()
            if txt.startswith("```"):
                txt = txt[3:].strip()
            if txt.endswith("```"):
                txt = txt[:-3].strip()

            if txt.startswith("sequenceDiagram"):
                return txt

            import re
            lines = txt.splitlines()
            cleaned_lines = []
            
            for line in lines:
                l = line.rstrip()
                if not l.strip():
                    cleaned_lines.append("")
                    continue

                indent = re.match(r'^\s*', l).group(0)

                # Fix actor declaration in flowchart
                actor_m = re.match(r'^\s*actor\s+([A-Za-z0-9_]+)(?:\s+(?:as\s+)?(.*))?$', l, re.IGNORECASE)
                if actor_m:
                    act_id = actor_m.group(1)
                    act_lbl = actor_m.group(2) or act_id
                    act_lbl = act_lbl.strip().strip('"').strip("'").replace('"', "'")
                    cleaned_lines.append(f'{indent}{act_id}["👤 {act_lbl}"]')
                    continue

                # Fix Subgraph quotes
                sub_m = re.match(r'^(\s*subgraph\s+[A-Za-z0-9_]+)\s*\[\s*([^\]]+?)\s*\]\s*$', l, re.IGNORECASE)
                if sub_m:
                    title = sub_m.group(2).strip().strip('"').strip("'").replace('"', "'")
                    cleaned_lines.append(f'{sub_m.group(1)} ["{title}"]')
                    continue

                # Fix dotted & plantuml arrows
                l = re.sub(r'([A-Za-z0-9_]+)\s*<\.\.\s*([A-Za-z0-9_]+)\s*:\s*<?<?([^>\r\n]+)>?>?', r'\2 -.->|"\3"| \1', l)
                l = re.sub(r'([A-Za-z0-9_]+)\s*\.\.>\s*([A-Za-z0-9_]+)\s*:\s*<?<?([^>\r\n]+)>?>?', r'\1 -.->|"\3"| \2', l)
                l = re.sub(r'([A-Za-z0-9_]+)\s*<\.\.\s*([A-Za-z0-9_]+)', r'\2 -.-> \1', l)
                l = re.sub(r'([A-Za-z0-9_]+)\s*\.\.>\s*([A-Za-z0-9_]+)', r'\1 -.-> \2', l)

                # Fix inline edge labels
                l = re.sub(r'--\s*(?:\(([^()\r\n]+)\)|([^->\r\n|]+?))\s*-->', r'-->|"\1\2"|', l)
                l = re.sub(r'--\s*(?:\(([^()\r\n]+)\)|([^->\r\n|]+?))\s*--\s*>', r'-->|"\1\2"|', l)

                # Protect End keyword
                if not re.match(r'^\s*end\s*$', l, re.IGNORECASE):
                    l = re.sub(r'\bEnd\s*\(\[\s*(.*?)\s*\]\)', r'EndNode(["\1"])', l)
                    l = re.sub(r'\bEnd\s*\[\s*(.*?)\s*\]', r'EndNode["\1"]', l)
                    l = re.sub(r'(-->|-\.->|==>)\s*End\b', r'\1 EndNode', l)
                    l = re.sub(r'\bEnd\s*(-->|-\.->|==>)', r'EndNode \1', l)

                cleaned_lines.append(l)

            # Auto-close subgraphs
            sub_count = sum(1 for line in cleaned_lines if re.match(r'^\s*subgraph\b', line, re.IGNORECASE))
            end_count = sum(1 for line in cleaned_lines if re.match(r'^\s*end\s*$', line.strip(), re.IGNORECASE))
            while sub_count > end_count:
                cleaned_lines.append("  end")
                end_count += 1

            return "\n".join(cleaned_lines)

        data = robust_json_loads(raw_text)
        if not data or not isinstance(data, dict):
            logger.warning("Agent 7: Parsed JSON is empty or not a dict! Falling back to empty structure.")
            data = {}

        sitemap_data = data.get("sitemap", [])
        system_flowchart = clean_mermaid_code(data.get("system_flowchart", ""))
        usecase_diagram = clean_mermaid_code(data.get("usecase_diagram", ""))
        activity_diagram = clean_mermaid_code(data.get("activity_diagram", ""))
        sequence_diagram = data.get("sequence_diagram", "")
        screen_mockups = ensure_all_screen_mockups(sitemap_data, data.get("screen_mockups", []), project_name)
        traceability_matrix = data.get("traceability_matrix", [])
        summary_stats = data.get("summary_stats", {})

        # Fallback for system_flowchart if empty: use activity_diagram
        if not system_flowchart and activity_diagram:
            system_flowchart = activity_diagram

        # 6. Save or Update in database
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM qa_analysis_diagrams WHERE project_id = %s::uuid ORDER BY updated_at DESC LIMIT 1", (project_id,))
        existing_row = cursor.fetchone()

        if existing_row:
            analysis_id = existing_row[0]
            cursor.execute("""
                UPDATE qa_analysis_diagrams
                SET sitemap_data = %s,
                    system_flowchart = %s,
                    usecase_diagram = %s,
                    activity_diagram = %s,
                    sequence_diagram = %s,
                    screen_mockups = %s,
                    traceability_matrix = %s,
                    summary_stats = %s,
                    status = 'Completed',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s::uuid
            """, (
                json.dumps(sitemap_data, ensure_ascii=False),
                system_flowchart,
                usecase_diagram,
                activity_diagram,
                sequence_diagram,
                json.dumps(screen_mockups, ensure_ascii=False),
                json.dumps(traceability_matrix, ensure_ascii=False),
                json.dumps(summary_stats, ensure_ascii=False),
                analysis_id
            ))
        else:
            cursor.execute("""
                INSERT INTO qa_analysis_diagrams (
                    project_id, sitemap_data, system_flowchart, usecase_diagram, activity_diagram,
                    sequence_diagram, screen_mockups, traceability_matrix, summary_stats, status
                ) VALUES (
                    %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, 'Completed'
                ) RETURNING id
            """, (
                project_id,
                json.dumps(sitemap_data, ensure_ascii=False),
                system_flowchart,
                usecase_diagram,
                activity_diagram,
                sequence_diagram,
                json.dumps(screen_mockups, ensure_ascii=False),
                json.dumps(traceability_matrix, ensure_ascii=False),
                json.dumps(summary_stats, ensure_ascii=False)
            ))
            analysis_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Successfully saved flow analysis (ID: {analysis_id}) for project {project_id}")
        return True, {
            "id": str(analysis_id),
            "project_id": str(project_id),
            "sitemap": sitemap_data,
            "system_flowchart": system_flowchart,
            "usecase_diagram": usecase_diagram,
            "activity_diagram": activity_diagram,
            "sequence_diagram": sequence_diagram,
            "screen_mockups": screen_mockups,
            "traceability_matrix": traceability_matrix,
            "summary_stats": summary_stats,
            "status": "Completed"
        }

    except Exception as e:
        logger.error(f"Error in analyze_project_flow_and_diagrams: {e}", exc_info=True)
        if conn:
            try:
                conn.close()
            except:
                pass
        return False, str(e)


def get_project_flow_analysis(project_id: str):
    """
    Fetches the latest saved flow analysis for a project.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, sitemap_data, usecase_diagram, activity_diagram,
                   sequence_diagram, screen_mockups, traceability_matrix, summary_stats,
                   status, updated_at, system_flowchart
            FROM qa_analysis_diagrams
            WHERE project_id = %s::uuid
            ORDER BY updated_at DESC LIMIT 1
        """, (project_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return None

        system_flowchart_val = row[10] if len(row) > 10 and row[10] else (row[3] or "")
        sitemap_val = row[1] or []
        mockups_val = ensure_all_screen_mockups(sitemap_val, row[5] or [])

        return {
            "id": str(row[0]),
            "project_id": str(project_id),
            "sitemap": sitemap_val,
            "system_flowchart": system_flowchart_val,
            "usecase_diagram": row[2] or "",
            "activity_diagram": row[3] or "",
            "sequence_diagram": row[4] or "",
            "screen_mockups": mockups_val,
            "traceability_matrix": row[6] or [],
            "summary_stats": row[7] or {},
            "status": row[8],
            "updated_at": row[9].isoformat() if row[9] else None
        }
    except Exception as e:
        logger.error(f"Error fetching flow analysis: {e}", exc_info=True)
        return None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Agent 7 Flow Analyzer Module loaded.")
