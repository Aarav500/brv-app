FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    default-libmysqlclient-dev \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip

# ❗ Remove mysql-connector-python from requirements.txt before this!
RUN pip install --no-cache-dir -r requirements.txt

# 👇 Force install separately to catch install issues
RUN pip install --no-cache-dir mysql-connector-python==9.4.0

RUN python -c "import mysql.connector; print('✅ Installed:', mysql.connector.__version__)"

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
