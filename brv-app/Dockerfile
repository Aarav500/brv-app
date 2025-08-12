FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive

# Install required system packages
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    libpq-dev \
    build-essential \
    python3-dev \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python dependencies first (better caching)
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Install PostgreSQL driver
RUN pip install --no-cache-dir psycopg2-binary==2.9.9

# Copy main application code
COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
