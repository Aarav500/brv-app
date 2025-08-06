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

# Copy and install dependencies
COPY requirements.txt .

# Force pip to upgrade and fail clearly on bad install
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt || (echo "❌ Pip install failed" && exit 1)

# Check if mysql-connector-python is really installed
RUN python -c "import mysql.connector; print('✅ mysql-connector-python installed')"

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
