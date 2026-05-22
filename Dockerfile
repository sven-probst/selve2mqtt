FROM python:3.14-slim

# Set version information
ARG VERSION=dev
ENV APP_VERSION=$VERSION
ENV WEB_PORT=8080

WORKDIR /app

# Install dependencies and curl for healthcheck
COPY requirements.txt .
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r requirements.txt

# Copy all python modules and configuration
COPY *.py config.yaml Logo.svg ./

# USB-Zugriff erlauben
RUN groupadd -g 1000 selve && \
    useradd -u 1000 -g selve -m selve && \
    usermod -a -G dialout selve
USER selve

EXPOSE ${WEB_PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${WEB_PORT}/health || exit 1

CMD ["python", "-u", "selve2mqtt.py"]
