"""供应商注册表：把配置里的 type 映射到具体实现。"""

from __future__ import annotations

from ..config import AppConfig, ProviderConfig, load_config
from .base import ImageModel, MockImageModel
from .gemini_image import GeminiImageModel
from .openai_image import OpenAIImageModel

_REGISTRY = {
    "mock": MockImageModel,
    "openai_image": OpenAIImageModel,
    "gemini_image": GeminiImageModel,
}


def build_model(provider: ProviderConfig) -> ImageModel:
    cls = _REGISTRY.get(provider.type)
    if cls is None:
        raise KeyError(f"未实现的供应商类型 {provider.type!r}，已支持：{', '.join(_REGISTRY)}")
    return cls(provider)


def get_model(name: str | None = None, config: AppConfig | None = None) -> ImageModel:
    cfg = config or load_config()
    return build_model(cfg.get(name))
