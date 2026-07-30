-- ============================================================
-- Authentication Database Schema (spectra_auth_db)
-- ============================================================

-- 1. ตารางเก็บข้อมูลผู้ใช้งาน (Users)
CREATE TABLE users (
    id SERIAL PRIMARY KEY,                        -- รหัสผู้ใช้งาน (Auto Increment)
    username VARCHAR(50) UNIQUE NOT NULL,         -- ชื่อผู้ใช้งาน (ต้องไม่ซ้ำกัน)
    password_hash VARCHAR(64) NOT NULL,           -- รหัสผ่านที่ถูกเข้ารหัสด้วย SHA-256
    role VARCHAR(20) DEFAULT 'user',              -- สิทธิ์การใช้งาน เช่น 'admin', 'user'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- วันที่สมัคร
);

-- 2. สร้าง Index เพื่อให้ค้นหาผู้ใช้งานตอน Login ได้อย่างรวดเร็ว
CREATE UNIQUE INDEX ix_users_username ON users(username);
CREATE INDEX ix_users_id ON users(id);

-- ============================================================
-- ตัวอย่างการ Insert ข้อมูลเบื้องต้น (Seed Data)
-- หมายเหตุ: รหัสผ่าน 'admin123' เมื่อผ่าน SHA-256 จะได้ค่าด้านล่าง
-- ============================================================
INSERT INTO users (username, password_hash, role) 
VALUES (
    'admin', 
    '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 
    'admin'
) ON CONFLICT (username) DO NOTHING;
