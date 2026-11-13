FROM python:3.11-slim

WORKDIR /app

COPY requirements_v2.txt .
RUN pip install --no-cache-dir -r requirements_v2.txt --index-url https://pypi.org/simple

COPY main_v2.py .

CMD ["sh", "-c", "uvicorn main_v2:app --host 0.0.0.0 --port ${PORT:-8080}"]
