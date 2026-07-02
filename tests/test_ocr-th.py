import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def create_test_pdf(filename, font_path):
    # 1. ลงทะเบียนฟอนต์ภาษาไทย
    if not os.path.exists(font_path):
        print(f"❌ ไม่พบไฟล์ฟอนต์ที่: {font_path} กรุณาตรวจสอบตำแหน่งไฟล์")
        return
    
    pdfmetrics.registerFont(TTFont('ThaiFont', font_path))
    
    # 2. สร้างหน้า PDF
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # 3. กำหนดเนื้อหาทดสอบ (จงใจพิมพ์ผิดในบางจุดเพื่อเทสระบบตรวจคำผิด)
    title = "เอกสารทดสอบระบบ OCR และตรวจจับคำผิดภาษาไทย (Test Document)"
    
    test_sentences = [
        "1. บริษ้ท จำกัด ได้ทำก่ารจัดส่งเอกสารเรียบรอยแล้ว (คำผิด: บริษ้ท, ทำก่าร, เรียบรอย)",
        "2. ใบเสร้จรับเงินฉบับนี้ยังไม่ไค้ชำระเงินตามระบบ (คำผิด: ใบเสร้จ, ไม่ไค้)",
        "3. กรุณาติตต่อเจ้าหน้าที่ เพื่ิอขอรับข้อมูลเพื่มเติม (คำผิด: ติตต่อ, เพื่ิอ, เพื่มเติม)",
        "4. สระลอยเวอร์ชันประหลาด: สว้นใหญ่คนมักจะพิมพืผิดเวลารีบเร่ง (คำผิด: สว้นใหญ่, พิมพื)",
        "5. รายงานผลการดำเนินงานประจำเปีงบประมาณสองพันยี่สิบหก (คำผิด: เปีงบประมาณ)",
        "6. วรรณยุกต์จม/สลับที่: ขน้ึ แท่นระบบอตั โนมตั ิเพ่ือใชง้านจรงิ (คำผิด: ขน้ึ, อตัโนมตัิ, เพ่ือใชง้านจรงิ)",
        "7. ตัวอย่างคำพ้องเสียงที่มักใช้ผิดในเอกสารกฎหมาย: โจทก์ยื่นฟ้องจำเลยในคดีคนไข้เป็นโจทก์เลข (จงใจใช้คำว่า โจทก์เลข แทน โจทย์เลข)"
    ]
    
    # 4. เขียนเนื้อหาลง PDF
    # เขียนหัวข้อ
    c.setFont('ThaiFont', 18)
    c.drawString(50, height - 80, title)
    
    c.setLineWidth(1)
    c.line(50, height - 95, width - 50, height - 95)
    
    # เขียนประโยคทดสอบ
    c.setFont('ThaiFont', 14)
    y_position = height - 130
    
    for sentence in test_sentences:
        c.drawString(50, y_position, sentence)
        y_position -= 35  # ขยับบรรทัดลงมา
        
    # 5. บันทึกไฟล์
    c.save()
    print(f"✨ สร้างไฟล์ PDF ทดสอบสำเร็จ: {filename}")

# เรียกใช้งาน (กรุณาเปลี่ยนชื่อไฟล์ฟอนต์ให้ตรงกับที่คุณมีในเครื่อง)
create_test_pdf("ocr_test_thai.pdf", "D:/OCR-Github/OCR-Document/fonts/THSarabun.ttf")