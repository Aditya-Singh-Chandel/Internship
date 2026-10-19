# ==============================================================================
# Dockerfile: The step-by-step recipe to build our FastAPI image
# ==============================================================================

# 1. Base Image: Start from an official Linux system that already has Python 3.11
FROM python:3.11-slim

# 2. Environment Variables:
# - PYTHONDONTWRITEBYTECODE=1: Don't clutter container with .pyc bytecode files
# - PYTHONUNBUFFERED=1: Print terminal logs instantly without buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. Working Directory: Like doing "mkdir /app && cd /app" inside the container
WORKDIR /app

# # 4. Install system tools: Install curl for healthchecks and clean up cache
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     curl \
#     && rm -rf /var/lib/apt/lists/*

# 5. Copy dependencies list first (crucial for Docker layer caching)
COPY requirements.txt .

# 6. Install Python packages inside the Linux image
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy all our application source code into /app
COPY . .

# 8. Expose port 8000 (documentation for developers and Docker)
EXPOSE 8000

# 9. The command to execute when the container is launched
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
