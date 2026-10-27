FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PANEL_HOST=0.0.0.0 \
    PANEL_PORT=8000 \
    DB_PATH=/data/viktorina.db

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

# Baza shu papkada saqlanadi — Coolify'da unga doimiy disk (volume) ulanadi
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
CMD ["python", "bot.py"]
