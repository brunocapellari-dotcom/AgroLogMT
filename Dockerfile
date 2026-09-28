FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-collector.txt /app/requirements-collector.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r /app/requirements-collector.txt \
    && groupadd --system agrolog \
    && useradd --system --gid agrolog --home-dir /nonexistent --shell /usr/sbin/nologin agrolog
COPY --chown=agrolog:agrolog collector /app/collector
COPY --chown=agrolog:agrolog models /app/models

USER agrolog
ENTRYPOINT ["python", "-m", "collector.cloud_runner"]
