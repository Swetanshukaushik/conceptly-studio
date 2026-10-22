# Conceptly Studio — Production Dockerfile
FROM python:3.9-slim

# Avoid prompt dialogs during apt installs
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies: FFmpeg, system fonts, audio libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy source code and config
COPY . .

# Create media output directory
RUN mkdir -p output

EXPOSE 8000

# Start FastAPI Studio server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
