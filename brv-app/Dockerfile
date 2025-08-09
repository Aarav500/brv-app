FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install required packages
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    default-libmysqlclient-dev \
    build-essential \
    python3-dev \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_23_9
ENV TNS_ADMIN=/opt/oracle/wallet

# 🔥 Install mysql-connector-python directly
RUN pip install --no-cache-dir mysql-connector-python==9.4.0

# ✅ Confirm mysql-connector installed
RUN python -c "import mysql.connector; print('✅ mysql-connector version:', mysql.connector.__version__)"

# Copy everything first
COPY . .

# Ensure oracle_db.py from the correct folder is placed in /app
COPY BRV1/BRV-app-OracleDB/oracle_db.py /app/oracle_db.py

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
