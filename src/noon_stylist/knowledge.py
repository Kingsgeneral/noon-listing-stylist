"""知识层加载与提示词构建。这是本项目与通用工具的差异所在。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"


@dataclass
class KnowledgeBase:
    rules: dict
    aesthetics: dict
    redlines: dict
    root: Path

    # ---------- 查询 ----------
    def scene_names(self) -> list[str]:
        return list((self.aesthetics.get("scenes") or {}).keys())

    def palette_names(self) -> list[str]:
        return list((self.aesthetics.get("palettes") or {}).keys())

    def occasion_names(self) -> list[str]:
        return list((self.aesthetics.get("seasonal_windows") or {}).keys())

    def scene(self, name: str) -> dict:
        scenes = self.aesthetics.get("scenes") or {}
        if name not in scenes:
            raise KeyError(f"未知场景 {name!r}，可选：{', '.join(scenes)}")
        return scenes[name]

    def palette(self, name: str) -> dict:
        palettes = self.aesthetics.get("palettes") or {}
        if name not in palettes:
            raise KeyError(f"未知色板 {name!r}，可选：{', '.join(palettes)}")
        return palettes[name]

    def hard_blocks(self) -> list[dict]:
        return self.redlines.get("hard_blocks") or []

    # ---------- 提示词构建 ----------
    def build_scene_prompt(
        self,
        scene_name: str,
        palette_name: str | None = None,
        occasion: str | None = None,
        extra: str = "",
    ) -> str:
        """把场景 + 色板 + 节庆 + 红线约束拼成一条可控的生图提示词。"""
        scene = self.scene(scene_name)
        parts: list[str] = [
            "Professional e-commerce product photography.",
            scene.get("prompt", "").strip(),
            f"Product placement: {scene.get('product_placement', 'centered')}.",
            "The product must remain identical in shape, color, logo and material; do not redesign the product.",
        ]
        notes: list[str] = []
        if palette_name:
            pal = self.palette(palette_name)
            colors = ", ".join(pal.get("colors", []))
            parts.append(f"Color palette: {colors}. Mood: {pal.get('description', '')}.")
            parts.append(f"Lighting: {pal.get('lighting', 'soft studio light')}.")
            notes.extend(f"avoid {item}" for item in pal.get("avoid", []))
        if occasion:
            window = (self.aesthetics.get("seasonal_windows") or {}).get(occasion)
            if window:
                cues = ", ".join(window.get("visual_cues", []))
                parts.append(f"Occasion context: {occasion} ({cues}); keep styling restrained and tasteful.")
        comp = self.aesthetics.get("composition_priors") or {}
        if comp:
            parts.append(
                "Composition: product occupies roughly 60-80 percent of frame, "
                f"soft contact shadow ({comp.get('shadow', 'soft contact shadow')}), "
                f"color temperature {comp.get('color_temp', 'neutral')}."
            )
        blocking = [b.get("label_zh") for b in self.hard_blocks()]
        if blocking:
            notes.append("no alcohol, no pork, no religious symbols, no immodest dress, no political symbols")
        if extra.strip():
            parts.append(extra.strip())
        if notes:
            parts.append("Avoid: " + "; ".join(notes) + ".")
        return " ".join(p for p in parts if p)


def load_knowledge(root: str | Path | None = None) -> KnowledgeBase:
    base = Path(root) if root else KNOWLEDGE_DIR

    def _read(name: str) -> dict:
        path = base / name
        if not path.exists():
            raise FileNotFoundError(f"缺少知识库文件：{path}")
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    return KnowledgeBase(
        rules=_read("noon_image_rules.yaml"),
        aesthetics=_read("gulf_aesthetics.yaml"),
        redlines=_read("cultural_redlines.yaml"),
        root=base,
    )
