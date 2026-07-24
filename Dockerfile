# ChatRaw Dockerfile - Python FastAPI
FROM python:3.11-slim

WORKDIR /app

# Install build dependencies for ARM platforms
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/main.py .
COPY backend/auth.py .
COPY backend/db_migrations.py .
COPY backend/db_runtime.py .
COPY backend/module_protocol.py .
COPY backend/module_registry.py .
COPY backend/module_task_protocol.py .
COPY backend/module_tasks.py .
COPY backend/resident_integrations.py .
COPY backend/server_data.py .
COPY backend/contracts ./contracts
COPY backend/static ./static
COPY Plugins ./Plugins
COPY scripts/prepare-server-secrets.py ./scripts/prepare-server-secrets.py
COPY scripts/server-entrypoint.sh ./scripts/server-entrypoint.sh

# Keep the image data directory empty so a newly created volume is also empty.
# Runtime initialization creates its plugin and secret subdirectories.
RUN mkdir -p /app/data

# Environment
ENV PORT=51111
ENV DATA_DIR=/app/data

EXPOSE 51111

CMD ["sh", "/app/scripts/server-entrypoint.sh"]
