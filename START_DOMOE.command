#!/bin/bash
# ==============================================================================
# 📄 ชื่อไฟล์: START_DOMOE.command
# 📝 คำอธิบาย:
#    สคริปต์สำหรับเริ่มต้นระบบจง (Launcher Script)
#    ทำหน้าที่รันทั้งส่วน Frontend และ Backend พร้อมกันในคลิกเดียว
#
# 🛠 หน้าที่หลัก:
#    1. ปิด Process เก่าที่อาจค้างอยู่ (Kill existing processes)
#    2. รัน Flask Backend (Python) ที่พอร์ต 5001
#    3. รัน Vite Frontend (React) ที่พอร์ต 3001
#    4. แสดง URL สำหรับเข้าใช้งาน
# ==============================================================================

# DO-MOE: Start All Services (Flask + Vite)
# Double-click this file to start everything!

cd "$(dirname "$0")"

echo "🚀 Starting DO-MOE Services..."
echo ""

# 1. Kill existing processes
echo "🧹 Cleaning up old processes..."
pkill -f "web_chatbot_v5.py" 2>/dev/null
lsof -i :3001 -t | xargs kill -9 2>/dev/null
sleep 1

# 2. Start Flask Backend
echo "🐍 Starting Flask Backend..."
cd backend
nohup python3 web_chatbot_v5.py --api --host 0.0.0.0 --port 5001 > flask_server.log 2>&1 &
FLASK_PID=$!
cd ..

# Wait for Flask to start
sleep 3

# 3. Start Frontend (Vite)
echo "⚡ Starting Frontend (Vite)..."
npm run dev &
VITE_PID=$!

echo ""
echo "✅ All services started!"
echo ""
echo "📍 Access URLs:"
echo "   Frontend: http://localhost:3001"
echo "   Backend:  http://localhost:5001"
echo ""
echo "   Network:  http://$(ipconfig getifaddr en0 2>/dev/null || echo 'N/A'):3001"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for user interrupt
wait $VITE_PID
