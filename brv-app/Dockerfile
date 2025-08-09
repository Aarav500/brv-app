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

# 🔽 Copy Oracle Instant Client from VM local path
COPY oracle/instantclient_23_9 /opt/oracle/instantclient_23_9

# 🔽 Copy Oracle Wallet from VM local path
COPY Wallet_brvdb1 /opt/oracle/wallet

# Set environment variables
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_23_9
ENV TNS_ADMIN=/opt/oracle/wallet

# 🔥 Install mysql-connector-python directly
RUN pip install --no-cache-dir mysql-connector-python==9.4.0

# ✅ Confirm mysql-connector installed
RUN python -c "import mysql.connector; print('✅ mysql-connector version:', mysql.connector.__version__)"

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
