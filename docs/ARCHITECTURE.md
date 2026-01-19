# 🏗️ DO-MOE Architecture Guide

## สำหรับโปรแกรมเมอร์ที่ต้องการเข้าใจระบบ

---

## 📊 System Overview (ภาพรวม)

```
┌─────────────────────────────────────────────────────────────────┐
│                         User (Browser)                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                       │
│                      localhost:5173                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  App.tsx    │  │ MessageBubble│ │  geminiService.ts       │  │
│  │  (หน้าหลัก) │  │ (แสดงข้อความ)│ │  (เรียก LLM APIs)       │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼ HTTP REST API
┌─────────────────────────────────────────────────────────────────┐
│                    Backend (Flask API)                           │
│                      localhost:5001                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ web_chatbot │  │ chatbot_core│  │     search_engine       │  │
│  │ _v5.py      │  │ .py         │  │     .py                 │  │
│  │ (Entry)     │  │ (หลักตอบคำถาม)│ │  (ค้นหา Qdrant)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
│     Qdrant        │ │     Redis         │ │   Groq/Gemini     │
│  (Vector DB)      │ │  (Sessions)       │ │   (LLM APIs)      │
│  ข้อมูลโรงเรียน    │ │  เก็บความจำ        │ │   สร้างคำตอบ       │
└───────────────────┘ └───────────────────┘ └───────────────────┘
```

---

## 🔄 Flow การทำงาน (เมื่อ User ถามคำถาม)

### ขั้นตอน 1: User พิมพ์คำถาม
```
User: "สตูลมีกี่โรงเรียน"
```

### ขั้นตอน 2: Frontend ส่งไป Backend
```javascript
// services/geminiService.ts
fetch('http://localhost:5001/chat', {
  method: 'POST',
  body: JSON.stringify({
    message: "สตูลมีกี่โรงเรียน",
    category: "school",
    session_id: "abc123"
  })
})
```

### ขั้นตอน 3: Backend วิเคราะห์คำถาม
```python
# backend/chatbot/query_parser.py
parsed = {
    "province": "สตูล",
    "query_type": "count",
    "entity": "school"
}
```

### ขั้นตอน 4: ค้นหาข้อมูลจาก Qdrant
```python
# backend/chatbot/search_engine.py
results = qdrant_client.query_points(
    collection="education_statistics_province",
    query_vector=embed("สตูล"),
    limit=5
)
# ได้ข้อมูล: {"province": "สตูล", "school_count": 348, ...}
```

### ขั้นตอน 5: สร้างคำตอบด้วย LLM
```python
# ใช้ Groq (เร็ว) หรือ Gemini (fallback)
prompt = f"""
ข้อมูลที่ค้นพบ: {results}
คำถาม: สตูลมีกี่โรงเรียน
ตอบเป็นภาษาไทย สุภาพ เข้าใจง่าย
"""
answer = groq.chat(prompt)
```

### ขั้นตอน 6: ส่งคำตอบกลับ
```json
{
  "response": "จังหวัดสตูลมีโรงเรียนทั้งหมด 348 แห่งครับ 🏫"
}
```

---

## 📁 โครงสร้างไฟล์สำคัญ

### Frontend (React)
| ไฟล์ | หน้าที่ |
|------|--------|
| `App.tsx` | Component หลัก จัดการ state, routing |
| `components/MessageBubble.tsx` | แสดงข้อความ chat (markdown, chart) |
| `components/ChatInput.tsx` | ช่องพิมพ์ข้อความ |
| `services/geminiService.ts` | เรียก Backend API + fallback logic |
| `services/firebase.ts` | Authentication (Google Login) |
| `config/systemPrompts.ts` | Prompt templates สำหรับ AI |

### Backend (Python Flask)
| ไฟล์ | หน้าที่ |
|------|--------|
| `web_chatbot_v5.py` | Entry point, Flask API routes |
| `chatbot/chatbot_core.py` | Logic หลักในการตอบคำถาม |
| `chatbot/search_engine.py` | Query Qdrant vector database |
| `chatbot/query_parser.py` | วิเคราะห์คำถาม (NLP) |
| `chatbot/memory.py` | จัดการ conversation memory |
| `redis_session.py` | เก็บ session ใน Redis |

---

## 🗄️ Data Flow

```
                    ┌──────────────────────────┐
                    │       Qdrant             │
                    │  (Vector Database)       │
                    │                          │
                    │  Collections:            │
                    │  • education_statistics  │
                    │    _province             │
                    │  • education_statistics  │
                    │    _district             │
                    │  • education_schools     │
                    └──────────────────────────┘
                              ▲
                              │ Semantic Search
                              │
┌──────────────┐    ┌──────────────────────────┐
│   User       │───▶│    Flask Backend         │
│   Question   │    │                          │
└──────────────┘    │  1. Parse question       │
                    │  2. Search Qdrant        │
                    │  3. Call LLM (Groq)      │
                    │  4. Format response      │
                    └──────────────────────────┘
                              │
                              ▼
                    ┌──────────────────────────┐
                    │       Redis              │
                    │   (Session Storage)      │
                    │                          │
                    │  • User memory           │
                    │  • Chat history          │
                    │  • Response cache        │
                    └──────────────────────────┘
```

---

## 🔑 API Keys ที่ใช้

| Key | ใช้ทำอะไร | ที่มา |
|-----|----------|-------|
| `GEMINI_API_KEY` | LLM หลัก/สำรอง | Google AI Studio |
| `GROQ_API_KEY` | LLM เร็ว (primary) | console.groq.com |
| `QDRANT_URL` | Vector Database | Self-hosted server |
| `REDIS_URL` | Session storage | Redis Cloud |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, TypeScript, Vite |
| Styling | TailwindCSS |
| Auth | Firebase (Google Sign-in) |
| Backend | Python 3.9+, Flask |
| Vector DB | Qdrant |
| Session | Redis |
| LLM | Groq (llama-3.3-70b), Gemini (fallback) |

---

## 📝 วิธีเพิ่ม Feature ใหม่

### เพิ่ม Component UI:
```
1. สร้างไฟล์ใน components/
2. Import ใน App.tsx
3. ใช้ state management ที่มีอยู่
```

### เพิ่ม API Endpoint:
```python
# ใน web_chatbot_v5.py
@app.route('/new-endpoint', methods=['POST'])
def new_endpoint():
    data = request.json
    # logic here
    return jsonify({"result": "..."})
```

### เพิ่ม Collection ใหม่ใน Qdrant:
```python
# ใน search_engine.py
COLLECTIONS['new_data'] = 'collection_name'
```

---

> 📌 **หมายเหตุ**: อ่าน README.md และ docs/SETUP.md สำหรับวิธี setup
