# Use official Python 3.12 slim image
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5007

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create persistent storage directories
RUN mkdir -p /app/backups /app/exports

# Expose application port
EXPOSE 5007

# Start application using Gunicorn (Multithreaded gthread mode for high concurrency and ultra-low latency)
CMD ["gunicorn", "--bind", "0.0.0.0:5007", "--workers", "4", "--threads", "4", "--worker-class", "gthread", "--timeout", "120", "--keep-alive", "5", "--max-requests", "1000", "--max-requests-jitter", "50", "wsgi:app"]
