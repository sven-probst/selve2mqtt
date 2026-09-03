FROM python:3.12-slim-trixie AS builder

WORKDIR /app

# OS packages (build-essential is needed to compile any missing binary wheels).
# apt-get upgrade is kept so security fixes land in the final image.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends build-essential

# Install Python deps in a separate stage-cached layer so app code changes
# do not re-run pip.
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

FROM python:3.12-slim-trixie AS runner

ARG VERSION=dev
ENV APP_VERSION=$VERSION
ENV WEB_PORT=8080
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Runner stage: only needs curl for healthcheck; skip build-essential.
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl

COPY --from=builder /opt/venv /opt/venv

COPY . .

RUN cp config.yaml.example config.yaml

RUN groupadd -g 1000 selve && \
    useradd -u 1000 -g selve -m selve && \
    usermod -a -G dialout selve
USER selve

EXPOSE ${WEB_PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:${WEB_PORT}/health || exit 1

CMD ["python", "-u", "selve2mqtt.py"]

