# MOE‑One Handoff – Production Deploy Guide (Docker)

This guide is for the engineer who will deploy MOE‑One to the organization server.
The setup uses **external Qdrant + external Redis** and runs:
- **Backend**: Flask + Gunicorn
- **Frontend**: Vite build served by Nginx (container)

---

## 1) Prerequisites on server
- Docker Engine + Docker Compose plugin (v2)
- Network access to **Qdrant** and **Redis**
- Optional: domain + HTTPS (recommended)

---

## 2) Required files (do NOT commit secrets)

### A) Backend env
Create `deploy/.env.backend` on the server:
```
GEMINI_API_KEY=
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile

QDRANT_URL=http://<qdrant-host>:6333
QDRANT_TIMEOUT=60

REDIS_URL=redis://user:pass@host:6379/0
SESSION_TTL_SECONDS=604800

ALLOWED_ORIGINS=https://your-domain,https://www.your-domain

ADMIN_PASSWORD_HASH=
OPERATOR_PASSWORD_HASH=
VIEWER_PASSWORD_HASH=
ADMIN_TOKEN_SECRET=change-me
ADMIN_TOKEN_TTL_SECONDS=43200

ENABLE_DEBUG_ENDPOINTS=0
DISABLE_FIRESTORE=0

GUNICORN_WORKERS=4
GUNICORN_THREADS=4
GUNICORN_LOG_LEVEL=info
```

> If you don’t want hash now, you can use `ADMIN_PASSWORD=` (plain) but **hash is recommended**.

### B) Frontend env
Create `deploy/.env.frontend` on the server:
```
VITE_BACKEND_URL=https://your-domain
VITE_FLASK_API_URL=https://your-domain
VITE_FIREBASE_API_KEY=
VITE_FIREBASE_AUTH_DOMAIN=
VITE_FIREBASE_PROJECT_ID=
VITE_FIREBASE_STORAGE_BUCKET=
VITE_FIREBASE_MESSAGING_SENDER_ID=
VITE_FIREBASE_APP_ID=
VITE_FIREBASE_MEASUREMENT_ID=
```

### C) Optional Firebase admin key
If Firebase Admin is required, place:
```
backend/serviceAccountKey.json
```

---

## 3) Deploy
From project root:
```bash
docker compose --env-file deploy/.env.frontend -f docker-compose.prod.yml up -d --build
```

Check containers:
```bash
docker compose -f docker-compose.prod.yml ps
```

Health check:
```bash
curl -s http://localhost:5001/api/health
```

Access:
- If LAN only: `http://SERVER_IP:3001`
- If public + SSL: `https://your-domain`

---

## 4) Logs
```bash
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f frontend
```

---

## 5) Update flow
```bash
# pull new code / replace folder

docker compose --env-file deploy/.env.frontend -f docker-compose.prod.yml up -d --build
```

---

## 6) HTTPS (recommended)
Use host‑level Nginx/Traefik to terminate TLS and forward to container `frontend:3001`.
Important:
- Enable `proxy_buffering off` for `/api/` streaming
- Ensure `ALLOWED_ORIGINS` includes your domain

---

## 7) Troubleshooting
- **CORS errors** → check `ALLOWED_ORIGINS` and rebuild frontend with correct `VITE_*` URLs
- **Streaming cuts** → check Nginx has `proxy_buffering off` and `proxy_read_timeout 300`
- **Admin login slow** → check Firebase/Firestore availability

---

## 8) Hash admin passwords (recommended)
From inside backend container or a python venv with werkzeug:
```bash
python - <<'PY'
from werkzeug.security import generate_password_hash
print(generate_password_hash("YourPasswordHere"))
PY
```

Put the hash into `ADMIN_PASSWORD_HASH` (and remove plain password).
