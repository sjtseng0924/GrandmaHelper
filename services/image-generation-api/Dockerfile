FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and Chinese fonts
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    fontconfig \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY tests/ ./tests/

# Expose the port
EXPOSE 8081

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8081
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "src/core/app.py"]