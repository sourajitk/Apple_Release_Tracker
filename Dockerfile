FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and tests
COPY src/ ./src/
COPY tests/ ./tests/

# Set Python path to include src directory
ENV PYTHONPATH=/app/src

# Create data directory and non-root user
RUN mkdir -p /app/data && \
    useradd -u 1000 -m appuser && \
    chown -R appuser:appuser /app

USER appuser

CMD ["python", "src/main.py"]
