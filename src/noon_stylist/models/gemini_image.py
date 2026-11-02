"""Gemini 图像接口（Nano Banana / Gemini Image）。"""

from __future__ import annotations

import base64

import requests

from .base import ImageModel


class GeminiImageModel(ImageModel):
    def __init__(self, config):
        super().__init__(config)
        self.name = config.name
        self.base_url = (config.base_url or "https://generativelanguage.googleapis.com").rstrip("/")
        self.model = config.model or "gemini-2.5-flash-image"

    def _endpoint(self) -> str:
        if not self.config.api_key:
            raise RuntimeError(
                f"{self.name} 缺少 API Key，请设置环境变量 {self.config.api_key_env}"
            )
        return f"{self.base_url}/v1beta/models/{self.model}:generateContent?key={self.config.api_key}"

    def generate(self, prompt: str, size: str = "1024x1024") -> bytes:
        return self._call([{"text": prompt}])

    def edit(self, image: bytes, prompt: str, size: str = "1024x1024") -> bytes:
        parts = [
            {"text": prompt},
            {
                "inline_data": {
                    "mime_type": "image/png",
                    "data": base64.b64encode(image).decode("ascii"),
                }
            },
        ]
        return self._call(parts)

    def _call(self, parts: list[dict]) -> bytes:
        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }
        resp = requests.post(self._endpoint(), json=body, timeout=240)
        if resp.status_code >= 400:
            raise RuntimeError(f"{self.name} 返回 {resp.status_code}: {resp.text[:400]}")
        payload = resp.json()
        candidates = payload.get("candidates") or []
        for candidate in candidates:
            for part in (candidate.get("content") or {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
        raise RuntimeError(f"{self.name} 未返回图片数据: {str(payload)[:400]}")
