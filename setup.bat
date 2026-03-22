@echo off
chcp 65001 > nul
title Thai OCR Spell Check - Setup

echo ================================================
echo  Thai OCR Spell Check System - Setup
echo ================================================
echo.

REM ตรวจสอบ Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] ไม่พบ Python  กรุณาติดตั้งก่อน: https://python.org
    pause
    exit /b 1
)

echo [OK] Python พร้อมใช้งาน
echo.

REM ติดตั้ง dependencies
echo กำลังติดตั้ง Python packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] ติดตั้ง packages ไม่สำเร็จ
    pause
    exit /b 1
)

echo.
echo [OK] ติดตั้ง packages สำเร็จ
echo.

REM ตรวจสอบ Tesseract
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
    echo [OK] พบ Tesseract OCR
) else (
    echo [WARNING] ไม่พบ Tesseract OCR
    echo กรุณาดาวน์โหลดและติดตั้งจาก:
    echo https://github.com/UB-Mannheim/tesseract/wiki
    echo.
    echo สำคัญ: ระหว่างติดตั้งต้องเลือก "Additional language data ^> Thai" ด้วย!
    echo.
)

REM ตรวจสอบ Poppler
if exist "C:\poppler\Library\bin\pdfinfo.exe" (
    echo [OK] พบ Poppler
) else (
    echo [WARNING] ไม่พบ Poppler
    echo กรุณาดาวน์โหลดจาก:
    echo https://github.com/oschwartz10612/poppler-windows/releases
    echo แล้ว Extract ไปที่ C:\poppler\
    echo.
)

echo.
echo ================================================
echo  Setup เสร็จสิ้น!
echo  รัน: run.bat เพื่อเริ่มระบบ
echo ================================================
pause
