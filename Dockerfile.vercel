# One image, one process: Node builds the React app, then FastAPI serves it and /api.

FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=web /web/dist ./static
COPY data/raw ./data/raw
ENV STATIC_DIR=/srv/static \
    DATA_DIR=/srv/data/raw \
    PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/api/health')"
# sh -c so $PORT expands (Heroku injects its own); exec so uvicorn is PID 1 and gets
# SIGTERM directly (clean, fast shutdown).
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
