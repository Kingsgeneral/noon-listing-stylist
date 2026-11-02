"""模型供应商配置加载。API Key 只从环境变量读取，不落盘。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
EXAMPLE_PATH = CONFIG_DIR / "providers.example.yaml"


@dataclass
class ProviderConfig:
    name: str
    type: str
    label: str = ""
    model: str | None = None
    base_url: str | None = None
    api_key_env: str | None = None
    supports_edit: bool = True
    supports_generate: bool = True
    extra: dict = field(default_factory=dict)

    @property
    def api_key(self) -> str | None:
        if not self.api_key_env:
            return None
        return os.environ.get(self.api_key_env)

    @property
    def has_credentials(self) -> bool:
        if self.type == "mock":
            return True
        return bool(self.api_key)


@dataclass
class AppConfig:
    default_provider: str
    providers: dict[str, ProviderConfig]
    source: Path
    using_example: bool = False

    def get(self, name: str | None = None) -> ProviderConfig:
        key = name or self.default_provider
        if key not in self.providers:
            available = ", ".join(sorted(self.providers))
            raise KeyError(f"未知模型供应商 {key!r}，可用：{available}")
        return self.providers[key]


def load_config(path: str | Path | None = None) -> AppConfig:
    env_path = os.environ.get("NOON_STYLIST_CONFIG")
    candidate = Path(path) if path else (Path(env_path) if env_path else CONFIG_DIR / "providers.yaml")
    using_example = False
    if not candidate.exists():
        candidate = EXAMPLE_PATH
        using_example = True
    raw = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
    providers: dict[str, ProviderConfig] = {}
    for name, item in (raw.get("providers") or {}).items():
        item = item or {}
        supports = item.get("supports") or {}
        providers[name] = ProviderConfig(
            name=name,
            type=item.get("type", "mock"),
            label=item.get("label", name),
            model=item.get("model"),
            base_url=item.get("base_url"),
            api_key_env=item.get("api_key_env"),
            supports_edit=bool(supports.get("edit", True)),
            supports_generate=bool(supports.get("generate", True)),
            extra={k: v for k, v in item.items() if k not in {"type", "label", "model", "base_url", "api_key_env", "supports"}},
        )
    if not providers:
        raise ValueError(f"配置文件 {candidate} 里没有任何 providers")
    default = raw.get("default_provider") or next(iter(providers))
    return AppConfig(default_provider=default, providers=providers, source=candidate, using_example=using_example)
