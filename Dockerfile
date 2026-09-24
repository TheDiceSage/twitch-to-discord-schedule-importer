FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
WORKDIR /app/bot

VOLUME ["/app/bot/data"]
ENV DB_PATH=/app/bot/data/schedule_sync.db

CMD ["python", "main.py"]
