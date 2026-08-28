from __future__ import annotations

import concurrent.futures
import time
from fastapi.testclient import TestClient
from PIL import Image

from app import api


class FakeModel:
    alias = "fake"
    model_id = "fake/model"

    def __init__(self) -> None:
        self.started = False
        self.prompts: list[str] = []
        self.delay: float = 0.0
        self.raise_oom: bool = False

    def prefetch(self, settings) -> None:
        pass

    def start(self, settings) -> None:
        self.started = True

    def generate(self, req):
        if self.raise_oom:
            import torch

            raise torch.cuda.OutOfMemoryError("CUDA out of memory in test")
        if self.delay > 0:
            time.sleep(self.delay)
        self.prompts.append(req.prompt)
        return Image.new("RGB", (8, 8), "red")

    def stop(self) -> None:
        self.started = False


def _client(monkeypatch, api_key: str = "secret"):
    monkeypatch.setenv("SD_API_KEY", api_key)
    fake = FakeModel()
    monkeypatch.setattr(api, "create_model", lambda alias: fake)
    return TestClient(api.app), fake


def test_import_without_api_key_does_not_raise(monkeypatch):
    monkeypatch.delenv("SD_API_KEY", raising=False)
    import app.api as test_api

    assert test_api.app is not None


def test_health_is_plain_ok(monkeypatch):
    client, _ = _client(monkeypatch)
    with client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_rejects_missing_or_wrong_api_key(monkeypatch):
    client, _ = _client(monkeypatch)
    with client:
        missing = client.post("/v1/images/generations", json={"prompt": "test"})
        wrong = client.post(
            "/v1/images/generations",
            headers={"x-api-key": "bad"},
            json={"prompt": "test"},
        )
    assert missing.status_code == 403
    assert wrong.status_code == 403


def test_phpbb_generation_contract(monkeypatch):
    client, fake = _client(monkeypatch)
    payload = {
        "prompt": "a test image",
        "negative_prompt": None,
        "n": 2,
        "width": 1024,
        "height": 1024,
        "guidance_scale": 7.5,
        "steps": 30,
        "model": "ignored",
    }
    with client:
        response = client.post(
            "/v1/images/generations",
            headers={"x-api-key": "secret"},
            json=payload,
        )
    body = response.json()
    assert response.status_code == 200
    assert isinstance(body["created"], int)
    assert len(body["data"]) == 2
    assert body["data"][0]["b64_json"]
    assert fake.prompts == ["a test image", "a test image"]


def test_request_parameter_bounds(monkeypatch):
    client, _ = _client(monkeypatch)
    with client:
        # n too high
        r1 = client.post(
            "/v1/images/generations",
            headers={"x-api-key": "secret"},
            json={"prompt": "test", "n": 20},
        )
        assert r1.status_code == 422

        # n too low
        r2 = client.post(
            "/v1/images/generations",
            headers={"x-api-key": "secret"},
            json={"prompt": "test", "n": 0},
        )
        assert r2.status_code == 422

        # width too large
        r3 = client.post(
            "/v1/images/generations",
            headers={"x-api-key": "secret"},
            json={"prompt": "test", "width": 8192},
        )
        assert r3.status_code == 422

        # height too small
        r4 = client.post(
            "/v1/images/generations",
            headers={"x-api-key": "secret"},
            json={"prompt": "test", "height": 16},
        )
        assert r4.status_code == 422

        # steps too high
        r5 = client.post(
            "/v1/images/generations",
            headers={"x-api-key": "secret"},
            json={"prompt": "test", "steps": 500},
        )
        assert r5.status_code == 422

        # guidance_scale negative
        r6 = client.post(
            "/v1/images/generations",
            headers={"x-api-key": "secret"},
            json={"prompt": "test", "guidance_scale": -1.0},
        )
        assert r6.status_code == 422


def test_gpu_oom_returns_503(monkeypatch):
    client, fake = _client(monkeypatch)
    fake.raise_oom = True
    with client:
        response = client.post(
            "/v1/images/generations",
            headers={"x-api-key": "secret"},
            json={"prompt": "test"},
        )
    assert response.status_code == 503
    assert "GPU allocation failed" in response.json()["detail"]


def test_generation_does_not_block_health(monkeypatch):
    monkeypatch.setenv("SD_API_KEY", "secret")
    fake = FakeModel()
    fake.delay = 0.3
    monkeypatch.setattr(api, "create_model", lambda alias: fake)

    client = TestClient(api.app)
    with client:
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            t0 = time.perf_counter()
            f_gen = executor.submit(
                client.post,
                "/v1/images/generations",
                headers={"x-api-key": "secret"},
                json={"prompt": "slow 1"},
            )
            time.sleep(0.05)
            f_health = executor.submit(client.get, "/health")

            health_resp = f_health.result()
            health_duration = time.perf_counter() - t0
            assert health_resp.status_code == 200
            assert health_duration < 0.2, f"Health took {health_duration:.2f}s, expected < 0.2s"

            gen_resp = f_gen.result()
            assert gen_resp.status_code == 200
