FROM python:3.11-slim

LABEL maintainer="pvSolar Team"
LABEL description="pvSolar SCADA - HMI/SCADA Dashboard"

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY config/ ./config/

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import socket; s = socket.socket(); s.connect(('localhost', 5000)); s.close()" || exit 1

# Run application
CMD ["python", "-m", "src.app", "-c", "config/scada.yaml"]
