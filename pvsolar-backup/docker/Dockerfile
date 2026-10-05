FROM python:3.11-slim

LABEL maintainer="pvSolar Team"
LABEL description="pvSolar Backup - Automated Backup & Restore"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

RUN mkdir -p /app/backups /app/data

EXPOSE 8008

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8008/health')" || exit 1

CMD ["python", "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8008"]
