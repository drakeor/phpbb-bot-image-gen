# phpBB Image Service

FastAPI image service for the existing phpBB bot contract.

## API

- `POST /v1/images/generations`
- Header: `x-api-key: $SD_API_KEY`
- Body fields: `prompt`, `negative_prompt`, `n`, `width`, `height`, `guidance_scale`, `steps`, `model`
- Response: `{ "created": 1700000000, "data": [{ "b64_json": "..." }] }`
- `GET /health` returns `{ "ok": true }`

The request `model` field is accepted for client compatibility. Runtime model choice comes only from `SD_MODEL`.

## Config

- `SD_MODEL`: `sd35-large`, `ssd-1b`, or `flux-schnell`
- `SD_API_KEY`: API key required by `x-api-key`
- `SD_HOST`: default `0.0.0.0`
- `SD_PORT`: default `8005`
- `SD_DEVICE`: default `cuda`
- `HF_TOKEN`: Hugging Face token for gated or private repos
- `HF_HOME`: default `/models/huggingface`
- `SD_FORCE_DOWNLOAD`: set `true` to refresh Hugging Face files
- `SD_LOCAL_FILES_ONLY`: set `true` to use only files already in `HF_HOME`
- `SD_RESTART_DELAY_SECONDS`: delay before restarting the API process, default `10`

## Docker

Generic image:

```bash
docker build -t phpbb-image-service .
docker run --gpus all -p 8005:8005 \
  -e SD_API_KEY="$SD_API_KEY" \
  -e SD_MODEL=sd35-large \
  -e HF_TOKEN="$HF_TOKEN" \
  phpbb-image-service
```

Baked model image:

```bash
DOCKER_BUILDKIT=1 docker build -t phpbb-image-service:sd35-large \
  --build-arg BAKE_MODEL=1 \
  --build-arg SD_MODEL=sd35-large \
  --secret id=hf_token,env=HF_TOKEN \
  .
```

Runtime can still receive `HF_TOKEN`, `SD_FORCE_DOWNLOAD=true`, and `SD_LOCAL_FILES_ONLY=false` for repair or troubleshooting.
