FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install required system packages + unzip + curl for downloading Instant Client
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    default-libmysqlclient-dev \
    build-essential \
    python3-dev \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 🔽 Download and install Oracle Instant Client
RUN curl -o /tmp/instantclient.zip https://download.oracle.com/otn_software/linux/instantclient/2390000/instantclient-basic-linux.x64-23.9.0.0.0dbru.zip \
    && unzip /tmp/instantclient.zip -d /opt/oracle \
    && rm /tmp/instantclient.zip

# Set library path for Oracle Client
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient_23_9:$LD_LIBRARY_PATH

# 🔥 Install mysql-connector-python directly
RUN pip install --no-cache-dir mysql-connector-python==9.4.0

# ✅ Confirm it's installed
RUN python -c "import mysql.connector; print('✅ mysql-connector version:', mysql.connector.__version__)"

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
