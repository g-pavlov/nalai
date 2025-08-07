# syntax=docker/dockerfile:1.4

# --- Build Stage ---
FROM python:3.12-slim AS build

# Install build tools and Poetry
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        gcc \
        build-essential \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

WORKDIR /build

# Copy stable dependency files first (for best caching)
COPY pyproject.toml poetry.lock ./

# Install Poetry (cached layer)
RUN pip install --no-cache-dir poetry==2.1.3 && poetry config virtualenvs.create false

# Install the export plugin
RUN poetry self add poetry-plugin-export

# Copy source code last in build stage (changes frequently)
COPY src/ ./src/

# Generate requirements.txt for production
RUN poetry export --without-hashes --without-urls --without=dev -o requirements.txt && \
    echo "." >> requirements.txt

# --- Runtime Stage ---
FROM python:3.12-slim AS runtime

# Build arguments for platform detection
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH

# Install only essential runtime dependencies (minimal)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        && rm -rf /var/lib/apt/lists/* \
        && apt-get clean \
        && rm -rf /var/cache/apt/*

# Copy requirements.txt and source code from build stage
COPY --from=build /build/requirements.txt /tmp/
COPY --from=build /build/src/ /tmp/src/
COPY --from=build /build/pyproject.toml /tmp/
COPY --from=build /build/poetry.lock /tmp/

# Install Python dependencies with uv for ultra-fast parallel downloads (cached layer)
RUN pip install --no-cache-dir uv && \
    cd /tmp && uv pip install --system --index-url https://pypi.org/simple/ --index-strategy unsafe-best-match -r requirements.txt && \
    # Remove uv after install
    pip uninstall -y uv && \
    # Remove source code after installing as system package
    rm -rf /tmp/src/ && \
    # Remove requirements.txt and project files after installation
    rm -f /tmp/requirements.txt /tmp/pyproject.toml /tmp/poetry.lock

# Copy config files to system location
COPY logging.yaml /etc/nalai/logging.yaml

# Create data directories with appropriate permissions
RUN mkdir -p /var/lib/nalai/api_specs /var/log/nalai && \
    chmod 755 /var/log/nalai /var/lib/nalai/api_specs

# Create non-root user for running the application
RUN useradd --system --no-create-home --shell /bin/false nalai && \
    chown -R nalai:nalai /var/log/nalai /var/lib/nalai

# Set environment variables for container runtime
ENV LOG_CONFIG_PATH=/etc/nalai/logging.yaml
ENV LOG_DIR=/var/log/nalai

USER nalai

EXPOSE 8080

CMD ["uvicorn", "nalai.server:app", "--host", "0.0.0.0", "--port", "8080"] 