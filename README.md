# 📄 Thai OCR Spell Check System

ระบบ OCR สำหรับสแกนเอกสาร PDF และตรวจสอบคำถูกคำผิดภาษาไทย โดยใช้ชุดคำศัพท์จากพจนานุกรมราชบัณฑิตยสภา (ผ่าน PyThaiNLP)

## ✨ คุณสมบัติ

- 📤 **อัปโหลด PDF** แบบ Drag & Drop
- 🔍 **OCR ภาษาไทย + อังกฤษ** ด้วย Tesseract + preprocessing
- ✅ **ตรวจคำผิด** โดยเทียบกับพจนานุกรมราชบัณฑิตยสภา
- 🔴 **ไฮไลท์คำผิด** พร้อมคำแนะนำ
- 📚 **เพิ่มคำ Custom** ได้เองผ่าน UI หรือแก้ไขไฟล์
- 📥 **Export** เป็น .txt หรือรายงาน

## 📋 Requirements

| Software | Version | Download |
|----------|---------|----------|
| Python | 3.9+ | [python.org](https://python.org) |
| Tesseract OCR | 5.x | [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) |
| Poppler | latest | [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases) |

> **สำคัญ**: ตอนติดตั้ง Tesseract ให้เลือก "Additional language data → Thai" ด้วย

## 🚀 การติดตั้ง

### 1. ติดตั้ง Tesseract OCR
- ดาวน์โหลดและติดตั้งจาก [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
- ระหว่างติดตั้ง เลือก **Thai** ในหัวข้อ "Additional language data"

### 2. ติดตั้ง Poppler
- ดาวน์โหลดจาก [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)
- Extract ไปที่ `C:\poppler\`

### 3. ติดตั้ง Python dependencies
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
│   ├── ocr_engine.py        # OCR processing
│   ├── spell_checker.py     # ตรวจคำผิด
│   └── dictionary_manager.py # จัดการ dictionary
├── frontend/
│   ├── index.html           # Web UI
│   ├── style.css            # Styles
│   └── script.js            # JavaScript
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
