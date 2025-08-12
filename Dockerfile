# Dockerfile
FROM python:3.11-slim

# Install system deps needed by google client & psycopg2
RUN apt-get update && apt-get install -y build-essential libpq-dev gcc curl --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy app
COPY . /app

# Create a directory for secrets (for google key)
VOLUME ["/run/secrets"]

# Expose Streamlit port
ENV PORT=8501
EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
