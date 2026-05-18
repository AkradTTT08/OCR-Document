# 📄 Thai OCR Spell Check System (AI Powered)

ระบบ OCR สำหรับสแกนเอกสาร PDF และรูปภาพ พร้อมตรวจสอบคำถูกคำผิดภาษาไทย 
ขับเคลื่อนด้วย **ZhipuAI (GLM-OCR และ GLM-4-Flash)** ที่มีความแม่นยำสูง เข้าใจบริบทของประโยค และรองรับมาตรฐาน **MCP (Model Context Protocol)** เพื่อเชื่อมต่อกับ AI Agent อื่นๆ ได้ทันที

## ✨ คุณสมบัติ

- 📤 **อัปโหลด PDF/รูปภาพ** แบบ Drag & Drop
- 🔍 **AI OCR (GLM-OCR)** สกัดข้อความและจัดหน้า (Layout Parsing) ได้แม่นยำที่สุด
- ✅ **AI Proofreader (GLM-4-Flash)** ตรวจคำผิดแบบวิเคราะห์บริบท (เช่น สำรับ/สำหรับ)
- 🔴 **ไฮไลท์คำผิด** พร้อมคำแนะนำบนหน้าเว็บ
- 📚 **เพิ่มคำศัพท์เฉพาะ (Custom Words)** เพื่อสอน AI ให้รู้จักศัพท์ในองค์กร
- 🤖 **รองรับ MCP Server** เสียบใช้งานร่วมกับ Cursor หรือ Claude Desktop ได้ทันที

---

## 📋 ความต้องการของระบบ (Requirements)

1. **Python** 3.9 - 3.12 ([python.org](https://python.org))
2. **Poppler** (สำหรับอ่าน PDF) - [ดาวน์โหลดที่นี่](https://github.com/oschwartz10612/poppler-windows/releases)
3. **ZhipuAI API Key** (จำเป็นต้องมีเพื่อใช้งาน AI)

---

## 🚀 การติดตั้ง

### 1. ติดตั้ง Poppler (สำหรับ PDF)
- แตกไฟล์ Poppler ไปไว้ที่ `C:\poppler\` (หรือกำหนดพาธเองในไฟล์ `.env`)

### 2. ติดตั้ง Python Packages
รันสคริปต์อัตโนมัติ หรือใช้คำสั่ง pip:
```bat
setup.bat
```
*(หรือ `pip install -r requirements.txt`)*

### 3. ตั้งค่า API Key
สร้างไฟล์ `.env` (คัดลอกจาก `.env.example`) และใส่ API Key ของคุณ:
```env
# ตั้งค่า API Key ของ ZhipuAI
ZHIPUAI_API_KEY=ใส่_api_key_ของคุณที่นี่

# (Optional) พาธของ Poppler
POPPLER_PATH=C:\poppler\Library\bin
```

---

## ▶️ วิธีการใช้งาน 1: ใช้งานผ่านหน้าเว็บ (Web UI)

รันคำสั่ง:
```bat
run.bat
```
*(หรือ `python backend/app.py`)*

จากนั้นเปิด Browser เข้าไปที่ **http://localhost:5173** คุณสามารถอัปโหลดไฟล์ PDF เพื่อทำการ OCR และตรวจคำผิดผ่านหน้าเว็บได้ทันที

---

## 🔌 วิธีการใช้งาน 2: ใช้งานผ่าน MCP (เชื่อมต่อกับ AI)

ระบบนี้รองรับ **Model Context Protocol (MCP)** ทำให้ AI อย่าง Cursor หรือ Claude สามารถ "อ่านเอกสารในเครื่องคุณ หรือจากลิงก์" ผ่านเครื่องมือนี้ได้โดยตรง!

### การเชื่อมต่อกับโปรแกรม Cursor
1. เปิดการตั้งค่า (Settings) ในโปรแกรม **Cursor**
2. ไปที่เมนู **Features** -> **MCP**
3. กดปุ่ม **+ Add New MCP Server**
4. กรอกข้อมูลดังนี้:
   - **Type:** `command`
   - **Name:** `Thai OCR Server`
   - **Command:** `python d:/OCR-Github/OCR-Document/backend/mcp_server.py`
     *(เปลี่ยน `d:/OCR-Github/OCR-Document/` เป็นพาธจริงที่คุณเก็บโปรเจกต์นี้ไว้)*
5. กดบันทึก (Save) หากไฟขึ้นสีเขียว แสดงว่าเชื่อมต่อสำเร็จ!

### ตัวอย่างการสั่งงาน AI (Prompt)
ในหน้าต่าง Chat ของ Cursor หรือ Claude คุณสามารถพิมพ์สั่ง AI ได้เลย เช่น:
> *"ช่วยโหลดรูปใบเสร็จจากไฟล์ `C:\Users\Downloads\receipt.jpg` ผ่านเครื่องมือ OCR แล้วสรุปยอดเงินให้หน่อย"*
> 
> *"ช่วยอ่าน PDF จากลิงก์ `https://example.com/doc.pdf` และสรุปเนื้อหาสำคัญ 3 ข้อ"*

*(ระบบจะมีฟังก์ชันป้องกันความปลอดภัย (SSRF Protection) ไม่ให้โหลดไฟล์จาก Private IP และจำกัดขนาดไฟล์ไม่เกิน 50MB เพื่อความปลอดภัยของเครื่องคุณ)*

---

## 📁 โครงสร้างไฟล์ (อัปเดตใหม่)

```text
OCR-Document/
├── backend/
│   ├── app.py               # Flask API (Web Server)
│   ├── mcp_server.py        # MCP Server (สำหรับเชื่อม AI Agent)
│   ├── ocr_engine.py        # ประมวลผลผ่าน GLM-OCR
│   ├── spell_checker.py     # AI Proofreader ด้วย GLM-4-Flash
│   └── dictionary_manager.py# จัดการศัพท์เฉพาะทาง
├── data/
│   └── thai_custom_words.txt # ไฟล์คำศัพท์ที่สอน AI เพิ่มเติม
├── svelte-app/              # Main Frontend (Svelte)
├── uploads/                 # โฟลเดอร์เก็บไฟล์และแคช
├── .env                     # ตั้งค่า API Key
├── requirements.txt         # ไฟล์ Packages
└── run.bat                  # สคริปต์รันหน้าเว็บ
```
