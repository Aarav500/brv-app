FROM python:3.10-buster

ENV DEBIAN_FRONTEND=noninteractive

# Install system-level build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    build-essential \
    default-libmysqlclient-dev \
    python3-dev \
    libaio1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first (caching layer)
COPY requirements.txt .

# Upgrade pip
RUN pip install --upgrade pip

# Install mysql-connector-python FIRST
RUN pip install --no-cache-dir mysql-connector-python==9.4.0

# Install rest of the packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy all app code
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
