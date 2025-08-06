FROM python:3.10-buster

ENV DEBIAN_FRONTEND=noninteractive

# Add all system dependencies first
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    default-libmysqlclient-dev \
    build-essential \
    python3-dev \
    libaio1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install mysql-connector-python FIRST, explicitly
COPY requirements.txt .

# First upgrade pip
RUN pip install --upgrade pip

# Install mysql-connector-python separately
RUN pip install --no-cache-dir --prefer-binary mysql-connector-python==9.4.0

# Install the rest of the requirements
RUN pip install --no-cache-dir -r requirements.txt || true

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
