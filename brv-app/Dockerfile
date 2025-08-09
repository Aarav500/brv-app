FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install required system packages
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

# Copy Python dependencies first (better caching)
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables for Oracle
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_23_9
ENV TNS_ADMIN=/opt/oracle/wallet

# Install MySQL connector
RUN pip install --no-cache-dir mysql-connector-python==9.4.0
RUN python -c "import mysql.connector; print('✅ mysql-connector version:', mysql.connector.__version__)"

# 🔹 Copy main application code
COPY . .

# 🔹 Copy oracle_db.py from BRV-app-OracleDB into the container
# (This works because we’ll set build context to /home/ubuntu/BRV1 in deploy script)
COPY BRV-app-OracleDB/oracle_db.py /app/oracle_db.py

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
