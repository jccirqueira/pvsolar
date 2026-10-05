FROM python:3.11-slim

LABEL maintainer="pvSolar Team"
LABEL description="pvSolar Reports - Automated Report Generation"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

RUN mkdir -p /app/output/pdf /app/output/excel

EXPOSE 8002

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/health')" || exit 1

CMD ["python", "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8002"]
