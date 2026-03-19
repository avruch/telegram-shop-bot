FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Data volume — mount a Railway/Docker volume here to persist shop.db
VOLUME ["/data"]

CMD ["python", "main.py"]
