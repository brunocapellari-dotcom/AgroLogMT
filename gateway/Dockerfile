FROM node:22-alpine AS maritime-ui
WORKDIR /ui
COPY maritime_ui/package.json /ui/package.json
RUN npm install --ignore-scripts --no-audit --no-fund --package-lock=false
COPY maritime_ui /ui
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-gateway.txt /app/requirements-gateway.txt
RUN pip install --no-cache-dir -r /app/requirements-gateway.txt \
    && useradd --system --uid 10001 --create-home --home-dir /home/agrolog --shell /usr/sbin/nologin agrolog
COPY --chown=agrolog:agrolog gateway /app/gateway
COPY --from=maritime-ui --chown=agrolog:agrolog /ui/dist /app/maritime_ui/dist
USER 10001
CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8080", "--no-server-header", "--no-date-header", "--proxy-headers"]
