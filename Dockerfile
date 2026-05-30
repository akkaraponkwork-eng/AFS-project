# ใช้ Official Image ของ Playwright (ครอบคลุม Dependencies ทั้งหมดของ Chromium อัตโนมัติ)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# ตั้ง Timezone เป็นไทย (UTC+7) แบบ non-interactive
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Bangkok

# ติดตั้ง curl, tzdata (non-interactive) และดาวน์โหลด cloudflared
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone && \
    rm -rf /var/lib/apt/lists/*
RUN curl -L --output /usr/local/bin/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && \
    chmod +x /usr/local/bin/cloudflared

# ตั้งค่า Working Directory ใน Container
WORKDIR /app

# คัดลอกไฟล์ requirements.txt และติดตั้ง Library
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกซอร์สโค้ดทั้งหมดลงใน Container
COPY . .

# เปิด Port 10000 (Render มักจะใช้ Port นี้)
EXPOSE 10000

# CMD สำหรับ web service — ใช้ entrypoint.py เพื่อรัน Gunicorn + Cloudflare Tunnel + Discord Notification
CMD ["python", "-u", "entrypoint.py"]
