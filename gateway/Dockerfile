FROM node:22-alpine AS maritime-ui
WORKDIR /ui
COPY maritime_ui/package.json /ui/package.json
RUN npm install --package-lock=false
COPY maritime_ui /ui
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-gateway.txt /app/requirements-gateway.txt
RUN pip install --no-cache-dir -r /app/requirements-gateway.txt
COPY gateway /app/gateway
COPY contracts /app/contracts
COPY --from=maritime-ui /ui/dist /app/maritime_ui/dist
CMD ["uvicorn", "gateway.production_app:app", "--host", "0.0.0.0", "--port", "8080"]
