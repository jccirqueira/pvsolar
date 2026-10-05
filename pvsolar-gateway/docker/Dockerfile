FROM python:3.11-slim

LABEL maintainer="pvSolar Team"
LABEL description="pvSolar Gateway - Solar Inverter Monitoring"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

# O gateway importa pacotes de topo dentro de src/ (web, mqtt, drivers, edge, ...)
ENV PYTHONPATH=/app/src

# 8000 = API/Web do gateway (ecossistema) | 9090 = Prometheus metrics
EXPOSE 8000 9090

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["python", "-m", "core.gateway", "-c", "config/gateway.yaml"]
