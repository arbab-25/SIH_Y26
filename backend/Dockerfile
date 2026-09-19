FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Tesseract, WeasyPrint, pyzbar
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libzbar0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-xlib-2.0-0 \
    libffi-dev \
    libcairo2 \
    libglib2.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create upload directory
RUN mkdir -p uploads/reports

# Make startup script executable
RUN chmod +x render_start.sh

EXPOSE 8000

# render_start.sh: runs migrations + seed + uvicorn on $PORT
# docker-compose overrides CMD with its own command: block
CMD ["./render_start.sh"]
