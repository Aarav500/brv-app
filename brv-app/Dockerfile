FROM python:3.10-buster

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

# Log everything during pip install
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --verbose -r requirements.txt

# ⛔ Fail early if mysql-connector-python was not installed
RUN python -c "import mysql.connector; print('✅ mysql-connector-python version:', mysql.connector.__version__)" || (echo '❌ mysql-connector-python failed to import' && exit 1)

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
