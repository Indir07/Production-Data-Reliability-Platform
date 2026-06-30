FROM python:3.12-slim

# Security: run as non-root
RUN groupadd -r pdrp && useradd -r -g pdrp pdrp

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY app/ ./app/

# Switch to non-root user
USER pdrp

EXPOSE 8000

# Production: 2 workers per CPU core + 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "3", "--log-config", "/dev/null"]
