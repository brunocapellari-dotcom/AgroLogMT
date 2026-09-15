FROM node:22-alpine AS maritime-ui
WORKDIR /ui
COPY maritime_ui/package.json maritime_ui/package-lock.json /ui/
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY maritime_ui /ui
RUN npm run build

FROM python:3.14-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-gateway.txt /app/requirements-gateway.txt
RUN pip install --no-cache-dir --disable-pip-version-check -r /app/requirements-gateway.txt \
    && groupadd --system agrolog \
    && useradd --system --gid agrolog --home-dir /nonexistent --shell /usr/sbin/nologin agrolog
COPY --chown=agrolog:agrolog gateway /app/gateway
COPY --chown=agrolog:agrolog --from=maritime-ui /ui/dist /app/maritime_ui/dist

USER agrolog
CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8080"]
