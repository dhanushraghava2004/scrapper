# Browsers + system deps preinstalled (matches your playwright==1.48.0)
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

# (Optional) keep image smaller by cleaning pip cache (the base image is slimmed already)
WORKDIR /app

# Install your Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your code
COPY . .

# Render injects $PORT; default to 8080 locally
ENV PORT=8080
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080}"]



