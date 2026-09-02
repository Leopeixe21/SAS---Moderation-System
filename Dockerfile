FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py detector.py moderation_text.py proof_renderer.py timeout_store.py ./
COPY references ./references

CMD ["python", "bot.py"]
