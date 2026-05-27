FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    wget curl ca-certificates fonts-liberation \
    libatk-bridge2.0-0 libatk1.0-0 libcairo2 libcups2 \
    libdbus-1-3 libdrm2 libgbm1 libglib2.0-0 libnspr4 libnss3 \
    libpango-1.0-0 libx11-6 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libxrender1 libxtst6 \
    xdg-utils libasound2 xvfb \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем Chromium через Playwright (используется cloakbrowser)
RUN playwright install chromium --with-deps

COPY . .

EXPOSE 5000

CMD ["python", "server.py"]
