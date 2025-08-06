FROM python:3.10

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc libssl-dev default-libmysqlclient-dev && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirements and force fresh install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip show mysql-connector-python

# Copy rest of the app
COPY . .

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
