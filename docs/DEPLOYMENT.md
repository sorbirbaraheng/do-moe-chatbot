# 🚀 DO-MOE Chatbot — คู่มือ Deployment

> เอกสารนี้สำหรับโปรแกรมเมอร์ที่จะนำระบบขึ้น Production Server
> อัปเดตล่าสุด: กุมภาพันธ์ 2569

---

## 📋 สารบัญ

1. [สถาปัตยกรรมระบบ](#-สถาปัตยกรรมระบบ)
2. [สเปค Server ที่แนะนำ](#-สเปค-server-ที่แนะนำ)
3. [ขั้นตอน Deploy](#-ขั้นตอน-deploy)
4. [Environment Variables](#-environment-variables)
5. [Qdrant Vector Database](#-qdrant-vector-database)
6. [การจัดการ API Keys](#-การจัดการ-api-keys)
7. [คำสั่งดูแลระบบ](#-คำสั่งดูแลระบบ)
8. [Troubleshooting](#-troubleshooting)

---

## 🏗 สถาปัตยกรรมระบบ

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose                        │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌────────────────┐ │
│  │ Frontend  │    │   Backend    │    │     Redis      │ │
│  │  (Nginx)  │───▸│  (Gunicorn)  │───▸│  (Session +    │ │
│  │  :3001    │    │   :5001      │    │   Cache)       │ │
│  └──────────┘    └──────┬───────┘    └────────────────┘ │
│                         │                                │
│                    ┌────▼─────┐                          │
│                    │  Qdrant  │  ◀── Vector Database     │
│                    │  :6333   │      (ข้อมูลการศึกษา)    │
│                    └──────────┘                          │
└─────────────────────────────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │   External APIs     │
              │  • Groq (LLM)       │
              │  • Gemini (LLM)     │
              │  • Firebase (Auth)  │
              └─────────────────────┘
```

### Services ทั้งหมด

| Service | Technology | Port | หน้าที่ |
|---------|-----------|------|---------|
| **Frontend** | Next.js + Nginx | 3001 (→80) | UI หน้าเว็บ |
| **Backend** | Flask + Gunicorn | 5001 | API + AI Logic |
| **Redis** | Redis 7 | 6379 | Session memory + Cache |
| **Qdrant** | Qdrant | 6333 | Vector DB เก็บข้อมูลการศึกษา |

---

## 💻 สเปค Server ที่แนะนำ

| ผู้ใช้พร้อมกัน | CPU | RAM | Storage | ค่าใช้จ่าย/เดือน |
|---|---|---|---|---|
| 10–15 คน | 2 cores | 4 GB | 40 GB SSD | ~$12 |
| 30–50 คน | 4 cores | 8 GB | 80 GB SSD | ~$24 |
| 50–100 คน | 8 cores | 16 GB | 100 GB SSD | ~$48 |

> **OS ที่แนะนำ**: Ubuntu 22.04 LTS / Debian 12

### Cloud Providers ที่ใช้ได้

- DigitalOcean (แนะนำ — ง่ายสุด)
- AWS EC2
- Google Cloud VM
- Azure VM
- Linode / Vultr

---

## 📦 ขั้นตอน Deploy

### Step 1: ติดตั้ง Docker บน Server

```bash
# Ubuntu/Debian
sudo apt update && sudo apt upgrade -y

# ติดตั้ง Docker
curl -fsSL https://get.docker.com | sh

# ให้ user ปัจจุบันใช้ Docker ได้โดยไม่ต้อง sudo
sudo usermod -aG docker $USER

# ติดตั้ง Docker Compose (มากับ Docker แล้ว)
docker compose version   # ต้องได้ v2.x+
```

### Step 2: Clone โค้ด

```bash
cd /opt   # หรือ directory ที่ต้องการ
git clone <repository-url> moe-chatbot
cd moe-chatbot
```

### Step 3: ตั้งค่า Environment

```bash
# Backend env
cp deploy/.env.backend.example deploy/.env.backend
nano deploy/.env.backend   # ← ใส่ค่าจริงตามตาราง Section ถัดไป

# Frontend env
cp deploy/.env.frontend.example deploy/.env.frontend
nano deploy/.env.frontend   # ← ใส่ URL ของ server
```

### Step 4: ใส่ Firebase Service Account Key

```bash
# Copy ไฟล์ serviceAccountKey.json ไปที่ backend/
scp serviceAccountKey.json user@server:/opt/moe-chatbot/backend/
```

> ⚠️ **สำคัญ**: ไฟล์นี้มี credentials ของ Firebase — ห้าม commit ลง Git

### Step 5: Build & Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### Step 6: ตรวจสอบ

```bash
# ดูสถานะ containers
docker compose -f docker-compose.prod.yml ps

# ดู logs
docker compose -f docker-compose.prod.yml logs -f backend

# ทดสอบ API
curl http://localhost:5001/api/health
```

เปิด browser ไปที่ `http://<server-ip>:3001` ต้องเห็นหน้าเว็บ

---

## 🔑 Environment Variables

### Backend (`deploy/.env.backend`)

| ตัวแปร | ค่าที่ต้องใส่ | หมายเหตุ |
|--------|-------------|----------|
| `GEMINI_API_KEY` | `AIzaSy...` | จาก [AI Studio](https://aistudio.google.com/app/apikey) |
| `GROQ_API_KEY` | `gsk_...` | จาก [Groq Console](https://console.groq.com) (อย่างน้อย 1 key) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | โมเดล LLM |
| `QDRANT_URL` | `http://203.159.242.144:6333` | Qdrant server (ดู Section ถัดไป) |
| `QDRANT_TIMEOUT` | `60` | timeout วินาที |
| `REDIS_URL` | `redis://redis:6379/0` | ถ้าใช้ Redis ใน Docker Compose ← ใช้ค่านี้ |
| `SESSION_TTL_SECONDS` | `604800` | 7 วัน |
| `ADMIN_PASSWORD_HASH` | `pbkdf2:sha256:...` | ขอจากทีม Dev |
| `ADMIN_TOKEN_SECRET` | `<random-string>` | สร้างใหม่ด้วย `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `ALLOWED_ORIGINS` | `https://your-domain.com` | CORS domains (ใส่จริง) |
| `GUNICORN_WORKERS` | `4` | ตั้งเท่ากับจำนวน CPU cores |
| `GUNICORN_THREADS` | `4` | threads ต่อ worker |
| `ENABLE_DEBUG_ENDPOINTS` | `0` | **ปิดใน Production!** |

### Frontend (`deploy/.env.frontend`)

| ตัวแปร | ค่าที่ต้องใส่ | หมายเหตุ |
|--------|-------------|----------|
| `VITE_BACKEND_URL` | `https://your-domain.com` | URL ของ backend |
| `VITE_FLASK_API_URL` | `https://your-domain.com` | เหมือนกัน |
| `VITE_FIREBASE_API_KEY` | `AIzaSy...` | จาก Firebase Console |
| `VITE_FIREBASE_AUTH_DOMAIN` | `project.firebaseapp.com` | จาก Firebase Console |
| `VITE_FIREBASE_PROJECT_ID` | `chatbot-97475` | จาก Firebase Console |
| `VITE_FIREBASE_STORAGE_BUCKET` | `...appspot.com` | จาก Firebase Console |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | `123456789` | จาก Firebase Console |
| `VITE_FIREBASE_APP_ID` | `1:123:web:abc` | จาก Firebase Console |
| `VITE_FIREBASE_MEASUREMENT_ID` | `G-XXXXXXX` | จาก Firebase Console |

---

## 🗄 Qdrant Vector Database

### ข้อมูลปัจจุบัน

ตอนนี้ Qdrant ถูก host อยู่ที่ **`203.159.242.144:6333`** มี 34 collections รวม **~2.6 ล้าน records** ของข้อมูลการศึกษา

**Collections หลักที่ใช้:**

| Collection | Records | ข้อมูล |
|---|---|---|
| `edu_students_v5` | 638,661 | นักเรียนระดับจังหวัด |
| `edu_students_2567` | 641,090 | นักเรียน ปี 67 |
| `edu_schools_v5` | 55,629 | โรงเรียนระดับจังหวัด |
| `edu_schools_2567` | 56,101 | โรงเรียน ปี 67 |
| `edu_teachers_v5` | 120,542 | ครูระดับจังหวัด |
| `edu_teachers_2567` | 117,528 | ครู ปี 67 |
| `edu_ratios_v5` | 56,148 | อัตราส่วนนักเรียนต่อครู |
| `edu_grade_summary_v5` | 125,967 | สรุปตามชั้นเรียน |
| `edu_gender_overview_v5` | 16,795 | แยกตามเพศ |
| `edu_systems_v5` | 10,410 | สังกัด |
| `semantic_cache` | dynamic | แคชคำถาม |

### ทางเลือก Qdrant

**ทางเลือก A: ใช้ Qdrant ที่มีอยู่แล้ว (แนะนำ)**
- ตั้ง `QDRANT_URL=http://203.159.242.144:6333` ใน `.env.backend`
- ไม่ต้องติดตั้งอะไรเพิ่ม
- ⚠️ ต้องมั่นใจว่า server เข้าถึง IP นี้ได้

**ทางเลือก B: ติดตั้ง Qdrant บน Server เดียวกัน**
- เพิ่ม Qdrant ใน `docker-compose.prod.yml` (ดูด้านล่าง)
- ต้อง migrate ข้อมูลด้วย Qdrant Snapshot
- ใช้ RAM เพิ่ม ~2-4 GB

### วิธี Migrate Qdrant (ถ้าต้องการ)

```bash
# บน server เก่า — สร้าง snapshot แต่ละ collection
curl -X POST "http://203.159.242.144:6333/collections/edu_students_v5/snapshots"

# download snapshot
curl "http://203.159.242.144:6333/collections/edu_students_v5/snapshots/<snapshot-name>" \
  -o edu_students_v5.snapshot

# บน server ใหม่ — restore
curl -X POST "http://new-server:6333/collections/edu_students_v5/snapshots/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@edu_students_v5.snapshot"
```

> ทำซ้ำสำหรับทุก collection

---

## 🔑 การจัดการ API Keys

### Groq API Keys

ระบบรองรับ **multi-key rotation** — ใส่หลาย key ได้ใน Firebase Firestore:

```
Firestore > admin_config > school > groqKeys: ["gsk_key1", "gsk_key2", ...]
Firestore > admin_config > general > groqKeys: ["gsk_key3", "gsk_key4", ...]
```

ระบบจะ rotate keys อัตโนมัติเมื่อ key ใดโดน rate limit

**ถ้าไม่ใช้ Firebase**: ใส่ key เดียวใน `GROQ_API_KEY` env var

### Gemini API Keys

เช่นเดียวกัน — ใส่ใน Firestore หรือ `GEMINI_API_KEY` env var

### สร้าง API Key

| Provider | URL | Free Tier |
|---|---|---|
| Groq | https://console.groq.com | 30 req/min |
| Gemini | https://aistudio.google.com/app/apikey | 15 req/min |

---

## 📝 Docker Compose สำหรับ Production

ไฟล์ `docker-compose.prod.yml` ปัจจุบันมี backend + frontend แล้ว

ถ้าต้องการเพิ่ม Redis + Qdrant บน server เดียวกัน ให้เพิ่ม:

```yaml
# เพิ่มใน services: ของ docker-compose.prod.yml

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    command: redis-server --save 60 1 --loglevel warning
    networks:
      - moe-net

  qdrant:
    image: qdrant/qdrant:v1.12.4
    restart: unless-stopped
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "6333:6333"
    networks:
      - moe-net

# เพิ่มใน volumes:
volumes:
  redis_data:
  qdrant_data:
```

แล้วแก้ `deploy/.env.backend`:
```
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
```

---

## 🛠 คำสั่งดูแลระบบ

```bash
# Start ทุก service
docker compose -f docker-compose.prod.yml up -d

# Stop ทุก service
docker compose -f docker-compose.prod.yml down

# ดู logs (backend)
docker compose -f docker-compose.prod.yml logs -f backend

# Restart backend (deploy code ใหม่)
docker compose -f docker-compose.prod.yml up -d --build backend

# ดูสถานะ
docker compose -f docker-compose.prod.yml ps

# ลบ cache (Semantic + Redis)
curl -X POST http://localhost:5001/api/cache/flush

# ดู session count
curl http://localhost:5001/api/sessions/count

# ดูสถานะ Qdrant
curl http://localhost:6333/collections
```

---

## 🔒 Security Checklist

- [ ] ตั้ง `ENABLE_DEBUG_ENDPOINTS=0` ใน Production
- [ ] ตั้ง `ALLOWED_ORIGINS` ให้เฉพาะ domain ที่ใช้จริง
- [ ] เปลี่ยน `ADMIN_TOKEN_SECRET` เป็น random string ใหม่
- [ ] ไม่ commit `.env`, `serviceAccountKey.json` ลง Git
- [ ] ตั้ง firewall ปิด port 6333 (Qdrant) + 6379 (Redis) จากภายนอก
- [ ] ใช้ HTTPS (ผ่าน reverse proxy เช่น Cloudflare Tunnel หรือ Nginx + Let's Encrypt)

---

## 🐛 Troubleshooting

### Container ไม่ start

```bash
# ดู logs
docker compose -f docker-compose.prod.yml logs backend

# ปัญหาที่พบบ่อย:
# 1. ไม่มี serviceAccountKey.json → ใส่ไฟล์ใน backend/
# 2. QDRANT_URL ผิด → ตรวจว่า server เข้าถึง Qdrant ได้
# 3. Redis ไม่ available → ระบบ fallback เป็น SQLite อัตโนมัติ
```

### Chatbot ตอบช้า

1. เพิ่ม `GUNICORN_WORKERS` (ตาม CPU cores)
2. เพิ่ม Groq API keys (ใน Firebase หรือ env)
3. ตรวจ `ENABLE_SEMANTIC_CACHE=1` (ใช้ cache)

### Memory ไม่ถูก share ข้าม requests

ตรวจว่า Redis ทำงาน:
```bash
docker compose -f docker-compose.prod.yml exec redis redis-cli ping
# ต้องได้ PONG
```

### API Keys หมด quota

ดู logs:
```bash
docker compose -f docker-compose.prod.yml logs backend | grep "rate limit\|quota"
```
แก้: เพิ่ม keys ใน Firebase Firestore

---

## 📁 โครงสร้างไฟล์สำคัญ

```
moe-chatbot/
├── docker-compose.prod.yml      ← Docker Compose หลัก
├── deploy/
│   ├── docker/
│   │   ├── backend.Dockerfile   ← Build backend image
│   │   └── frontend.Dockerfile  ← Build frontend image
│   ├── nginx/
│   │   └── default.conf         ← Nginx config
│   ├── .env.backend             ← ⚠️ Backend secrets (ต้องสร้างเอง)
│   ├── .env.backend.example     ← Template
│   ├── .env.frontend            ← ⚠️ Frontend config (ต้องสร้างเอง)
│   └── .env.frontend.example    ← Template
├── backend/
│   ├── web_chatbot_v5.py        ← Flask API entry point
│   ├── gunicorn.conf.py         ← Gunicorn production config
│   ├── serviceAccountKey.json   ← ⚠️ Firebase key (ต้อง copy มาเอง)
│   ├── chatbot/                 ← Core chatbot logic
│   └── redis_session.py         ← Redis session storage
├── scripts/
│   ├── start.sh                 ← Start services (dev)
│   ├── stop.sh                  ← Stop services
│   ├── logs.sh                  ← View logs
│   └── status.sh                ← Check status
└── docs/
    └── DEPLOYMENT.md            ← เอกสารนี้
```

---

## ✅ สรุป Quick Start

```bash
# 1. Clone
git clone <repo> && cd moe-chatbot

# 2. Config
cp deploy/.env.backend.example deploy/.env.backend
cp deploy/.env.frontend.example deploy/.env.frontend
# แก้ไข .env files ตามตารางด้านบน

# 3. Firebase key
cp /path/to/serviceAccountKey.json backend/

# 4. Deploy!
docker compose -f docker-compose.prod.yml up -d --build

# 5. ตรวจสอบ
curl http://localhost:5001/api/health
# เปิด browser → http://<server-ip>:3001
```

**ใช้เวลา deploy ไม่เกิน 30 นาที** ถ้ามี server + Docker พร้อมแล้ว 🚀
