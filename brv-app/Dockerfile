FROM python:3.10-slim-buster

# Avoid interactive prompts during package install
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for mysql-connector-python to compile
RUN apt-get update && apt-get install -y \
    build-essential \
    default-libmysqlclient-dev \
    libssl-dev \
    libffi-dev \
    python3-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install them
COPY requirements.txt requirements.txt

# Upgrade pip before install
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Streamlit runs on port 8501
EXPOSE 8501

# Start Streamlit app
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
