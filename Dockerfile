FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py detector.py proof_renderer.py ./
COPY references ./references

CMD ["python", "bot.py"]

