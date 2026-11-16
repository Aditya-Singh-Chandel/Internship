# ==============================================================================
# Dockerfile: The step-by-step recipe to build our FastAPI image
# ==============================================================================

# 0. Frontend build stage: compile the React app into static files (frontend/dist)
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 1. Base Image: Start from an official Linux system with Python 3.12 (matches the local venv)
FROM python:3.12-slim

# 2. Environment Variables:
# - PYTHONDONTWRITEBYTECODE=1: Don't clutter container with .pyc bytecode files
# - PYTHONUNBUFFERED=1: Print terminal logs instantly without buffering
# - FASTEMBED_CACHE_PATH: Where the embedding model is downloaded (a volume in docker-compose)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FASTEMBED_CACHE_PATH=/tmp/fastembed_cache

# 3. Working Directory: Like doing "mkdir /app && cd /app" inside the container
WORKDIR /app

# 4. Copy dependencies list first (crucial for Docker layer caching)
COPY requirements.txt .

# 5. Install Python packages inside the Linux image
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy the backend source code and the built frontend (served by FastAPI at /app)
COPY app ./app
COPY scripts ./scripts
COPY --from=frontend /frontend/dist ./frontend/dist

# 7. Run as an unprivileged user instead of root
RUN useradd --create-home appuser \
    && mkdir -p /tmp/fastembed_cache \
    && chown appuser /tmp/fastembed_cache
USER appuser

# 8. Expose port 8000 (documentation for developers and Docker)
EXPOSE 8000

# 9. The command to execute when the container is launched
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
