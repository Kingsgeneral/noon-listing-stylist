"""OpenAI 兼容风格图像接口（GPT Image 2 / Qwen Image Edit / Seedream 兼容模式等）。"""

from __future__ import annotations

import base64
import io

import requests

from .base import ImageModel


class OpenAIImageModel(ImageModel):
    def __init__(self, config):
        super().__init__(config)
        self.name = config.name
        if not config.base_url:
            raise ValueError(f"{config.name} 缺少 base_url")
        self.base_url = config.base_url.rstrip("/")
        self.model = config.model or "gpt-image-2"

    def _headers(self) -> dict:
        if not self.config.api_key:
            raise RuntimeError(
                f"{self.name} 缺少 API Key，请设置环境变量 {self.config.api_key_env}"
            )
        return {"Authorization": f"Bearer {self.config.api_key}"}

    def generate(self, prompt: str, size: str = "1024x1024") -> bytes:
        resp = requests.post(
            f"{self.base_url}/images/generations",
            headers=self._headers(),
            json={"model": self.model, "prompt": prompt, "size": size, "n": 1},
            timeout=180,
        )
        return self._extract(resp)

    def edit(self, image: bytes, prompt: str, size: str = "1024x1024") -> bytes:
        resp = requests.post(
            f"{self.base_url}/images/edits",
            headers=self._headers(),
            data={"model": self.model, "prompt": prompt, "size": size, "n": 1},
            files={"image": ("product.png", image, "image/png")},
            timeout=240,
        )
        return self._extract(resp)

    @staticmethod
    def _extract(resp: requests.Response) -> bytes:
        if resp.status_code >= 400:
            raise RuntimeError(f"图像接口返回 {resp.status_code}: {resp.text[:400]}")
        payload = resp.json()
        items = payload.get("data") or []
        if not items:
            raise RuntimeError(f"图像接口返回空结果: {str(payload)[:400]}")
        item = items[0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])
        if item.get("url"):
            img_resp = requests.get(item["url"], timeout=120)
            img_resp.raise_for_status()
            return img_resp.content
        raise RuntimeError("图像接口返回中没有 b64_json 或 url")


def _noop():  # 兼容某些供应商返回的图片流校验
    return io.BytesIO()
