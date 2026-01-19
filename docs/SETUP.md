# 🛠️ Setup Guide for Developers

คู่มือสำหรับ Developer ที่ต้องการ Run โปรเจค DO-MOE บนเครื่องตัวเอง

---

## 📋 Prerequisites

| Tool | Version | Download |
|------|---------|----------|
| Node.js | 18+ | https://nodejs.org |
| Python | 3.9+ | https://python.org |
| Git | Latest | https://git-scm.com |

---

## 🚀 Installation Steps

### Step 1: Clone Repository

```bash
git clone https://github.com/YOUR_ORG/moe-one---ict-hub.git
cd moe-one---ict-hub
```

### Step 2: Install Frontend Dependencies

```bash
npm install
```

### Step 3: Install Backend Dependencies

```bash
cd backend
pip3 install flask flask-cors python-dotenv qdrant-client google-generativeai redis requests
```

### Step 4: Create Environment File

```bash
cp .env.example .env
```

แก้ไขไฟล์ `backend/.env` ด้วย **API keys จริง** (ขอจาก Team Lead):

```env
# Required - LLM API
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here

# Required - Vector Database
QDRANT_URL=http://203.159.242.144:6333

# Optional - Redis (fallback to SQLite if not set)
REDIS_URL=redis://localhost:6379/0
```

---

## 🏃 Running the Project

### Terminal 1: Frontend (React + Vite)

```bash
# From project root
npm run dev
```
→ Opens at http://localhost:5173

### Terminal 2: Backend (Flask API)

```bash
cd backend
python3 web_chatbot_v5.py --api --port 5001
```
→ API at http://localhost:5001

---

## ✅ Verify Setup

1. Open http://localhost:5173
2. Login with Google
3. Type "สตูลมีกี่โรงเรียน"
4. Should see response with data

---

## 🔧 Troubleshooting

### Error: GROQ_API_KEY not found
```
⚠️ GROQ_API_KEY not found - Using Gemini only
```
→ ปกติ ถ้าไม่มี Groq key จะ fallback ไป Gemini

### Error: Qdrant connection failed
```
❌ Failed to connect to Qdrant
```
→ ตรวจสอบ QDRANT_URL ว่าถูกต้อง (ใช้ VPN ถ้าอยู่นอก network)

### Error: Module not found
```bash
pip3 install -r requirements.txt
```

---

## 📁 Key Files to Know

| File | Purpose |
|------|---------|
| `App.tsx` | Main React component |
| `backend/web_chatbot_v5.py` | Flask API entry point |
| `backend/chatbot/chatbot_core.py` | Core chatbot logic |
| `services/geminiService.ts` | LLM integration |
| `config/systemPrompts.ts` | AI persona prompts |

---

## 🔐 Important: Never Commit These Files!

- `.env` - Contains API keys
- `sessions.db` - User sessions
- `shared_config.json` - Runtime config

These are in `.gitignore` already.

---

> 💬 มีปัญหา? ติดต่อ Team Lead หรือเปิด Issue บน GitHub
