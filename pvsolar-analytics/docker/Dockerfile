FROM python:3.11-slim

LABEL maintainer="pvSolar Team"
LABEL description="pvSolar Analytics - AI/ML Analytics Platform"

WORKDIR /app

# Dependencias de compilacao (driver PostgreSQL e bibliotecas ML)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ src/
COPY config/ config/
COPY ml_models/ ml_models/

EXPOSE 8001

# Sem rota /health no Analytics: check TCP na porta da API
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.connect(('localhost', 8001)); s.close()" || exit 1

# Entry point real: factory create_app(config) via main() (--host/--port sobrepoe a config)
CMD ["python", "-m", "src.core.app", "-c", "config/analytics.yaml", "--host", "0.0.0.0", "--port", "8001"]
