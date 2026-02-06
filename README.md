# DO-MOE AI Chatbot 🤖

ระบบ AI Chatbot สำหรับข้อมูลการศึกษาไทย พัฒนาโดย กระทรวงศึกษาธิการ

## 📋 Prerequisites

- **Node.js** >= 18.x
- **Python** >= 3.9
- **Qdrant** Vector Database (running on server)
- **Redis** (optional, for session management)

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/sorbirbaraheng/do-moe-chatbot.git
cd do-moe-chatbot
```

### 2. Frontend Setup

```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend จะรันที่: `http://localhost:3000`

### 3. Backend Setup

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Run Flask API
python3 web_chatbot_v5.py --api --port 5001
```

Backend จะรันที่: `http://localhost:5001`

## 🔑 API Keys Configuration

### วิธีที่ 1: ผ่าน Admin Panel (แนะนำ)

1. เปิด Frontend และ Login ด้วย Admin account
2. ไปที่ **Admin Panel** > **API Settings**
3. เพิ่ม API Keys:
   - **Groq API Keys** (Primary) - หลาย keys สำหรับ rotation
   - **Gemini API Keys** (Fallback)
4. กด **บันทึก**

### วิธีที่ 2: ผ่าน Environment Variables

สร้างไฟล์ `.env` ใน `backend/`:

```env
GROQ_API_KEY=gsk_xxx...
GEMINI_API_KEY=AIzaSy...
QDRANT_URL=http://your-qdrant-server:6333
REDIS_URL=redis://...
```

## 📁 Project Structure

```
├── backend/
│   ├── chatbot/
│   │   ├── chatbot_core.py      # Main chatbot class
│   │   ├── llm.py               # Multi-provider LLM (Groq/Gemini)
│   │   ├── llm_agent.py         # LLM Agent with function calling
│   │   ├── tools.py             # Tool definitions
│   │   ├── tool_executor.py     # Tool executor for Qdrant
│   │   └── handlers/            # Mixin handlers
│   ├── firebase_config.py       # Firebase/Firestore config
│   └── web_chatbot_v5.py        # Flask API entry point
├── tests/                       # Verification & Regression Tests
│   ├── regression/              # Automated verification scripts
│   └── repro/                   # Bug reproduction scripts
├── scripts/                     # Utility scripts
│   └── perf/                    # Performance benchmarks
├── services/
│   └── geminiService.ts         # Frontend AI service
├── components/
│   └── admin/                   # Admin Panel components
└── contexts/
    └── AdminConfigContext.tsx   # Config management
```

## 🔧 Configuration

### Qdrant Collections (V5)

| Collection | Description |
|------------|-------------|
| `edu_schools_v5` | โรงเรียน |
| `edu_teachers_v5` | ครู |
| `edu_students_v5` | นักเรียน |
| `edu_ratios_v5` | อัตราส่วน |
| `edu_areas_v5` | พื้นที่การศึกษา |

### LLM Models

- **Primary:** Groq `llama-3.3-70b-versatile`
- **Fallback:** Gemini `gemini-2.0-flash`

## 🛠️ Development

### Run Frontend (Dev)
```bash
npm run dev
```

### Run Backend (Dev)
```bash
cd backend
python3 web_chatbot_v5.py --api --port 5001
```

### Build for Production
```bash
npm run build
```

## 📝 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/stream` | Send chat message (streaming) |
| POST | `/api/sync-config` | Sync config from Admin Panel |
| GET | `/api/health` | Health check |

## 🔐 Firebase Setup (Optional)

สำหรับ Admin Panel sync:

1. สร้าง Firebase project
2. เปิด Firestore
3. เพิ่ม Service Account key ใน `backend/`
4. Config จะ sync อัตโนมัติ

## 📞 Support

- GitHub Issues: https://github.com/sorbirbaraheng/do-moe-chatbot/issues
