FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    default-libmysqlclient-dev \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install general dependencies
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt || true

# ⛑️ Force install mysql-connector-python (bypass silent failure in bulk install)
RUN pip install --no-cache-dir mysql-connector-python==9.4.0

# Validate install
RUN python -c "import mysql.connector; print('✅ mysql-connector-python installed:', mysql.connector.__version__)"

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
