FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SPARKLE_WORKER_HOST=0.0.0.0 \
    SPARKLE_WORKER_PORT=8770 \
    SPARKLE_WORKER_STATE_DIR=/var/lib/sparkle-worker \
    SPARKLE_WORKER_EXECUTOR=bubblewrap \
    SPARKLE_WORKER_BWRAP=/usr/bin/bwrap \
    SPARKLE_WORKER_PYTHON=/usr/local/bin/python3 \
    SPARKLE_WORKER_TRUSTED_TLS_TERMINATION=true \
    SPARKLE_WORKER_SIGNING_KEY_FILE=/run/secrets/sparkle-worker-signing-key

RUN apt-get update \
    && apt-get install --no-install-recommends -y bubblewrap ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --home-dir /nonexistent --shell /usr/sbin/nologin sparkle-worker \
    && install -d -o sparkle-worker -g sparkle-worker -m 0700 /var/lib/sparkle-worker

WORKDIR /opt/sparkle
COPY src/sparkle ./sparkle

USER 10001:10001
EXPOSE 8770
ENTRYPOINT ["python3", "-m", "sparkle.worker_service"]
