FROM python:3.10-buster

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies needed to build mysql-connector-python
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    default-libmysqlclient-dev \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python requirements
COPY requirements.txt .

# Upgrade pip and install requirements
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Verify mysql-connector-python is installed
RUN python -c "import mysql.connector; print('✅ mysql-connector-python installed')"

# Copy application code
COPY . .

# Expose port
EXPOSE 8501

# Run Streamlit app
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
