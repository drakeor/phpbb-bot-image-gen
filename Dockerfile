# syntax=docker/dockerfile:1.7

ARG BASE_IMAGE=vastai/pytorch:cuda-12.8.1-auto
FROM ${BASE_IMAGE}

ARG SD_MODEL=sd35-large
ARG BAKE_MODEL=0

ENV PYTHONUNBUFFERED=1 \
    PATH=/venv/main/bin:$PATH \
    APP_HOME=/opt/workspace-internal/phpbb-image-service \
    PYTHONPATH=/opt/workspace-internal/phpbb-image-service \
    HF_HOME=/models/huggingface \
    SD_HOST=0.0.0.0 \
    SD_PORT=8005 \
    SD_MODEL=${SD_MODEL} \
    SD_LOCAL_FILES_ONLY=${BAKE_MODEL} \
    SD_RESTART_DELAY_SECONDS=10

WORKDIR ${APP_HOME}

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
RUN chmod +x ${APP_HOME}/scripts/service-entrypoint.sh

RUN --mount=type=secret,id=hf_token,required=false \
    if [ "$BAKE_MODEL" = "1" ]; then \
      export HF_TOKEN="$(cat /run/secrets/hf_token 2>/dev/null || true)"; \
      SD_MODEL="$SD_MODEL" SD_LOCAL_FILES_ONLY=false python -m app.prefetch; \
    fi

EXPOSE 8005

ENTRYPOINT ["/opt/workspace-internal/phpbb-image-service/scripts/service-entrypoint.sh"]
