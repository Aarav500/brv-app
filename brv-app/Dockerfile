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

# Install everything *except* mysql-connector-python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 🔥 Install mysql-connector-python *manually*
RUN pip install --no-cache-dir mysql-connector-python==9.4.0

# 🔍 Confirm it's installed INSIDE the container
RUN python -c "import mysql.connector; print('✅ mysql-connector version:', mysql.connector.__version__)"

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
