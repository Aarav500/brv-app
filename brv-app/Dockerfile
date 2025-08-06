FROM python:3.10-slim

# Prevent interactive prompts during install
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# 🧱 Install system dependencies needed for some Python packages
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# 🚀 Upgrade pip, setuptools, wheel to avoid silent install failures
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 📦 Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 📁 Copy application code
COPY . .

# 🔥 Start the app
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
