# Deploy (Docker + Nginx) - MOE-One

This setup uses external Qdrant/Redis and runs:
- Flask backend (Gunicorn)
- Nginx serving Vite build + proxy /api to backend

## 1) Prepare env files

```bash
cp deploy/.env.backend.example deploy/.env.backend
cp deploy/.env.frontend.example deploy/.env.frontend
```

Edit both files with your real values:
- `deploy/.env.backend`
  - `GEMINI_API_KEY`, `GROQ_API_KEY`, `REDIS_URL`, `QDRANT_URL`
  - `ALLOWED_ORIGINS` must include your domain(s)
  - Use `ADMIN_PASSWORD_HASH` if possible
- `deploy/.env.frontend`
  - `VITE_BACKEND_URL` and `VITE_FLASK_API_URL` should be your domain
  - Firebase keys from your project

## 2) Build & start

```bash
docker compose --env-file deploy/.env.frontend -f docker-compose.prod.yml up -d --build
```

## 3) Verify

```bash
curl -s http://localhost:5001/api/health
```

If health is OK, open the frontend URL via Nginx:
- If on the same server: `http://SERVER_IP:3001`
- If behind TLS: `https://your-domain`

## Notes
- For real HTTPS, place a TLS terminator (Nginx/Traefik) in front of port 3001.
- If you already have a central Nginx, point it to this container.
- Stream endpoints need `proxy_buffering off` (already set in `deploy/nginx/default.conf`).

## Stop

```bash
docker compose -f docker-compose.prod.yml down
```
