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

## Output variation

A request that omits `width` and `height` draws a size per image from the active
model's `size_buckets`. The draw picks an orientation by weight, then an entry
inside that orientation uniformly. A request carrying either dimension passes
through at the size it names.

After generation the image passes a crop gate and five filter gates, each an
independent draw:

- `SD_VARIATION_ENABLED`: set `false` to return every image at the model default size with no filters, default `true`
- `SD_SIZE_WEIGHT_WIDE`: orientation weight for wide entries, default `0.55`
- `SD_SIZE_WEIGHT_TALL`: orientation weight for tall entries, default `0.35`
- `SD_SIZE_WEIGHT_SQUARE`: orientation weight for square entries, default `0.10`
- `SD_P_STANDARD_SIZE`: chance of cropping to an exact conventional ratio and downscaling to a standard size such as `1280x720` or `1024x768`, default `0.50`
- `SD_P_RANDOM_CROP`: chance of taking the crop window off-center, default `0.35`
- `SD_P_NOISE`: chance of gaussian noise at sigma 1 to 3, default `0.03`
- `SD_P_BLUR`: chance of gaussian blur at radius 0.3 to 0.8, default `0.03`
- `SD_P_CONTRAST`: chance of a 5 to 15 percent contrast reduction, default `0.08`
- `SD_P_PIXELATE`: chance of a pixelation pass at factor 2 to 4, default `0.02`
- `SD_P_JPEG`: chance of a JPEG re-encode at quality 75 to 90, default `0.30`

At these defaults 59 percent of images carry no filter, 36 percent carry one,
and 5 percent carry two or more. The response body stays PNG in every case; the
JPEG gate applies its compression artifacts and decodes back before encoding.

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
