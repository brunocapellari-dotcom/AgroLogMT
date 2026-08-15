FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/gateway

RUN useradd --no-create-home --shell /usr/sbin/nologin agrolog \
    && chown -R agrolog:agrolog /app
USER agrolog

CMD ["sh", "-c", "uvicorn gateway.main:app --host 0.0.0.0 --port ${PORT}"]
