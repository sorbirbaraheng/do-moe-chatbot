# 🎓 DO-MOE Education Chatbot

**AI-powered Education Data Assistant for Thailand's Ministry of Education**

![Version](https://img.shields.io/badge/version-5.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue)
![Python](https://img.shields.io/badge/Python-3.9+-yellow)

---

## 📋 Overview

DO-MOE เป็นระบบ AI Chatbot สำหรับการสืบค้นข้อมูลการศึกษาของประเทศไทย พัฒนาสำหรับกระทรวงศึกษาธิการ รองรับการค้นหาข้อมูลโรงเรียน สถิตินักเรียน และคำถามทั่วไปเกี่ยวกับการศึกษา

### ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🗣️ **Multi-Category Chat** | รองรับ 3 หมวด: ทั่วไป, โรงเรียน, นักเรียน |
| 🤖 **Multi-LLM Support** | Groq (primary) + Gemini (fallback) |
| 🔍 **Vector Search** | Qdrant สำหรับ semantic search |
| ⚡ **Real-time Streaming** | แสดงคำตอบแบบ character-by-character |
| 📊 **Interactive Charts** | แสดงกราฟและแผนที่ |
| 👍👎 **Feedback System** | เก็บ feedback สำหรับ improve AI |
| 🔐 **Authentication** | Firebase Auth (Google Sign-in) |

---

## 🏗️ Project Structure

```
moe-one---ict-hub/
├── 📂 backend/                 # Python Flask API
│   ├── chatbot/               # Core chatbot logic
│   │   ├── chatbot_core.py    # Main chatbot class
│   │   ├── query_parser.py    # Intent extraction
│   │   ├── search_engine.py   # Qdrant queries
│   │   └── memory.py          # Conversation memory
│   ├── web_chatbot_v5.py      # Flask API entry point
│   ├── redis_session.py       # Redis session storage
│   └── .env.example           # Environment template
│
├── 📂 components/              # React UI components
│   ├── MessageBubble.tsx      # Chat message display
│   ├── ChatInput.tsx          # Input with voice/file
│   ├── ChartWidget.tsx        # Chart rendering
│   └── admin/                 # Admin panel
│
├── 📂 services/                # Frontend services
│   ├── geminiService.ts       # LLM API integration
│   ├── feedbackService.ts     # Feedback to Firebase
│   └── firebase.ts            # Firebase config
│
├── 📂 config/                  # App configuration
│   ├── defaultConfig.ts       # Default settings
│   └── systemPrompts.ts       # AI persona prompts
│
├── App.tsx                    # Main React app
├── index.html                 # Entry HTML
└── package.json               # Dependencies
```

---

## 🚀 Quick Start

### Prerequisites

- Node.js 18+
- Python 3.9+
- Redis (optional, has SQLite fallback)

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/moe-one---ict-hub.git
cd moe-one---ict-hub

# Frontend
npm install

# Backend
cd backend
pip install -r requirements.txt  # or use pip3
```

### 2. Environment Setup

```bash
# Copy example files
cp backend/.env.example backend/.env

# Edit with your API keys
nano backend/.env
```

**Required variables:**
```env
GEMINI_API_KEY=your_gemini_key
QDRANT_URL=http://your-qdrant-server:6333
GROQ_API_KEY=your_groq_key  # Optional but recommended
REDIS_URL=redis://localhost:6379/0  # Optional
```

### 3. Run Development

```bash
# Terminal 1: Frontend
npm run dev

# Terminal 2: Backend
cd backend
python3 web_chatbot_v5.py --api --port 5001
```

Open http://localhost:5173

---

## 🔧 Tech Stack

### Frontend
- **React 18** + TypeScript
- **Vite** - Build tool
- **Firebase** - Auth & Firestore

### Backend  
- **Flask** - REST API
- **Qdrant** - Vector database
- **Redis** - Session storage
- **Groq/Gemini** - LLM providers

---

## 📖 Documentation

- [📘 Setup Guide](./docs/SETUP.md) - Detailed setup instructions
- [📘 API Reference](./docs/API.md) - Backend API endpoints
- [📘 Architecture](./docs/ARCHITECTURE.md) - System design

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file

---

## 👥 Team

Developed by **ICT Hub, Ministry of Education Thailand**

---

> 💡 **Note:** ไฟล์ `.env` ไม่ได้ถูก commit ผู้ใช้ใหม่ต้องสร้างเองจาก `.env.example`
