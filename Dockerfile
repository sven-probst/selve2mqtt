FROM python:3.12-slim

# Set version information
ARG VERSION=dev
ENV APP_VERSION=$VERSION
ENV WEB_PORT=8080

WORKDIR /app

# Install dependencies and curl for healthcheck
# Using cache mounts speeds up multi-arch builds by persisting downloaded packages
COPY requirements.txt .

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends curl

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy all python modules and configuration
COPY . .

# Use the example configuration as a default. 
# This ensures the container can start even if no config.yaml is mounted.
RUN cp config.yaml.example config.yaml

# USB-Zugriff erlauben
RUN groupadd -g 1000 selve && \
    useradd -u 1000 -g selve -m selve && \
    usermod -a -G dialout selve
USER selve

EXPOSE ${WEB_PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${WEB_PORT}/health || exit 1

CMD ["python", "-u", "selve2mqtt.py"]
