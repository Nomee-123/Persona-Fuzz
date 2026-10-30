FROM node:22-slim AS ui
WORKDIR /app/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PF_RUNS_DIR=/app/runs
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY engine ./engine
COPY contracts ./contracts
COPY fixtures ./fixtures
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY --from=ui /app/ui/dist ./ui/dist
RUN mkdir -p /app/runs /app/results
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"
CMD ["python", "-m", "engine.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
