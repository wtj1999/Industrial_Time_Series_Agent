# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install --index-url "${PIP_INDEX_URL}" --upgrade pip \
    && pip install --index-url "${PIP_INDEX_URL}" -r requirements.txt

COPY agent_app ./agent_app

RUN mkdir -p /app/uploads /app/agent_app/artifacts/anomaly_detection \
    /app/agent_app/artifacts/prediction_models

EXPOSE 8000
WORKDIR /app

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["sh", "-c", "exec uvicorn agent_app.api:app --host 0.0.0.0 --port 8000 --workers ${API_WORKERS:-1}"]


FROM node:20-alpine AS frontend-build

WORKDIR /frontend
ARG NPM_REGISTRY=https://registry.npmmirror.com
COPY frontend/package.json frontend/package-lock.json ./
RUN npm config set registry "${NPM_REGISTRY}" \
    && npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm config set fetch-timeout 300000 \
    && npm ci --no-audit --no-fund
COPY frontend/ ./
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npm run build


FROM nginx:1.27-alpine AS frontend

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /frontend/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q --spider http://localhost/health || exit 1
