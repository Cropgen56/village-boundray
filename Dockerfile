# =============================================================================
# Stage 1 — builder
# Install system GDAL deps + Python dependencies into a virtual env.
# Keeps the final image clean (no build tools, no apt cache).
# =============================================================================
FROM python:3.11-slim-bookworm AS builder

# System deps needed by GDAL / GeoPandas / Shapely
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgdal-dev \
        gdal-bin \
        libgeos-dev \
        libproj-dev \
        libspatialindex-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate a virtual env
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .

# Install Python deps (GDAL C bindings must match system GDAL version)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# =============================================================================
# Stage 2 — runtime
# Lean image: only the venv + app code + data.
# =============================================================================
FROM python:3.11-slim-bookworm AS runtime

LABEL maintainer="maharashtra-boundary-api"
LABEL description="FastAPI service to look up village / taluka / district boundaries in Maharashtra"

# Runtime-only GDAL shared libraries (no -dev, no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgdal32 \
        libgeos-c1v5 \
        libproj25 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /home/appuser/app

# Copy application code
COPY app/        ./app/
COPY run.py      ./run.py

# Switch to non-root
RUN chown -R appuser:appuser /home/appuser/app
USER appuser

# Expose API port
EXPOSE 8080

# GeoJSON data is NOT in the image: it is downloaded from Cloud Storage at
# startup using Application Default Credentials (GCS_* env vars).

# Health check — uvicorn only opens the port after data has loaded,
# so a TCP connect means the API is ready (no separate /health route)
HEALTHCHECK --interval=30s --timeout=10s --start-period=180s --retries=3 \
    CMD python -c "import socket; socket.create_connection(('localhost', 8080), 5)" \
    || exit 1

# Start the server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
