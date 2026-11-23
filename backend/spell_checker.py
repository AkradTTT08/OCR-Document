"""
Spell Checker - ระบบตรวจสอบคำผิดภาษาไทยและภาษาอังกฤษแบบ Hybrid 3 ชั้น (3-Layer Linguistic & AI Engine)
Layer 1: Deterministic Rule & Lexicon Scanner (พจนานุกรมคำมักเขียนผิดราชบัณฑิตยสภา + ทับศัพท์ + English SpellChecker + ตรวจสระเพี้ยนจาก PDF)
Layer 2: Context-Aware Gemini 2.5 Multimodal/Linguistic Proofreader (ตรวจบริบท คำพ้องเสียง ไวยากรณ์ และสำนวน)
Layer 3: Word-Boundary & Context-Anchored Span Matcher (ใช้ PyThaiNLP newmm word boundaries และ English regex boundaries ป้องกันการไฮไลท์ซ้อนในคำอื่น)
"""
import bisect
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Pattern สำหรับตรวจสอบภาษาและตัวอักษร
THAI_CHAR_RE = re.compile(r'[\u0E00-\u0E7F]')
THAI_CHUNK_RE = re.compile(r'[\u0E00-\u0E7F]+')
ENG_WORD_RE = re.compile(r'^[a-zA-Z]{2,}$')
ENG_TOKEN_FINDER_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]{1,30}\b")

# รูปแบบที่ต้องข้ามไม่นำไปตรวจคำผิด (URL, Email, Markdown Code, Hex/UUID, Version, Path)
IGNORE_SPAN_RE = re.compile(
    r"(?:```[\s\S]*?```|`[^`\n]+`|https?://[^\s)\]>]+|[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+|\b(?:v?\d+(?:\.\d+)+|[0-9a-fA-F]{8,})\b)",
    re.MULTILINE
)

