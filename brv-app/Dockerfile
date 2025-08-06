FROM python:3.10

WORKDIR /app

# Clean install tools and system libs
RUN apt-get update && apt-get install -y gcc libssl-dev default-libmysqlclient-dev && \
    rm -rf /var/lib/apt/lists/*

# Force upgrade pip and print version
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip --version

# Copy requirements first, so cache gets busted only when needed
COPY requirements.txt .

# Forcefully install everything fresh (with log output)
RUN echo "📦 Installing dependencies..." && \
    pip install --no-cache-dir -r requirements.txt && \
    pip show mysql-connector-python

# Copy all source code
COPY . .

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
