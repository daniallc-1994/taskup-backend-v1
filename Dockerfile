# Use official Python runtime
FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway will override with $PORT)
EXPOSE 8000

# Start FastAPI
CMD ["sh", "-c", "uvicorn backend.fastapi_main:app --host 0.0.0.0 --port ${PORT:-8000}"]
