# Use official Python 3.10 image
FROM python:3.10

# Set working directory inside the container
WORKDIR /app

# Install OS-level dependencies (required for mysql-connector and others)
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    gcc \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Step 3: Install mysql-connector-python explicitly with verbose logging
RUN pip install --no-cache-dir --verbose mysql-connector-python==9.4.0

# Copy the rest of your app
COPY . .

# Expose Streamlit default port
EXPOSE 8501

# Start the Streamlit app
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