# ── Layer 1A: พจนานุกรมคำภาษาไทยที่มักเขียนผิด & คำทับศัพท์ตามเกณฑ์ราชบัณฑิตยสภา ──
# Format: "คำที่เขียนผิด": (["คำที่ถูกต้องอันดับ 1", "ทางเลือก"], "misspelled" | "semantic", "คำอธิบายเหตุผล")
KNOWN_THAI_MISSPELLINGS: Dict[str, Tuple[List[str], str, str]] = {
    # คำสะกดผิดยอดนิยมในเอกสารราชการ / SRS / TOR / รายงาน
    "อนุญาติ": (["อนุญาต"], "misspelled", "สะกดผิดตามพจนานุกรมราชบัณฑิตยสภา ('อนุญาต' ไม่ต้องมีสระอิ)"),
    "สังเกตุ": (["สังเกต"], "misspelled", "สะกดผิดตามพจนานุกรมราชบัณฑิตยสภา ('สังเกต' ไม่ต้องมีสระอุ)"),
    "กฏหมาย": (["กฎหมาย"], "misspelled", "ใช้พยัญชนะผิด ต้องใช้ 'ฎ' (ชฎา) หยักเดียว เป็น 'กฎหมาย'"),
    "กฏเกณฑ์": (["กฎเกณฑ์"], "misspelled", "ใช้พยัญชนะผิด ต้องใช้ 'ฎ' (ชฎา) เป็น 'กฎเกณฑ์'"),
    "กฏระเบียบ": (["กฎระเบียบ"], "misspelled", "ใช้พยัญชนะผิด ต้องใช้ 'ฎ' (ชฎา) เป็น 'กฎระเบียบ'"),
    "ข้อกฏหมาย": (["ข้อกฎหมาย"], "misspelled", "ใช้พยัญชนะผิด ต้องใช้ 'ฎ' (ชฎา) เป็น 'ข้อกฎหมาย'"),
    "ปรากฎ": (["ปรากฏ"], "misspelled", "ใช้พยัญชนะผิด คำว่า 'ปรากฏ' ต้องใช้ 'ฏ' (ปฏัก) สองหยัก"),
    "มาตราฐาน": (["มาตรฐาน"], "misspelled", "สะกดผิด คำที่ถูกต้องคือ 'มาตรฐาน' (ไม่มีสระอาหลัง ร)"),
    "สัมนา": (["สัมมนา"], "misspelled", "สะกดผิด คำที่ถูกต้องคือ 'สัมมนา' (มี ม สองตัว)"),
    "กะทะ": (["กระทะ"], "misspelled", "สะกดผิดตามพจนานุกรมฯ ต้องมี ร เป็น 'กระทะ'"),
    "กะเพรา": (["กะเพรา"], "misspelled", ""),  # valid guard
    "กระเพรา": (["กะเพรา"], "misspelled", "สะกดผิด ชื่อพรรณไม้และอาหารใช้ 'กะเพรา' (ไม่มี ร หลัง ก)"),
    "รสชาด": (["รสชาติ"], "misspelled", "สะกดผิด คำที่ถูกต้องคือ 'รสชาติ' ('ชาด' คือวัตถุสีแดง)"),
    "บิณฑบาตร": (["บิณฑบาต"], "misspelled", "คำกริยา 'บิณฑบาต' ไม่ต้องมี ร ต่อท้าย (ส่วน 'ตักบาตร' มี ร)"),
    "ใส่บาต": (["ใส่บาตร"], "misspelled", "คำนาม 'บาตร' ต้องมี ร ต่อท้าย เป็น 'ใส่บาตร'"),
    "ตักบาต": (["ตักบาตร"], "misspelled", "คำนาม 'บาตร' ต้องมี ร ต่อท้าย เป็น 'ตักบาตร'"),
    "ผูกพันธ์": (["ผูกพัน"], "misspelled", "สะกดผิด คำว่า 'ผูกพัน' ไม่ต้องมี ธ์"),
    "ประชาสัมพันธ์": (["ประชาสัมพันธ์"], "misspelled", ""),  # valid guard
    "สับดาห์": (["สัปดาห์"], "misspelled", "สะกดผิด ต้องใช้ ป เป็น 'สัปดาห์'"),
    "สาเหตุ": (["สาเหตุ"], "misspelled", ""),  # valid guard
    "ลางสังหร": (["ลางสังหรณ์"], "misspelled", "สะกดผิด ต้องมี ณ์ การันต์ เป็น 'ลางสังหรณ์'"),
    "อานิสงค์": (["อานิสงส์"], "misspelled", "สะกดผิด ต้องใช้ ส์ การันต์ เป็น 'อานิสงส์'"),
    "เจตจำนงค์": (["เจตจำนง"], "misspelled", "สะกดผิด คำว่า 'เจตจำนง' ไม่ต้องมี ค์ การันต์"),
    "จำนงค์": (["จำนง"], "misspelled", "สะกดผิด คำว่า 'จำนง' ไม่ต้องมี ค์ การันต์"),
    "อริยาบถ": (["อิริยาบถ"], "misspelled", "สะกดผิด ต้องมีสระอิที่ อ เป็น 'อิริยาบถ'"),
    "เกียจคร้าน": (["เกียจคร้าน"], "misspelled", ""),  # valid guard
    "ขี้เกียจ": (["ขี้เกียจ"], "misspelled", ""),  # valid guard
    "รังเกียจ": (["รังเกียจ"], "misspelled", ""),  # valid guard
    "น่าเกลียด": (["น่าเกลียด"], "misspelled", ""),  # valid guard
    "รังเกลียด": (["รังเกียจ"], "misspelled", "สะกดผิด ต้องใช้ 'รังเกียจ'"),
    "น่าเกียจ": (["น่าเกลียด"], "misspelled", "สะกดผิด ต้องใช้ 'น่าเกลียด'"),
    "คลีนิค": (["คลินิก"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ที่ถูกต้องคือ 'คลินิก'"),
    "คลินิค": (["คลินิก"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ที่ถูกต้องคือ 'คลินิก' (ลงท้ายด้วย ก)"),
    "เทคนิค": (["เทคนิค"], "misspelled", ""),  # valid guard
    "กราฟฟิค": (["กราฟิก"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ที่ถูกต้องคือ 'กราฟิก'"),
    "กราฟฟิก": (["กราฟิก"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ที่ถูกต้องคือ 'กราฟิก'"),
    "กราฟิค": (["กราฟิก"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ที่ถูกต้องคือ 'กราฟิก'"),
    "ลิงค์": (["ลิงก์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Link คือ 'ลิงก์' (ใช้ ก์)"),
    "ลิ้งค์": (["ลิงก์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Link คือ 'ลิงก์'"),
    "ลิ้งก์": (["ลิงก์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Link คือ 'ลิงก์' (ไม่มีไม้โท)"),
    "เว็ปไซต์": (["เว็บไซต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Website คือ 'เว็บไซต์' (ใช้ บ)"),
    "เวปไซต์": (["เว็บไซต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Website คือ 'เว็บไซต์'"),
    "เว็บไซด์": (["เว็บไซต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Website คือ 'เว็บไซต์' (ใช้ ต์)"),
    "เว็บไซท์": (["เว็บไซต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Website คือ 'เว็บไซต์' (ใช้ ต์)"),
    "แอพพลิเคชั่น": (["แอปพลิเคชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Application คือ 'แอปพลิเคชัน'"),
    "แอปพลิเคชั่น": (["แอปพลิเคชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Application คือ 'แอปพลิเคชัน' (ไม่มีไม้เอก)"),
    "แอพพลิเคชัน": (["แอปพลิเคชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Application คือ 'แอปพลิเคชัน' (ใช้ ป)"),
    "ฟังก์ชั่น": (["ฟังก์ชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Function คือ 'ฟังก์ชัน' (ไม่มีไม้เอก)"),
    "ฟังชั่น": (["ฟังก์ชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Function คือ 'ฟังก์ชัน'"),
    "ฟังค์ชั่น": (["ฟังก์ชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Function คือ 'ฟังก์ชัน' (ใช้ ก์)"),
    "เวอร์ชั่น": (["เวอร์ชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Version คือ 'เวอร์ชัน' (ไม่มีไม้เอก)"),
    "โซลูชั่น": (["โซลูชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Solution คือ 'โซลูชัน' (ไม่มีไม้เอก)"),
    "โปรโมชั่น": (["โปรโมชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Promotion คือ 'โปรโมชัน' (ไม่มีไม้เอก)"),
    "คอลเลคชั่น": (["คอลเลกชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Collection คือ 'คอลเลกชัน'"),
    "ทรานแซคชั่น": (["ทรานแซกชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Transaction คือ 'ทรานแซกชัน'"),
    "ออฟชั่น": (["ออปชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Option คือ 'ออปชัน'"),
    "ออปชั่น": (["ออปชัน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Option คือ 'ออปชัน' (ไม่มีไม้เอก)"),
    "อีเมล์": (["อีเมล"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Email คือ 'อีเมล' (ไม่มีตัวการันต์)"),
    "โปรเจ็ค": (["โปรเจกต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Project คือ 'โปรเจกต์'"),
    "โปรเจค": (["โปรเจกต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Project คือ 'โปรเจกต์'"),
    "โปรเจ็คต์": (["โปรเจกต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Project คือ 'โปรเจกต์' (ไม่มีไม้ไต่คู้)"),
    "อัพเดท": (["อัปเดต"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Update คือ 'อัปเดต'"),
    "อัปเดท": (["อัปเดต"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Update คือ 'อัปเดต' (ใช้ ต)"),
    "อัพเดต": (["อัปเดต"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Update คือ 'อัปเดต' (ใช้ ป)"),
    "อัพโหลด": (["อัปโหลด"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Upload คือ 'อัปโหลด' (ใช้ ป)"),
    "อัพเกรด": (["อัปเกรด"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Upgrade คือ 'อัปเกรด' (ใช้ ป)"),
    "อินเตอร์เน็ต": (["อินเทอร์เน็ต"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Internet คือ 'อินเทอร์เน็ต'"),
    "อินเทอร์เนต": (["อินเทอร์เน็ต"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Internet คือ 'อินเทอร์เน็ต'"),
    "ซอฟท์แวร์": (["ซอฟต์แวร์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Software คือ 'ซอฟต์แวร์' (ใช้ ต์)"),
    "ซอฟแวร์": (["ซอฟต์แวร์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Software คือ 'ซอฟต์แวร์'"),
    "ดิจิตอล": (["ดิจิทัล"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Digital คือ 'ดิจิทัล'"),
    "คอมเมนท์": (["คอมเมนต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Comment คือ 'คอมเมนต์' (ใช้ ต์)"),
    "คอมเม้นท์": (["คอมเมนต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Comment คือ 'คอมเมนต์'"),
    "คอมเม้นต์": (["คอมเมนต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Comment คือ 'คอมเมนต์'"),
    "เปอร์เซ็น": (["เปอร์เซ็นต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Percent คือ 'เปอร์เซ็นต์' (มี ต์)"),
    "เปอร์เซนต์": (["เปอร์เซ็นต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Percent คือ 'เปอร์เซ็นต์' (มีไม้ไต่คู้)"),
    "ล็อคอิน": (["ล็อกอิน"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Login คือ 'ล็อกอิน' (ใช้ ก)"),
    "ล็อคเอาท์": (["ล็อกเอาต์"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Logout คือ 'ล็อกเอาต์'"),
    "พาสเวิร์ด": (["พาสเวิร์ด", "รหัสผ่าน"], "misspelled", ""),  # valid guard
    "ไลบรารี่": (["ไลบรารี"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Library คือ 'ไลบรารี' (ไม่มีไม้เอก)"),
    "สเปค": (["สเปก"], "misspelled", "คำทับศัพท์ราชบัณฑิตฯ ของ Spec คือ 'สเปก' (ใช้ ก)"),
    # การใช้ คะ / ค่ะ ผิดวรรณยุกต์ในคำลงท้ายตายตัว
    "นะค่ะ": (["นะคะ"], "semantic", "คำลงท้าย 'นะคะ' ต้องใช้เสียงตรี ('คะ' ไม่มีไม้เอก) เสมอ"),
    "สวัสดีคะ": (["สวัสดีค่ะ"], "semantic", "คำทักทายบอกเล่า 'สวัสดีค่ะ' ต้องใช้เสียงโท ('ค่ะ' มีไม้เอก)"),
    "ขอบคุณคะ": (["ขอบคุณค่ะ"], "semantic", "คำกล่าวขอบคุณ 'ขอบคุณค่ะ' ต้องใช้เสียงโท ('ค่ะ' มีไม้เอก)"),
    "ใช่คะ": (["ใช่ค่ะ"], "semantic", "คำตอบรับ 'ใช่ค่ะ' ต้องใช้เสียงโท ('ค่ะ' มีไม้เอก)"),
    "ได้คะ": (["ได้ค่ะ"], "semantic", "คำตอบรับ 'ได้ค่ะ' ต้องใช้เสียงโท ('ค่ะ' มีไม้เอก)"),
    "เรียบร้อยคะ": (["เรียบร้อยค่ะ"], "semantic", "คำบอกเล่า 'เรียบร้อยค่ะ' ต้องใช้เสียงโท ('ค่ะ' มีไม้เอก)"),
    "ยินดีคะ": (["ยินดีค่ะ"], "semantic", "คำบอกเล่า 'ยินดีค่ะ' ต้องใช้เสียงโท ('ค่ะ' มีไม้เอก)"),
    "ขอโทษคะ": (["ขอโทษค่ะ"], "semantic", "คำกล่าวขอโทษ 'ขอโทษค่ะ' ต้องใช้เสียงโท ('ค่ะ' มีไม้เอก)"),
}

# ลบรายการที่เป็น valid guard (suggestions หรือ message ว่าง)
ACTIVE_THAI_MISSPELLINGS: Dict[str, Tuple[List[str], str, str]] = {
    k: v for k, v in KNOWN_THAI_MISSPELLINGS.items() if v[2]
}

# ── Layer 1B: คำภาษาอังกฤษที่พบบ่อยในเอกสาร IT/Business และมักสะกดผิด ──
KNOWN_ENGLISH_MISSPELLINGS: Dict[str, Tuple[List[str], str]] = {
    "recieve": (["receive"], "สะกดผิดตามหลัก 'i before e except after c' -> 'receive'"),
    "occured": (["occurred"], "สะกดผิด ต้องเติม r สองตัวเมื่อเติม -ed -> 'occurred'"),
    "occurence": (["occurrence"], "สะกดผิด ต้องมี r สองตัว -> 'occurrence'"),
    "seperate": (["separate"], "สะกดผิด ต้องใช้ 'a' ตรงกลาง -> 'separate'"),
    "definately": (["definitely"], "สะกดผิด มาจากรากศัพท์ finite -> 'definitely'"),
    "accomodate": (["accommodate"], "สะกดผิด ต้องมี c สองตัวและ m สองตัว -> 'accommodate'"),
    "enviroment": (["environment"], "สะกดผิด ตกตัว 'n' หน้า m -> 'environment'"),
    "goverment": (["government"], "สะกดผิด ตกตัว 'n' หน้า m -> 'government'"),
    "managment": (["management"], "สะกดผิด ตกตัว 'e' หลัง g -> 'management'"),
    "requirment": (["requirement"], "สะกดผิด ตกตัว 'e' หลัง r -> 'requirement'"),
    "requirments": (["requirements"], "สะกดผิด ตกตัว 'e' หลัง r -> 'requirements'"),
    "autentication": (["authentication"], "สะกดผิด ตกตัว 'h' -> 'authentication'"),
    "authetication": (["authentication"], "สะกดผิด ตกตัว 'n' -> 'authentication'"),
    "authorisation": (["authorization", "authorisation"], ""),  # valid UK spelling
    "configuration": (["configuration"], ""),
    "configurtion": (["configuration"], "สะกดผิด ตกตัว 'a' -> 'configuration'"),
    "performace": (["performance"], "สะกดผิด ตกตัว 'n' -> 'performance'"),
    "maintenace": (["maintenance"], "สะกดผิด ตกตัว 'n' -> 'maintenance'"),
    "maintainance": (["maintenance"], "สะกดผิด ต้องสะกดว่า 'maintenance'"),
    "independant": (["independent"], "สะกดผิด ลงท้ายด้วย -ent -> 'independent'"),
    "neccessary": (["necessary"], "สะกดผิด มี c ตัวเดียวและ s สองตัว -> 'necessary'"),
    "necesary": (["necessary"], "สะกดผิด ต้องมี s สองตัว -> 'necessary'"),
    "succesful": (["successful"], "สะกดผิด ต้องมี c สองตัวและ s สองตัว -> 'successful'"),
    "successfull": (["successful"], "สะกดผิด ลงท้ายด้วย -ful (l ตัวเดียว) -> 'successful'"),
    "untill": (["until"], "สะกดผิด ใช้ l ตัวเดียว -> 'until'"),
    "wich": (["which"], "สะกดผิด ตกตัว 'h' -> 'which'"),
    "teh": (["the"], "พิมพ์สลับตำแหน่ง (Typo) -> 'the'"),
    "adn": (["and"], "พิมพ์สลับตำแหน่ง (Typo) -> 'and'"),
    "form": (["form"], ""),
    "calender": (["calendar"], "สะกดผิด ปฏิทินภาษาอังกฤษสะกดด้วย -ar -> 'calendar'"),
    "priviledge": (["privilege"], "สะกดผิด ไม่มีตัว 'd' -> 'privilege'"),
    "refered": (["referred"], "สะกดผิด ต้องเติม r สองตัว -> 'referred'"),
    "transffered": (["transferred"], "สะกดผิด มี f ตัวเดียวและ r สองตัว -> 'transferred'"),
    "architechture": (["architecture"], "สะกดผิด ไม่มี 'h' หลัง c ตัวที่สอง -> 'architecture'"),
    "infrastucture": (["infrastructure"], "สะกดผิด ตกตัว 'r' หลัง st -> 'infrastructure'"),
    "documenation": (["documentation"], "สะกดผิด ตกตัว 't' -> 'documentation'"),
    "specifcation": (["specification"], "สะกดผิด ตกตัว 'i' -> 'specification'"),
    "availibility": (["availability"], "สะกดผิด ต้องใช้ 'a' หลัง l -> 'availability'"),
    "compatability": (["compatibility"], "สะกดผิด ต้องใช้ 'i' หลัง t -> 'compatibility'"),
    "resposibility": (["responsibility"], "สะกดผิด ตกตัว 'n' -> 'responsibility'"),
    "vulnerbility": (["vulnerability"], "สะกดผิด ตกตัว 'a' -> 'vulnerability'"),
}

ACTIVE_ENGLISH_MISSPELLINGS: Dict[str, Tuple[List[str], str]] = {
    k: v for k, v in KNOWN_ENGLISH_MISSPELLINGS.items() if v[1]
}

# รายการคำศัพท์เทคนิค/ตัวย่อ/ชื่อเฉพาะด้าน Software & QA ที่ไม่ควรตรวจว่าสะกดผิด
TECH_ENGLISH_WHITELIST: Set[str] = {
    "api", "apis", "sdk", "sdks", "ui", "ux", "qa", "ocr", "srs", "sdd", "tor", "sow", "uat", "sit",
    "jwt", "oauth", "sso", "mfa", "otp", "tls", "ssl", "https", "http", "url", "urls", "uri",
    "sql", "nosql", "postgresql", "postgres", "mysql", "sqlite", "mongodb", "redis", "supabase",
    "json", "yaml", "yml", "xml", "csv", "xlsx", "pdf", "pdfs", "docx", "jpg", "jpeg", "png", "webp", "svg",
    "html", "css", "scss", "js", "ts", "jsx", "tsx", "svelte", "react", "vue", "angular", "nextjs", "vite",
    "python", "flask", "fastapi", "django", "gunicorn", "uvicorn", "pytest", "playwright", "cypress", "k6",
    "docker", "kubernetes", "k8s", "nginx", "apache", "linux", "ubuntu", "windows", "macos", "ios", "android",
    "github", "gitlab", "bitbucket", "jira", "confluence", "clickup", "figma", "canva", "postman", "swagger",
    "gemini", "openai", "anthropic", "claude", "zhipuai", "glm", "ollama", "qwen", "langchain", "langgraph",
    "multimodal", "llm", "llms", "rag", "embeddings", "vector", "vectors", "chunk", "chunks", "token", "tokens",
    "webhook", "webhooks", "async", "await", "cors", "csrf", "xss", "sqli", "owasp", "rbac", "crud",
    "frontend", "backend", "fullstack", "microservice", "microservices", "serverless", "devops", "cicd",
    "navbar", "topbar", "sidebar", "dropzone", "tooltip", "modal", "modals", "dropdown", "wireframe", "wireframes",
    "mockup", "mockups", "sitemap", "flowchart", "mermaid", "traceability", "kpi", "kpis", "sla", "eta",
    "admin", "admins", "username", "usernames", "login", "logout", "signin", "signup", "checkbox", "textarea",
    "metadata", "config", "configs", "param", "params", "regex", "boolean", "nullable", "uuid", "timestamp",
    "spectra", "foodsmile", "manifest", "carmanifest", "tiffa", "pomr", "pdpa", "gdpr", "iso", "ieee",
}

_eng_spellchecker = None


def _get_english_spellchecker():
    """Lazy-load pyspellchecker instance พร้อมเติมคำศัพท์ IT/Domain"""
    global _eng_spellchecker
    if _eng_spellchecker is not None:
        return _eng_spellchecker
    try:
        from spellchecker import SpellChecker
        sc = SpellChecker(language='en', distance=1)
        sc.word_frequency.load_words(list(TECH_ENGLISH_WHITELIST))
        _eng_spellchecker = sc
    except Exception as e:
        logger.debug(f"pyspellchecker unavailable: {e}")
        _eng_spellchecker = False
    return _eng_spellchecker


def _build_line_map(text: str) -> List[int]:
    """Returns list of newline character indices."""
    return [i for i, c in enumerate(text) if c == '\n']


def _get_line(pos: int, newline_positions: List[int]) -> int:
    """Return 1-indexed line number for a character position."""
    return bisect.bisect_left(newline_positions, pos) + 1


def _load_all_custom_vocabulary() -> Tuple[List[str], Set[str]]:
    """
    โหลดคำศัพท์ที่อนุญาตทั้งหมดจาก:
    1) data/thai_custom_words.txt (คำที่ผู้ใช้เพิ่มผ่านปุ่มพจนานุกรม)
    2) data/user_words.txt (คลังคำศัพท์ IT มาตรฐานของระบบ)
    คืนค่า (custom_words_list_for_prompt, all_allowed_lower_set)
    """
    base_dir = os.path.dirname(os.path.dirname(__file__))
    custom_words_path = os.path.join(base_dir, 'data', 'thai_custom_words.txt')
    user_words_path = os.path.join(base_dir, 'data', 'user_words.txt')

    placeholder_ignore = {'กรุณาเพิ่มคำของคุณด้านล่าง', 'ทดสอบคำพิเศษ999'}
    custom_prompt_words: List[str] = []
    allowed_set: Set[str] = set(TECH_ENGLISH_WHITELIST)

    for path, is_user_custom in ((custom_words_path, True), (user_words_path, False)):
        if not os.path.exists(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    w = line.strip()
                    if not w or w.startswith('#') or w in placeholder_ignore:
                        continue
                    allowed_set.add(w.lower())
                    if is_user_custom:
                        custom_prompt_words.append(w)
        except Exception as e:
            logger.error(f"Error loading vocabulary from {path}: {e}")

    return custom_prompt_words, allowed_set


def _tokenize_thai_and_english_counts(text: str) -> Tuple[int, int, Set[int]]:
    """
    ใช้ PyThaiNLP (newmm) ในการตัดคำภาษาไทยจริง (ไม่ตัดแค่ตามช่องว่าง)
    คืนค่า:
    - thai_word_count: จำนวนคำภาษาไทยจริง
    - eng_word_count: จำนวนคำภาษาอังกฤษจริง
    - thai_word_boundaries: เซตของตำแหน่ง index รอยต่อคำในข้อความ เพื่อป้องกันการจับ substring กลางคำอื่น
    """
    thai_word_count = 0
    eng_word_count = 0
    boundaries: Set[int] = {0, len(text)}

    try:
        from pythainlp.tokenize import word_tokenize
        tokens = word_tokenize(text, engine="newmm", keep_whitespace=True)
        pos = 0
        for tok in tokens:
            boundaries.add(pos)
            pos += len(tok)
            boundaries.add(pos)
            stripped = tok.strip()
            if not stripped:
                continue
            if THAI_CHAR_RE.search(stripped):
                thai_word_count += 1
            elif ENG_WORD_RE.match(stripped):
                eng_word_count += 1
        return thai_word_count, eng_word_count, boundaries
    except Exception:
        # Fallback หากไม่มี pythainlp
        for m in THAI_CHUNK_RE.finditer(text):
            boundaries.add(m.start())
            boundaries.add(m.end())
            # ประมาณจำนวนคำไทยจากความยาวเฉลี่ย 4.2 ตัวอักษรต่อคำ
            thai_word_count += max(1, round(len(m.group()) / 4.2))
        for m in ENG_TOKEN_FINDER_RE.finditer(text):
            boundaries.add(m.start())
            boundaries.add(m.end())
            eng_word_count += 1
        return thai_word_count, eng_word_count, boundaries


def _build_ignored_intervals(text: str) -> List[Tuple[int, int]]:
    """สร้างช่วงตำแหน่งของ URL, Email, Code Block ที่ห้ามตรวจเป็นคำผิด"""
    return [(m.start(), m.end()) for m in IGNORE_SPAN_RE.finditer(text)]


def _is_in_ignored_span(pos: int, end: int, ignored_spans: List[Tuple[int, int]]) -> bool:
    for s, e in ignored_spans:
        if pos < e and end > s:
            return True
    return False


def _run_layer1_deterministic_scan(
    text: str,
    allowed_lower: Set[str],
    thai_boundaries: Set[int],
    ignored_spans: List[Tuple[int, int]],
    lang_mode: str = 'tha+eng'
) -> List[Dict[str, Any]]:
    """
    Layer 1: ตรวจสอบคำผิดด้วยพจนานุกรมคำมักเขียนผิดราชบัณฑิตฯ + ตรวจสระเพี้ยน PDF + English SpellChecker
    """
    check_thai = lang_mode in ('tha+eng', 'tha', 'all')
    check_eng = lang_mode in ('tha+eng', 'eng', 'all')
    candidates: List[Dict[str, Any]] = []

    # 1A. ตรวจคำผิดภาษาไทยจากคลังคำมักเขียนผิดราชบัณฑิตฯ
    if check_thai:
        for wrong_word, (suggs, err_type, reason) in ACTIVE_THAI_MISSPELLINGS.items():
            if wrong_word.lower() in allowed_lower:
                continue
            start = 0
            while True:
                idx = text.find(wrong_word, start)
                if idx == -1:
                    break
                end = idx + len(wrong_word)
                start = end
                if _is_in_ignored_span(idx, end, ignored_spans):
                    continue
                # สำหรับคำสั้น (<= 4 ตัวอักษร) ต้องอยู่ตรงรอยต่อคำเพื่อไม่ให้ไปจับกลางคำอื่น
                if len(wrong_word) <= 4 and (idx not in thai_boundaries and end not in thai_boundaries):
                    continue
                candidates.append({
                    "token": wrong_word,
                    "suggestions": suggs,
                    "error_type": err_type,
                    "lang": "thai",
                    "message": reason,
                    "exact_span": (idx, end),
                    "source": "lexicon_th"
                })

        # 1B. ตรวจอาการสระอาสลับกับวรรณยุกต์จาก PDF เช่น 'คา้' -> 'ค้า', 'หนา้' -> 'หน้า'
        for m in re.finditer(r"(?:ห[งญณนมยรลว]|[กขคตปผพ][รลว]|[\u0E01-\u0E2E])\u0E32[\u0E48-\u0E4B]", text):
            if _is_in_ignored_span(m.start(), m.end(), ignored_spans):
                continue
            glitched = m.group()
            # สลับวรรณยุกต์มาไว้หน้าสระอา
            fixed = glitched[:-2] + glitched[-1] + "\u0E32"
            candidates.append({
                "token": glitched,
                "suggestions": [fixed],
                "error_type": "misspelled",
                "lang": "thai",
                "message": "ลำดับวรรณยุกต์และสระอาสลับตำแหน่งจากการสกัด PDF",
                "exact_span": (m.start(), m.end()),
                "source": "pdf_glitch_th"
            })

    # 1C. ตรวจคำผิดภาษาอังกฤษ
    if check_eng:
        sc = _get_english_spellchecker()
        if sc:
            sc.word_frequency.load_words([w for w in allowed_lower if w.isascii()])

        for m in ENG_TOKEN_FINDER_RE.finditer(text):
            if _is_in_ignored_span(m.start(), m.end(), ignored_spans):
                continue
            word = m.group()
            lower_w = word.lower()

            if lower_w in allowed_lower or len(word) <= 2:
                continue
            # ข้ามตัวย่อ ALL CAPS (เช่น SRS, UAT, API, HTTP) หรือคำที่มีตัวพิมพ์ใหญ่ผสมกลางคำ (camelCase / PascalCase เช่น FoodSmile, GitHub)
            if word.isupper() or any(c.isupper() for c in word[1:]):
                continue
            if "'" in word or "-" in word:
                continue

            # เช็คกับคลังคำอังกฤษที่มักสะกดผิดแน่ๆ ก่อน
            if lower_w in ACTIVE_ENGLISH_MISSPELLINGS:
                suggs, reason = ACTIVE_ENGLISH_MISSPELLINGS[lower_w]
                if word[0].isupper():
                    suggs = [s.capitalize() for s in suggs]
                candidates.append({
                    "token": word,
                    "suggestions": suggs,
                    "error_type": "misspelled",
                    "lang": "english",
                    "message": reason,
                    "exact_span": (m.start(), m.end()),
                    "source": "lexicon_en"
                })
            elif sc and len(word) >= 4:
                # ตรวจสอบด้วย pyspellchecker เฉพาะคำที่ไม่อยู่ในคลังคำภาษาอังกฤษ
                if lower_w in sc.unknown([lower_w]):
                    raw_cands = list(sc.candidates(lower_w) or [])
                    top_corr = sc.correction(lower_w)
                    ordered = []
                    if top_corr and top_corr != lower_w:
                        ordered.append(top_corr)
                    for c in raw_cands:
                        if c != lower_w and c not in ordered:
                            ordered.append(c)
                        if len(ordered) >= 3:
                            break
                    if ordered:
                        if word[0].isupper():
                            ordered = [s.capitalize() for s in ordered]
                        candidates.append({
                            "token": word,
                            "suggestions": ordered,
                            "error_type": "misspelled",
                            "lang": "english",
                            "message": f"ไม่พบในพจนานุกรมภาษาอังกฤษ อาจสะกดผิด (แนะนำ: {', '.join(ordered[:2])})",
                            "exact_span": (m.start(), m.end()),
                            "source": "pyspell_en"
                        })

    return candidates


def _find_safe_occurrences(
    text: str,
    token: str,
    lang: str,
    context_snippet: str,
    thai_boundaries: Set[int],
    ignored_spans: List[Tuple[int, int]]
) -> List[Tuple[int, int]]:
    """
    ค้นหาตำแหน่งของคำผิดในข้อความอย่างแม่นยำ:
    - สำหรับภาษาอังกฤษ: บังคับขอบเขตคำ (?<![A-Za-z'-])token(?![A-Za-z'-]) เพื่อไม่ให้คำสั้นไปตรงกลางคำอื่น
    - สำหรับภาษาไทย:
      1) หาก AI ส่ง context_snippet มา ให้ค้นหาตำแหน่งที่อยู่ในบริบทนั้นเป็นหลัก
      2) หากคำสั้น (<= 3 ตัวอักษร เช่น 'คะ', 'ใน', 'การ') ต้องมีขอบเขตคำจาก PyThaiNLP รองรับ ไม่ให้ไปจับกลางคำเช่น 'คะแนน' หรือ 'คณะ'
    """
    if not token:
        return []

    matches: List[Tuple[int, int]] = []
    if lang == 'english' or ENG_WORD_RE.match(token):
        pattern = re.compile(r"(?<![A-Za-z'-])" + re.escape(token) + r"(?![A-Za-z'-])")
        for m in pattern.finditer(text):
            if not _is_in_ignored_span(m.start(), m.end(), ignored_spans):
                matches.append((m.start(), m.end()))
    else:
        start = 0
        while True:
            idx = text.find(token, start)
            if idx == -1:
                break
            end = idx + len(token)
            start = end
            if _is_in_ignored_span(idx, end, ignored_spans):
                continue

            # ป้องกันปัญหาคำไทยสั้นๆ ไปจับกลางคำอื่น (เช่น 'คะ' ใน 'คะแนน', 'คณะ', 'วิเคราะห์')
            if len(token) <= 3:
                # ต้องมีจุดเริ่มต้นและจุดสิ้นสุดตรงกับขอบเขตคำของ PyThaiNLP หรือเป็นช่องว่าง/เครื่องหมายวรรคตอน
                left_ok = (idx in thai_boundaries) or (idx == 0) or (not THAI_CHAR_RE.match(text[idx - 1]))
                right_ok = (end in thai_boundaries) or (end == len(text)) or (not THAI_CHAR_RE.match(text[end]))
                if not (left_ok and right_ok):
                    continue
            matches.append((idx, end))

    # หากมีหลายจุดและ AI ระบุ context มา ให้เลือกเฉพาะจุดที่ตรงกับ context
    if len(matches) > 1 and context_snippet and len(context_snippet.strip()) > len(token):
        ctx_clean = context_snippet.strip()
        anchored = []
        for s, e in matches:
            win_start = max(0, s - 45)
            win_end = min(len(text), e + 45)
            window = text[win_start:win_end]
            if ctx_clean in window:
                anchored.append((s, e))
        if anchored:
            return anchored

    return matches


def spellcheck_text(
    text: str,
    include_suggestions: bool = True,
    lang: str = 'tha+eng'
) -> Dict[str, Any]:
    """
    ตรวจสอบคำผิดในข้อความทั้งภาษาไทยและอังกฤษด้วย 3-Layer Hybrid Engine:
    - Layer 1: พจนานุกรมคำมักเขียนผิดราชบัณฑิตฯ + สระเพี้ยน PDF + English SpellChecker
    - Layer 2: Google Gemini 2.5 Flash Contextual Proofreader
    - Layer 3: Word-Boundary & Context-Anchored Span Matcher
    """
    if not text or not text.strip():
        return _empty_spell_check(text or "")

    custom_prompt_words, allowed_lower = _load_all_custom_vocabulary()
    thai_word_count, eng_word_count, thai_boundaries = _tokenize_thai_and_english_counts(text)
    ignored_spans = _build_ignored_intervals(text)

    # ── Layer 1: Deterministic Lexicon & Rule Pre-Scan ──
    layer1_candidates = _run_layer1_deterministic_scan(
        text=text,
        allowed_lower=allowed_lower,
        thai_boundaries=thai_boundaries,
        ignored_spans=ignored_spans,
        lang_mode=lang
    )

    # แยก candidate ที่มั่นใจ 100% (จากคลังคำผิดราชบัณฑิตฯ / คลังคำผิดอังกฤษตายตัว / สระเพี้ยน PDF)
    high_confidence_l1 = [c for c in layer1_candidates if c.get("source") in ("lexicon_th", "pdf_glitch_th", "lexicon_en")]
    pyspell_hints = [c["token"] for c in layer1_candidates if c.get("source") == "pyspell_en"]

    custom_instruction = (
        f"Custom/Domain vocabulary to treat as 100% CORRECT (NEVER report these as errors): {', '.join(custom_prompt_words)}."
        if custom_prompt_words else ""
    )
    hint_instruction = (
        f"Pay extra attention to these potential English typos detected by dictionary pre-scan (verify in context before reporting): {', '.join(dict.fromkeys(pyspell_hints[:25]))}."
        if pyspell_hints else ""
    )
    lang_scope_instruction = {
        'tha': "ONLY report Thai language spelling/semantic errors. Ignore English words completely.",
        'eng': "ONLY report English language spelling/grammar errors. Ignore Thai words completely.",
    }.get(lang, "Report both Thai and English spelling, transliteration, typographical, and context-based semantic errors.")

    system_prompt = f"""You are a senior Thai Royal Institute (ราชบัณฑิตยสภา) and English linguistic proofreader for enterprise software & QA documents.
{lang_scope_instruction}

Check thoroughly for:
1. Thai Spelling & Royal Institute Standard (พจนานุกรมราชบัณฑิตยสภา):
   - Misspelled words (e.g., อนุญาติ -> อนุญาต, สังเกตุ -> สังเกต, กฏหมาย -> กฎหมาย, ปรากฎ -> ปรากฏ, มาตราฐาน -> มาตรฐาน, สัมนา -> สัมมนา, รสชาด -> รสชาติ, ผูกพันธ์ -> ผูกพัน).
   - Standard Thai transliterations (คำทับศัพท์ราชบัณฑิตฯ: แอปพลิเคชัน, ฟังก์ชัน, เวอร์ชัน, โปรเจกต์, อัปเดต, อัปโหลด, อีเมล, ลิงก์, เว็บไซต์, ซอฟต์แวร์, ดิจิทัล, กราฟิก, คลินิก, เปอร์เซ็นต์).
   - Thai PDF vowel/tone-mark glitches (e.g., คา้ -> ค้า, หนา้ -> หน้า, เอกสา ร -> เอกสาร).
2. Thai Contextual & Semantic Errors (คำพ้องเสียง/ใช้ผิดบริบท):
   - สำรับ vs สำหรับ, คะ vs ค่ะ (e.g., นะค่ะ -> นะคะ, สวัสดีคะ -> สวัสดีค่ะ, ขอบคุณคะ -> ขอบคุณค่ะ), ขั้นตอน vs คั้นตอน, การณ์ vs การ, ผลลัพธ์ vs ผลลัพท์.
3. English Spelling, Grammar & Homophones:
   - Typos (e.g., recieve -> receive, enviroment -> environment, requirment -> requirement, authetication -> authentication, seperately -> separately).
   - Wrong word in context (e.g., their/there, affect/effect, Compliment/Complement).

CRITICAL GUARDRAILS:
- ONLY report genuine errors. Do NOT flag valid technical terms, acronyms (SRS, UAT, API, OAuth, JSON, SQL, PDF), proper nouns, project codes, or variable names.
- Ignore markdown table syntax (|---|), code blocks, URLs, emails, file paths, and numbers.
- {custom_instruction}
- {hint_instruction}
- "token" MUST be the EXACT single misspelled word or short 2-word phrase as it appears in the text (never return a whole sentence as token).
- "context" MUST be a short 4-8 word verbatim substring from the text containing the token so its exact position can be anchored.
- "message" MUST be a concise Thai explanation (1 short sentence) explaining why it is wrong.

Return STRICTLY raw JSON matching this schema:
{{
  "errors": [
    {{
      "token": "exact_misspelled_word",
      "context": "short verbatim surrounding phrase containing the token",
      "suggestions": ["best_correction", "alternative_correction"],
      "error_type": "misspelled",
      "lang": "thai",
      "message": "คำอธิบายสั้นๆ ว่าผิดเพราะอะไรและควรแก้เป็นอะไร"
    }}
  ]
}}
Use "error_type": "misspelled" for spelling/transliteration/typo errors, or "semantic" for context/tone/homophone errors.
Use "lang": "thai" or "english".
If there are no errors, return {{"errors": []}}."""

    raw_env_model = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')
    # ป้องกันกรณี .env ตั้งค่าเป็นโมเดลที่ไม่มีอยู่จริง เช่น gemini-3.1-flash
    if '3.1' in raw_env_model:
        raw_env_model = 'gemini-2.5-flash'

    ai_errors: List[Dict[str, Any]] = []
    try:
        from ocr_engine import get_all_api_keys, _get_gemini_client
        keys = get_all_api_keys()
        if keys:
            from google.genai import types

            raw_fallback_models = [raw_env_model, 'gemini-2.5-flash', 'gemini-2.5-flash-lite']
            seen = set()
            fallback_models = [m for m in raw_fallback_models if not (m in seen or seen.add(m))]

            response = None
            used_model = 'gemini-2.5-flash'
            for key_idx in range(len(keys)):
                client = _get_gemini_client(key_idx)
                for current_model in fallback_models:
                    try:
                        logger.info(f"Calling Gemini [Key #{key_idx+1}] ({current_model}) for hybrid spellcheck...")
                        response = client.models.generate_content(
                            model=current_model,
                            contents=f"Proofread this document text carefully:\n\n{text}",
                            config=types.GenerateContentConfig(
                                system_instruction=system_prompt,
                                temperature=0.0,
                                response_mime_type="application/json",
                            )
                        )
                        if response and response.text:
                            used_model = current_model
                            break
                    except Exception as model_err:
                        logger.warning(f"Gemini Spellcheck error with Key #{key_idx+1} {current_model}: {model_err}")
                        continue
                if response and response.text:
                    break

            if response and response.text:
                if hasattr(response, 'usage_metadata'):
                    try:
                        from db_ingestion import log_api_usage
                        actual_model = getattr(response, 'model_version', None) or used_model
                        log_api_usage("Spell_Check", actual_model, response.usage_metadata)
                    except Exception as usage_err:
                        logger.error(f"Failed to log API usage: {usage_err}")

                content = (response.text or "").strip()
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]

                data = json.loads(content.strip())
                ai_errors = data.get("errors", []) or []
                logger.info(f"Gemini hybrid spellcheck found {len(ai_errors)} AI errors (+ {len(high_confidence_l1)} deterministic rule matches).")
        else:
            logger.warning("GOOGLE_API_KEY is missing; using Layer 1 deterministic spellcheck fallback.")
    except Exception as e:
        logger.error(f"Gemini Spellcheck Error (falling back to Layer 1 deterministic matches): {e}")

    # ── Layer 3: Merge Layer 1 (High-Confidence Lexicon) + Layer 2 (Gemini Context AI) with Safe Boundaries ──
    newline_positions = _build_line_map(text)
    intervals: List[Tuple[int, int, Dict[str, Any]]] = []

    # 3A. ใส่ผลลัพธ์จาก Layer 1 ที่มีตำแหน่ง exact_span แน่นอนก่อน
    for c in high_confidence_l1:
        s, e = c["exact_span"]
        intervals.append((s, e, c))

    # หาก Gemini ไม่คืนผลลัพธ์ (เช่น quota เต็ม) ให้นำผลจาก pyspellchecker ของ Layer 1 มาช่วยด้วย
    if not ai_errors:
        for c in layer1_candidates:
            if c.get("source") == "pyspell_en":
                s, e = c["exact_span"]
                intervals.append((s, e, c))

    # 3B. ประมวลผลรายการคำผิดจาก Gemini AI พร้อมกรองคำใน Custom Dictionary และจับขอบเขตคำอย่างปลอดภัย
    check_thai = lang in ('tha+eng', 'tha', 'all')
    check_eng = lang in ('tha+eng', 'eng', 'all')

    for err in ai_errors:
        if not isinstance(err, dict):
            continue
        token = (err.get("token") or "").strip()
        if not token or token not in text:
            continue
        if token.lower() in allowed_lower:
            continue

        suggestions = [str(s).strip() for s in (err.get("suggestions") or []) if str(s).strip() and str(s).strip() != token]
        # หาก AI บอกว่าผิดแต่คำแนะนำเหมือนคำเดิมเป๊ะ หรือไม่มีคำแนะนำและเป็นคำศัพท์เทคนิค ให้ข้าม
        if not suggestions and token.lower() in TECH_ENGLISH_WHITELIST:
            continue

        detected_lang = err.get("lang")
        if THAI_CHAR_RE.search(token):
            detected_lang = 'thai'
        elif ENG_WORD_RE.match(token) or token.isascii():
            detected_lang = 'english'
        else:
            detected_lang = 'other'

        if detected_lang == 'thai' and not check_thai:
            continue
        if detected_lang == 'english' and not check_eng:
            continue

        context_snippet = err.get("context") or ""
        safe_spans = _find_safe_occurrences(
            text=text,
            token=token,
            lang=detected_lang,
            context_snippet=context_snippet,
            thai_boundaries=thai_boundaries,
            ignored_spans=ignored_spans
        )

        err_type = err.get("error_type", "misspelled")
        if err_type not in ("misspelled", "semantic", "format"):
            err_type = "misspelled"

        message = (err.get("message") or "").strip()
        if not message:
            if err_type == "semantic":
                message = "ใช้คำไม่ตรงตามบริบทของประโยค"
            elif detected_lang == "english":
                message = "ตัวสะกดภาษาอังกฤษไม่ถูกต้อง"
            else:
                message = "ตัวสะกดไม่ตรงตามพจนานุกรมมาตรฐาน"

        normalized_err = {
            "token": token,
            "suggestions": suggestions,
            "error_type": err_type,
            "lang": detected_lang,
            "message": message
        }

        for s, e in safe_spans:
            intervals.append((s, e, normalized_err))

    # 3C. เรียงลำดับตามตำแหน่งเริ่มต้น และตัดรายการที่ซ้อนทับกัน (เลือกคำที่ยาวกว่า หรือรายการจาก Layer 1 ที่มีคำอธิบายชัดเจน)
    intervals.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    non_overlapping: List[Tuple[int, int, Dict[str, Any]]] = []
    last_end = 0
    for itv in intervals:
        start, end, err = itv
        if start >= last_end:
            non_overlapping.append(itv)
            last_end = end

    # 3D. สร้างผลลัพธ์ tokens และ final_error_list
    result_tokens: List[Dict[str, Any]] = []
    final_error_list: List[Dict[str, Any]] = []

    thai_errors = 0
    eng_errors = 0
    semantic_errors = 0
    current_idx = 0

    for start, end, err in non_overlapping:
        if start > current_idx:
            prefix = text[current_idx:start]
            for pt in re.split(r'(\s+)', prefix):
                if not pt:
                    continue
                pt_lang = 'other'
                if THAI_CHAR_RE.search(pt):
                    pt_lang = 'thai'
                elif ENG_WORD_RE.search(pt):
                    pt_lang = 'english'
                result_tokens.append({
                    'token': pt,
                    'lang': pt_lang,
                    'is_correct': True,
                    'suggestions': [],
                    'position': current_idx,
                    'line_number': _get_line(current_idx, newline_positions),
                    'error_type': None
                })
                current_idx += len(pt)

        token_str = text[start:end]
        error_type = err.get("error_type", "misspelled")
        tok_lang = err.get("lang", "other")
        if THAI_CHAR_RE.search(token_str):
            tok_lang = 'thai'
        elif ENG_WORD_RE.search(token_str) or token_str.isascii():
            tok_lang = 'english'

        if error_type == "semantic":
            semantic_errors += 1
        else:
            if tok_lang == 'thai':
                thai_errors += 1
            elif tok_lang == 'english':
                eng_errors += 1

        suggestions = err.get("suggestions", []) if include_suggestions else []
        message = err.get("message", "")
        line_num = _get_line(start, newline_positions)

        result_tokens.append({
            'token': token_str,
            'lang': tok_lang,
            'is_correct': False,
            'suggestions': suggestions,
            'position': start,
            'line_number': line_num,
            'error_type': error_type,
            'message': message
        })

        final_error_list.append({
            'token': token_str,
            'lang': tok_lang,
            'line_number': line_num,
            'suggestions': suggestions,
            'position': start,
            'error_type': error_type,
            'message': message
        })
        current_idx = end

    if current_idx < len(text):
        suffix = text[current_idx:]
        for pt in re.split(r'(\s+)', suffix):
            if not pt:
                continue
            pt_lang = 'other'
            if THAI_CHAR_RE.search(pt):
                pt_lang = 'thai'
            elif ENG_WORD_RE.search(pt):
                pt_lang = 'english'
            result_tokens.append({
                'token': pt,
                'lang': pt_lang,
                'is_correct': True,
                'suggestions': [],
                'position': current_idx,
                'line_number': _get_line(current_idx, newline_positions),
                'error_type': None
            })
            current_idx += len(pt)

    total_checked = max(thai_word_count + eng_word_count, len(final_error_list))
    total_errors = thai_errors + eng_errors + semantic_errors
    error_rate = round(total_errors / total_checked * 100, 2) if total_checked > 0 else 0

    return {
        'tokens': result_tokens,
        'errors': final_error_list,
        'summary': {
            'thai_tokens': thai_word_count,
            'english_tokens': eng_word_count,
            'total_tokens': total_checked,
            'error_count': total_errors,
            'thai_errors': thai_errors,
            'english_errors': eng_errors,
            'semantic_errors': semantic_errors,
            'error_rate': error_rate
        }
    }


def spellcheck_pages(pages: List[Dict], lang: str = 'tha+eng') -> List[Dict]:
    """ตรวจสอบคำผิดในทุกหน้าของ OCR result"""
    results = []
    for page in pages:
        spell_result = spellcheck_text(page.get('text', ''), lang=lang)
        results.append({**page, 'spell_check': spell_result})
    return results


def _empty_spell_check(text: str) -> Dict[str, Any]:
    """Fallback ในกรณีที่ข้อความว่างเปล่า"""
    thai_words, eng_words, _ = _tokenize_thai_and_english_counts(text) if text.strip() else (0, 0, set())
    return {
        'tokens': [{'token': text, 'is_correct': True, 'position': 0}] if text else [],
        'errors': [],
        'summary': {
            'thai_tokens': thai_words,
            'english_tokens': eng_words,
            'total_tokens': thai_words + eng_words,
            'error_count': 0,
            'thai_errors': 0,
            'english_errors': 0,
            'semantic_errors': 0,
            'error_rate': 0
        }
    }
