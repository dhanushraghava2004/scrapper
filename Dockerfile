# Base Python
FROM python:3.11-slim

# System deps needed for Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl unzip fonts-liberation libnss3 libnss3-dev libatk1.0-0 libatk-bridge2.0-0 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpangocairo-1.0-0 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser
RUN python -m playwright install --with-deps chromium

# Copy app
COPY . .

# Render provides $PORT. Use it (fallback 8080 locally).
ENV PORT=8080
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]
