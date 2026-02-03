# 🌐 DO-MOE Architecture: Hybrid Access (Localhost + LAN)

เอกสารนี้อธิบายว่าทำไมคุณสามารถ **จัดการผ่าน Localhost** แต่คนอื่น **ใช้งานผ่าน Network (LAN)** ได้พร้อมกัน โดยไม่ต้องแก้ค่าไปมา

## 🎯 เป้าหมายของคุณ
> "จัดการในหน้า localhost ... แต่ Network: http://10.20.3.17:3001/ ก็ยังสามารถใช้งานได้"

**คำตอบ:** ✅ **ทำได้แน่นอนครับ 100%** ระบบถูกออกแบบมาเพื่อรองรับสิ่งนี้แล้ว

---

## 🛠 เบื้องหลังการทำงาน (How it works)

### 1. ฝั่งคุณ (Admin / Localhost)
- **URL ที่เข้า:** `http://localhost:3001`
- **Backend:** `http://127.0.0.1:5001`
- **พฤติกรรม:** 
  - เมื่อคุณกด Save Config ระบบจะบันทึก URL ว่า `http://127.0.0.1:5001` ลงฐานข้อมูล (Firebase)
  - นี่คือค่าที่ "ถูกต้อง" สำหรับเครื่องคุณ

### 2. ฝั่งผู้ใช้งาน (User / Mobile / LAN)
- **URL ที่เข้า:** `http://10.20.3.17:3001`
- **Backend:** `http://10.20.3.17:5001`
- **ปัญหาเดิม:** ถ้าระบบดึงค่าจาก Firebase ตรงๆ มันจะได้ `http://127.0.0.1:5001` -> มือถือจะ Error เพราะมันไม่มี Server ในตัวเอง
- **✨ วิธีแก้ใหม่ (Smart Fallback):**
  - **Step 1:** ระบบโหลดค่าจาก Firebase (`http://127.0.0.1:5001`)
  - **Step 2:** โค้ดที่เรารันบนมือถือจะ "เอะใจ" ว่า:
    > *"เอ๊ะ! Config บอกให้ใช้ localhost แต่ฉันกำลังรันอยู่บน IP 10.20.x.x นี่นา... ใช้ localhost ไม่ได้แน่ๆ"*
  - **Step 3 (Override):** ระบบจะ **ทิ้งค่าจาก Firebase** ชั่วคราว และเปลี่ยนไปใช้ **IP ของเครื่องแม่ (10.20.3.17)** โดยอัตโนมัติ

---

## 📊 สรุปตารางการทำงาน

| อุปกรณ์ | เข้าผ่าน URL | ค่าใน Firebase (ที่ Admin Save) | ค่าที่ระบบ **แอบเปลี่ยนให้จริง** (Smart Override) | ผลลัพธ์ |
| :--- | :--- | :--- | :--- | :--- |
| **เครื่องคุณ (Admin)** | `localhost` | `127.0.0.1` | `127.0.0.1` (เดิม) | ✅ ใช้งานได้ปกติ |
| **มือถือ / เครื่องอื่น** | `10.20.3.17` | `127.0.0.1` | **`10.20.3.17` (Auto)** | ✅ ใช้งานได้ปกติ (ไม่ Error) |

## ✅ ข้อดี
1. **ไม่ต้องแก้ Config ไปมา:** คุณ Save ผ่าน Localhost ได้เลย ไม่ต้องคอยเปลี่ยน IP เป็น 10.20... ก่อน Save
2. **Key ไม่หาย:** ระบบ Save แบบ Atomic Update ทำให้ Key ปลอดภัย แม้จะมีการสลับโหมด
3. **รองรับ Dynamic IP:** ถ้าพรุ่งนี้ IP เครื่องคุณเปลี่ยนเป็น `10.20.5.99` ระบบบนมือถือก็จะรู้เองตาม URL ที่เข้าใช้งาน

---

# 🚀 Pre-Deployment Checklist (สิ่งที่ต้องทำก่อน Deploy จริง)

เมื่อคุณพร้อมที่จะนำระบบนี้ขึ้น Production (ใช้งานจริงสำหรับบุคคลทั่วไป) ขอให้ตรวจสอบรายการต่อไปนี้เพื่อความปลอดภัยและประสิทธิภาพสูงสุดครับ

## 1. 🔒 Security: แก้ไข Firestore Rules (สำคัญที่สุด)
ตอนนี้เราเปิด `allow write: if true;` ไว้เพื่อการทดสอบ (ใครก็แก้ข้อมูลได้) ต้องปิดกลับเป็น:

```javascript
match /settings/{document=**} {
  allow read: if true;
  allow write: if request.auth != null && request.auth.token.role == 'admin'; // หรือเงื่อนไขที่ปลอดภัย
}
```
> **เหตุผล:** ป้องกันไม่ให้คนนอกมาแอบแก้ API Key หรือเปลี่ยน URL ของ Backend

## 2. 🛡️ HTTPS Configuration
- ถ้า Web Frontend ของคุณใช้ **HTTPS** (เช่น `https://chat.moe.go.th`)
- ตัว Backend Flask **ต้องเป็น HTTPS ด้วย** (เช่น `https://api.moe.go.th`)
- **ระวัง:** ห้ามใช้ `https://` (หน้าเว็บ) คู่กับ `http://` (backend) เพราะ Browser จะบล็อก (Mixed Content Error)

## 3. ⚙️ Environment Variables (.env)
ตรวจสอบไฟล์ `.env` บนเครื่อง Server จริง:
- `DEBUG=False` (ปิดโหมด Debug เพื่อความเร็วและความปลอดภัย)
- `GROQ_API_KEY`, `GEMINI_API_KEY` (ใส่ Key จริงสำหรับ Production)

## 4. 📦 Build for Production
บนเครื่อง Server จริง ห้ามรันด้วย `npm run dev` ให้ใช้คำสั่ง:
```bash
# 1. สร้าง Production Build
npm run build

# 2. เริ่มต้น Server
npm start
```
> **เหตุผล:** `npm run dev` ช้ากว่าและกินทรัพยากรมากกว่ามาก ไม่เหมาะกับการรองรับคนจำนวนเยอะๆ

## 5. 🐍 Production WSGI (Python Backend)
แทนที่จะรัน `python web_chatbot_v5.py` ตรงๆ ควรใช้ Gunicorn เพื่อรองรับ Load เยอะๆ:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 web_chatbot_v5:app
```
*(ถ้ามีคนใช้เยอะจริงๆ แนะนำให้ทำข้อนี้ครับ)*
