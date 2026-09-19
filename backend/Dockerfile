FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Tesseract (OCR), pyzbar, WeasyPrint (PDF), onnxruntime (RapidOCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libzbar0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
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

# Create upload directories (persisted via Render disk / volume when configured)
RUN mkdir -p uploads/reports

# Make the startup script executable (host builds may strip the exec bit)
RUN chmod +x render_start.sh

EXPOSE 8000

# Run Alembic migrations + seed the rule book, then start the API server.
# Previously the container started uvicorn directly, so migrations/seed never ran
# on Render -> empty Rule Book and 'DATABASE ENTRY NOT WORKING'.
CMD ["sh", "./render_start.sh"]
