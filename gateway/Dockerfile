FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-gateway.txt /app/requirements-gateway.txt
RUN pip install --no-cache-dir -r /app/requirements-gateway.txt
COPY gateway /app/gateway
CMD ["uvicorn", "gateway.app:app", "--host", "0.0.0.0", "--port", "8080"]
