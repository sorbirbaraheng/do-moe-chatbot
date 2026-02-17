FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build deps (if needed) and python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

EXPOSE 5001

CMD ["gunicorn", "-c", "gunicorn.conf.py", "web_chatbot_v5:app"]
