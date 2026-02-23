# DO-MOE AI Chatbot 🤖

> ระบบ AI Chatbot สำหรับข้อมูลการศึกษาไทย พัฒนาโดย กระทรวงศึกษาธิการ

![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=nextdotjs)
![Flask](https://img.shields.io/badge/Flask-3.x-blue?logo=flask)
![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-red)
![Redis](https://img.shields.io/badge/Redis-7-red?logo=redis)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker)

---

## ✨ Features

- 🧠 **Multi-LLM AI** — Groq (llama-3.3-70b) + Gemini (gemini-2.0-flash) พร้อม auto-failover
- 💎 **Apple 2025 Glass UI** — หน้า UI สวยงาม พรีเมียม พร้อม Suggestion Chips ใสลอยตัว
- 🔍 **RAG Pipeline & Metadata Filtering** — ค้นหาข้อมูลจาก Qdrant Vector Database 2.6 ล้าน records ได้อย่างแม่นยำ
- 📊 **Chart Generation** — สร้างกราฟเปรียบเทียบข้อมูลอัตโนมัติ (Bar, Line, Pie)
- 💬 **Advanced Context-Aware** — จำบริบทจังหวัด/ปี และสลับหมวดหมู่คำถามอัตโนมัติ (ผ่าน 10-Question Benchmark 10/10)
- ⚡ **Local LAN Ready** — Nginx reverse proxy ให้รันบน LAN ได้ทันที
- 🏫 **School Search** — ค้นหาโรงเรียนรายชื่อ + ข้อมูลละเอียด
- 🔑 **Multi-Key Rotation & Firestore Sync** — ดึง API Keys จาก Admin Panel มาใช้แบบ Real-time
- 🛡️ **Admin Panel** — จัดการ API keys, ตรวจสอบ Audit Log, Monitor Session การใช้งาน
- 🐳 **Docker Ready** — Deploy ด้วย Docker Compose คำสั่งเดียว

---

## 📋 Prerequisites

| ซอฟต์แวร์ | เวอร์ชัน | หมายเหตุ |
|-----------|---------|----------|
| Node.js | >= 18.x | Frontend |
| Python | >= 3.9 | Backend |
| Docker | >= 24.x | Production deployment |
| Qdrant | >= 1.7 | Vector database (running on server) |
| Redis | >= 7.x | Optional — session management & cache |

---

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

> Frontend จะรันที่: http://localhost:3000

### 3. Backend Setup

```bash
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Run Flask API
python3 web_chatbot_v5.py --api --port 5001
```

> Backend จะรันที่: http://localhost:5001

### 4. Docker (Production)

```bash
# ตั้งค่า environment
cp deploy/.env.backend.example deploy/.env.backend
cp deploy/.env.frontend.example deploy/.env.frontend
# แก้ไขค่า API keys ใน .env files

# Build & Run
docker compose -f docker-compose.prod.yml up -d --build
```

> 📄 ดูคู่มือ deploy ละเอียด: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 🔑 API Keys Configuration

### วิธีที่ 1: ผ่าน Admin Panel (แนะนำ)

1. เปิด Frontend และ Login ด้วย Admin account
2. ไปที่ **Admin Panel > API Settings**
3. เพิ่ม API Keys:
   - **Groq API Keys** (Primary) — รองรับหลาย keys สำหรับ rotation
   - **Gemini API Keys** (Fallback)
4. กด **บันทึก**

### วิธีที่ 2: ผ่าน Environment Variables

สร้างไฟล์ `.env` ใน `backend/`:

```env
GROQ_API_KEY=gsk_xxx...
GEMINI_API_KEY=AIzaSy...
QDRANT_URL=http://your-qdrant-server:6333
REDIS_URL=redis://localhost:6379/0
```

---

## 📁 Project Structure

```
do-moe-chatbot/
├── backend/
│   ├── chatbot/
│   │   ├── agent/                   # LLM Agent definitions (llm_agent.py, tools.py)
│   │   ├── core/                    # Core logic (chatbot_core.py, memory.py, context.py)
│   │   ├── data/                    # Data sources (thai_provinces.py, location data)
│   │   ├── executors/               # Tool Executors (school_tools.py, normalizers.py)
│   │   ├── handlers/                # Request Handlers (search, proxy, stats, intercept)
│   │   ├── search/                  # Qdrant Search Engine & Extractors
│   │   └── utils/                   # Helpers (formatters.py)
│   ├── configs/                     # Application & Vector DB configurations
│   ├── routes/                      # Flask API endpoints (admin, metrics, chat)
│   ├── run_10q_test.py              # Automated 10-Question benchmark script
│   └── web_chatbot_v5.py            # Flask API entry point
├── src/
│   ├── components/
│   │   ├── admin/                   # Admin Panel components
│   │   ├── chat/                    # Chat UI (ChatView, MessageBubble, ChatInput)
│   │   ├── layout/                  # Sidebar & Mobile Menu
│   │   └── pages/                   # LandingPage & LoginPage
│   ├── contexts/                    # React Contexts (Auth, AdminConfig)
│   ├── hooks/                       # Custom React Hooks (useChatManager, useSpeechSynthesis)
│   ├── services/                    # Firebase, API, and Core Services
│   ├── types/                       # TypeScript definitions
│   └── utils/                       # Frontend helpers
├── deploy/
│   ├── docker/                      # Dockerfiles for frontend/backend
│   └── nginx/                       # Nginx reverse proxy configuration
├── docs/
│   └── DEPLOYMENT.md                # Deployment manual (Thai)
├── scripts/                         # Utility scripts (Docker management)
│   ├── start.sh / stop.sh           # Service management
│   └── flush_cache.sh               # Cache management
├── docker-compose.prod.yml          # Production Docker Compose
└── README.md                        # เอกสารนี้
```

---

## 🔧 Configuration

### Qdrant Collections

| Collection | Description | Records |
|-----------|-------------|---------|
| `edu_schools_v5` | โรงเรียน (สังกัด, ที่ตั้ง, จำนวน) | 55,629 |
| `edu_teachers_v5` | ครู (แยกเพศ, จังหวัด) | 120,542 |
| `edu_students_v5` | นักเรียน (แยกเพศ, ชั้น, จังหวัด) | 638,661 |
| `edu_ratios_v5` | อัตราส่วนนักเรียนต่อครู | 56,148 |
| `edu_grade_summary_v5` | สรุปตามชั้นเรียน | 125,967 |
| `edu_gender_overview_v5` | ภาพรวมแยกเพศ | 16,795 |
| `edu_systems_v5` | สังกัดหน่วยงาน | 10,410 |
| `edu_areas_*` | พื้นที่การศึกษา | 415 |

> รองรับข้อมูล **3 ปีการศึกษา**: 2565, 2566, 2567

### LLM Models

| ลำดับ | Provider | Model | หมายเหตุ |
|-------|----------|-------|----------|
| Primary | Groq | `llama-3.3-70b-versatile` | เร็ว, ฟรี |
| Fallback | Gemini | `gemini-2.0-flash` | Stable, Google |

---

## 📝 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/chat` | ส่งข้อความ chat (synchronous) |
| `POST` | `/api/chat/stream` | ส่งข้อความ chat (streaming) |
| `POST` | `/api/sync-config` | Sync config จาก Admin Panel |
| `POST` | `/api/cache/flush` | ล้าง semantic cache |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/sessions/count` | จำนวน active sessions |

---

## 🛡️ Admin Panel

| Feature | Description |
|---------|-------------|
| **Model Config** | เปลี่ยน LLM model, temperature, max tokens |
| **API Keys** | จัดการ Groq/Gemini keys (เพิ่ม/ลบ/rotation) |
| **RAG Config** | ตั้งค่า retrieval parameters |
| **UX Policy** | ปรับ persona, tone, response style |

---

## 🐳 Production Deployment

ดูคู่มือ deploy ฉบับเต็ม: **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**

สรุปสั้น:

```bash
# 1. Clone & Config
git clone <repo> && cd do-moe-chatbot
cp deploy/.env.backend.example deploy/.env.backend   # แก้ไข API keys
cp deploy/.env.frontend.example deploy/.env.frontend  # แก้ไข URLs

# 2. Firebase key
cp /path/to/serviceAccountKey.json backend/

# 3. Deploy!
docker compose -f docker-compose.prod.yml up -d --build

# 4. เปิดเบราว์เซอร์ → http://<server-ip>:3001 ✅
```

### System Architecture

```
┌──────────┐    ┌──────────────┐    ┌──────────┐
│ Frontend │───▸│   Backend    │───▸│  Redis   │
│ (Nginx)  │    │ (Gunicorn)   │    │ (Cache)  │
│  :3001   │    │   :5001      │    │  :6379   │
└──────────┘    └──────┬───────┘    └──────────┘
                       │
                  ┌────▼─────┐    ┌─────────────┐
                  │  Qdrant  │    │ Groq/Gemini │
                  │  :6333   │    │   (LLM API) │
                  └──────────┘    └─────────────┘
```

---

## 🔐 Firebase Setup (Optional)

สำหรับ Admin Panel config sync:

1. สร้าง Firebase project
2. เปิด Firestore Database
3. เพิ่ม Service Account key ใน `backend/serviceAccountKey.json`
4. Config จะ sync อัตโนมัติระหว่าง Admin Panel ↔ Backend

---

## 📄 License

MIT License © 2026 กระทรวงศึกษาธิการ
