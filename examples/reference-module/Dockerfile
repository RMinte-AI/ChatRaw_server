FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py manifest.example.json private_dependency.py ./

ENV REFERENCE_MODULE_DATA_DIR=/app/data
EXPOSE 8765

CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8765"]
