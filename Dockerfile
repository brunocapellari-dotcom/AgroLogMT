FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements-collector.txt /app/requirements-collector.txt
RUN pip install --no-cache-dir -r /app/requirements-collector.txt
COPY collector /app/collector

ENTRYPOINT ["python", "-m", "collector.cloud_runner"]
