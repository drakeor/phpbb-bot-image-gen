# Plan

Scope agreed in discussion. Nothing here is implemented yet.

## 1. Combine two files

`app/model_contract.py` and `app/model_select.py` become a single file, name chosen at implementation time. It holds the `ImageModel` contract and the alias registry together.

Imports updated in `app/api.py`, `app/prefetch.py`, and the test module that references the registry.

The name avoids `app/models.py`, because Python resolves `app.models` to the existing `app/models/` package directory and a module file of that name beside it would never be imported.

## 2. Rename the entrypoint module

`app/server.py` becomes `app/main.py`.

One other reference changes: the `python -m app.server` string in `scripts/service-entrypoint.sh`. The Dockerfile `CMD` points at that script, not at the module, so it needs no edit.

## 3. Audit fixes

### Top three

- **Bound the request parameters.** `n`, `width`, `height`, `steps` and `guidance_scale` currently have no ceiling. A single request can ask for hundreds of images or an 8192-pixel canvas.
- **Move generation off the event loop.** The endpoint is `async` and calls the pipeline inline, so a multi-second blocking CUDA call sits on the asyncio loop and freezes `/health` and every other request. Generation moves into a threadpool, behind a single lock so one runs at a time.
- **Move settings out of module-import scope.** `app/api.py` calls `Settings.from_env()` at module level, so importing the module without `SD_API_KEY` raises. It moves into the lifespan handler. The test module's `importlib.reload` workaround goes away with it.

### Item 1 — prefetch

`snapshot_download` fetches every file in a repo, including `.bin` duplicates of the safetensors, standalone single-file checkpoints, and fp32 weights alongside the fp16 variant that `start()` actually loads.

Prefetch changes to download exactly the file set `start()` loads, using the same `variant` and `use_safetensors` arguments, and writes to the correct hub cache directory instead of passing `HF_HOME` itself as `cache_dir`.

### Item 4 — GPU allocation failure

`generate` catches the allocation failure, releases cached device memory, and the endpoint returns 503 rather than leaving the process wedged with a fragmented allocator.

### Item 6 — logging

None exists today. Added: model load with elapsed time, per-request duration and dimensions, and failures.

### Item 7 — entrypoint

`scripts/service-entrypoint.sh` currently traps TERM and INT and ignores them, so `docker stop` waits the full grace period then SIGKILLs. It also restarts every 10 seconds forever with no backoff and no ceiling, including for a bad `SD_MODEL` that will never start.

Changes: forward TERM and INT to the child process and exit, back off exponentially between restarts, and stop retrying on a configuration error.

### Item 9 — four one-liners

- `SD_DEVICE` defaults to `cuda` and appears nowhere in the README.
- A bad `SD_PORT` raises a `ValueError` naming neither the variable nor the value.
- The README documents `"created": 0` while the code returns a real timestamp.
- The FLUX path calls `enable_model_cpu_offload()` on every cuda device, costing seconds per image on a card where the model fits in VRAM. It becomes conditional on available VRAM.

### Not being fixed

- Item 2 — torch absent from `requirements.txt`.
- Item 3 — no version pins.
- Item 5 — exception text returned to the caller.
- Item 8 — API key compared with `!=` rather than a constant-time comparison.

## 4. Git

`git init` in this folder. `.gitignore` line 4 already covers `.venv/`.

Verified this session: `gh` at `/usr/bin/gh`, version 2.98.0, authenticated as `drakeor` over ssh. Token scopes are `admin:public_key`, `gist`, `read:org`, `repo`.

`write:packages` is absent from those scopes. That only matters for pushing an image to GHCR from this box; a GitHub Actions workflow uses its own `GITHUB_TOKEN` and does not depend on the local scopes.

## 5. GHCR

A GitHub Actions workflow builds the default image on push and on tags and pushes it to `ghcr.io/drakeor/<repo>`.

The default build is `BAKE_MODEL=0` — base image, requirements, application code, with the model downloaded when the container starts. The Dockerfile already carries the `BAKE_MODEL` switch and the gated prefetch block, and the README already documents both builds.

`SD_MODEL` is read at runtime, so one image serves all three aliases. Tags: `:latest` plus the commit sha.

The package is set public so vast.ai pulls with no registry credentials in the instance config.

Baked-model images are built locally and pushed by hand when wanted. They are not part of the Actions workflow.

## 6. Verification

1. Run the pytest suite.
2. Start the service with `SD_MODEL=ssd-1b` on the local RTX 3090.
3. POST a generation request and decode the returned base64 to confirm it is a PNG.

Local box, verified this session: RTX 3090, 24 GB VRAM, driver 595.91.07, 48 GB free RAM, 139 GB free disk. `segmind/SSD-1B` is the smallest of the three aliases at roughly 4.5 GB in fp16.

## Out of scope

**Issue 5 — the box becoming unresponsive on vast.ai and requiring a hard reboot.** Discussed and set aside. Ideas raised, none adopted: a memory ceiling on the model process via cgroup `memory.high`, a threshold watchdog (`earlyoom` / `nohang`), a pinned high-priority escape process, flattening the peak during model load, an fsync'd sampler plus persistent journald so a freeze leaves evidence behind, and deliberate reproduction on a cheap instance.

## Open decisions

- The repository name.
- Whether `HF_HOME` moves off `/models/huggingface`.
