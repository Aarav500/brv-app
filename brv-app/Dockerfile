FROM python:3.10

# Install all likely dependencies for mysql-connector
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    libffi-dev \
    libaio1 \
    default-libmysqlclient-dev \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
