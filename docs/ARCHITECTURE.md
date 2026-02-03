# 🏗️ MOE-One Architecture

## Overview

MOE-One เป็น AI Chatbot สำหรับค้นหาข้อมูลการศึกษาของประเทศไทย ประกอบด้วย:
- **Frontend**: React + Vite (TypeScript)
- **Backend**: Flask + Python
- **Database**: Qdrant Vector Database
- **Auth/Config**: Firebase Firestore

---

## Directory Structure

```
moe-one---ict-hub/
├── 📱 Frontend (React/Vite)
│   ├── App.tsx             # Main application entry
│   ├── components/         # UI Components
│   │   ├── admin/          # Admin panel components
│   │   ├── chat/           # Chat interface components
│   │   └── common/         # Shared components
│   ├── contexts/           # React Context providers
│   ├── services/           # API client services
│   ├── config/             # Frontend configuration
│   └── types/              # TypeScript type definitions
│
├── 🐍 Backend (Flask/Python)
│   └── backend/
│       ├── chatbot/        # Core chatbot logic
│       │   ├── chatbot_core.py   # Main chatbot engine
│       │   ├── llm_agent.py      # LLM orchestration
│       │   ├── tool_executor.py  # Tool execution (search, etc.)
│       │   ├── tools.py          # Tool definitions
│       │   └── query_parser.py   # Query parsing & NLU
│       ├── rag/            # RAG (Retrieval-Augmented Generation)
│       └── web_chatbot_v5.py     # Flask API server
│
├── 📚 docs/                # Documentation
├── 🧪 tests/               # Test files
├── 📦 archive/             # Archived debug scripts
└── 🔧 Config Files
    ├── package.json        # NPM dependencies
    ├── requirements.txt    # Python dependencies
    └── vite.config.ts      # Vite configuration
```

---

## Key Files

| File | Purpose |
|------|---------|
| `web_chatbot_v5.py` | Flask API entry point |
| `chatbot/chatbot_core.py` | Main chatbot logic |
| `chatbot/tool_executor.py` | Database query execution |
| `chatbot/llm_agent.py` | LLM orchestration |
| `services/geminiService.ts` | Gemini/Groq API client |
| `contexts/AdminConfigContext.tsx` | Config management |

---

## Data Flow

```
User Message → Frontend (React)
     ↓
Flask API (/api/chat)
     ↓
LLM Agent (tool selection)
     ↓
Tool Executor (Qdrant queries)
     ↓
Response Formatting
     ↓
Stream back to Frontend
```

---

## Configuration

- **API Keys**: Stored in Firebase Firestore (`settings/main-config`)
- **Prompts**: Configurable via Admin Panel → Prompt Management
- **Model**: Groq (primary) + Gemini (backup)

---

## Running Locally

```bash
# Frontend
npm install
npm run dev

# Backend
cd backend
pip install -r requirements.txt
python web_chatbot_v5.py
```

---

## Environment Variables

### Frontend (.env.local)
```
VITE_FIREBASE_API_KEY=...
```

### Backend (backend/.env)
```
GEMINI_API_KEY=...
QDRANT_HOST=...
QDRANT_PORT=...
```
