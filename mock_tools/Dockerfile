FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Default; overridden per-service in docker-compose.yml
CMD ["uvicorn", "tool_a:app", "--host", "0.0.0.0", "--port", "8000"]
