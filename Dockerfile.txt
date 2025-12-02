FROM python:3.13-slim

# Create working directory
WORKDIR /app

# Install system deps (optional but safe)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the whole project
COPY . .

# Railway sets PORT env var; default to 8000 locally
ENV PORT=8000

# Start FastAPI (our app is backend.fastapi_main:app)
CMD ["sh", "-c", "uvicorn backend.fastapi_main:app --host 0.0.0.0 --port ${PORT:-8000}"]
``
