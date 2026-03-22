# 📄 Thai OCR Spell Check System

ระบบ OCR สำหรับสแกนเอกสาร PDF และตรวจสอบคำถูกคำผิดภาษาไทย โดยใช้ PaddleOCR และชุดคำศัพท์จากพจนานุกรมราชบัณฑิตยสภา (ผ่าน PyThaiNLP)

## ✨ คุณสมบัติ

- 📤 **อัปโหลด PDF** แบบ Drag & Drop
- 🔍 **OCR ภาษาไทย + อังกฤษ** ด้วย **PaddleOCR** (แม่นยำสูงกว่า Tesseract)
- ✅ **ตรวจคำผิด** โดยเทียบกับพจนานุกรมราชบัณฑิตยสภา
- 🔴 **ไฮไลท์คำผิด** พร้อมคำแนะนำ 
- 📚 **เพิ่มคำ Custom** ได้เองผ่าน UI หรือแก้ไขไฟล์
- 📥 **Export** เป็น .txt หรือรายงาน

## 📋 Requirements

| Software | Version | Download |
|----------|---------|----------|
| Python | 3.9 - 3.12 | [python.org](https://python.org) |
| Poppler | latest | [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) |

## 🚀 การติดตั้ง

### 1. ติดตั้ง Poppler (สำหรับอ่าน PDF)
- ดาวน์โหลดจาก [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
- Extract ไปที่ `C:\poppler\` (หรือพาธที่ตั้งไว้ใน `.env`)

### 2. ติดตั้ง Python dependencies
PaddleOCR จะติดตั้งโมเดลภาษาไทยให้โดยอัตโนมัติเมื่อรันครั้งแรก
```bat
setup.bat
```
หรือ
```bash
pip install -r requirements.txt
```

## ▶️ การรัน

```bat
run.bat
```

แล้วเปิด browser ที่ **http://localhost:5000**

## 📁 โครงสร้างไฟล์

```
OCRDocument/
├── backend/
│   ├── app.py               # Flask API
│   ├── ocr_engine.py        # PaddleOCR processing
│   ├── spell_checker.py     # ตรวจคำผิด
│   └── dictionary_manager.py # จัดการ dictionary
├── svelte-app/               # Main Frontend (Svelte)
├── data/
│   └── thai_custom_words.txt # คำศัพท์เพิ่มเติม (แก้ไขได้)
├── tests/
│   └── test_system.py        # Unit tests
├── uploads/                  # PDF ที่อัปโหลด
├── requirements.txt
├── setup.bat
└── run.bat
```

## 🔌 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/ocr` | OCR PDF เท่านั้น |
| POST | `/api/spellcheck` | ตรวจคำจาก text |
| POST | `/api/process` | OCR + Spell check รวม |
| GET | `/api/dictionary/stats` | สถิติ dictionary |
| POST | `/api/dictionary/add` | เพิ่มคำใหม่ |

## 📖 แหล่งข้อมูล Dictionary

- **PyThaiNLP** – รวม word list จากราชบัณฑิตยสภา + คลังคำทั่วไป
- **`data/thai_custom_words.txt`** – คำที่เพิ่มเองได้
