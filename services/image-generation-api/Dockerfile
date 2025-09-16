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
COPY main.py .
COPY text_pic.py .
COPY config/ ./config/

# Expose the port
EXPOSE 8081

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8081

# Run the application
CMD ["python", "main.py"]