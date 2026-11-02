"""流水线编排：主图规范化 / 场景图生成 / 详情图排版。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from .compose import DetailSpec, compose_detail_page
from .knowledge import KnowledgeBase, load_knowledge
from .models.base import ImageModel, MockImageModel

MAIN_PROMPT = (
    "Recompose this product photo as a strict Noon main image: pure white seamless background "
    "(RGB 255,255,255), product centered and fully visible with 3-6 percent margin, "
    "soft contact shadow, no text, no watermark, no logo overlay, no border, no props, "
    "keep the product shape, color, logo and material exactly unchanged, square 1:1 composition."
)


def _trim_uniform_border(img: Image.Image, tolerance: int = 14, margin_ratio: float = 0.01) -> Image.Image:
    """裁掉四角一致的纯色背景（常见于影棚米色/灰色底），无需抠图模型。"""
    import numpy as np

    rgb = img.convert("RGB")
    arr = np.asarray(rgb).astype("int16")
    h, w, _ = arr.shape
    c = max(4, int(min(h, w) * 0.03))
    corners = [arr[:c, :c], arr[:c, -c:], arr[-c:, :c], arr[-c:, -c:]]
    means = [patch.reshape(-1, 3).mean(axis=0) for patch in corners]
    stds = [float(patch.reshape(-1, 3).std(axis=0).max()) for patch in corners]
    bg = np.mean(means, axis=0)
    if max(stds) >= 8 or min(bg) >= 248:
        return img  # 四角不是纯色，或本身已是白底

    diff = np.abs(arr - bg).max(axis=2)
    ys, xs = np.where(diff > tolerance)
    if len(xs) == 0:
        return img
    m = max(1, int(min(w, h) * margin_ratio))
    box = (
        max(0, int(xs.min()) - m),
        max(0, int(ys.min()) - m),
        min(w, int(xs.max()) + 1 + m),
        min(h, int(ys.max()) + 1 + m),
    )
    return img.crop(box)


def local_normalize_main(
    image_path: str | Path,
    out_path: str | Path,
    side: int = 1500,
    trim_border: bool = True,
) -> Path:
    """不依赖任何模型的主图规范化：去纯色底、去透明、补白底、居中、补成正方形。"""
    img = Image.open(image_path)
    if trim_border:
        img = _trim_uniform_border(img)
    img = img.convert("RGBA")
    canvas = Image.new("RGB", img.size, "white")
    canvas.paste(img, mask=img.split()[-1])

    w, h = canvas.size
    edge = max(w, h)
    square = Image.new("RGB", (edge, edge), "white")
    square.paste(canvas, ((edge - w) // 2, (edge - h) // 2))

    # 商品四周留 4% 安全边距
    inner = int(edge * 0.92)
    square = square.resize((inner, inner), Image.LANCZOS)
    final = Image.new("RGB", (edge, edge), "white")
    final.paste(square, ((edge - inner) // 2, (edge - inner) // 2))
    final = final.resize((side, side), Image.LANCZOS)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    final.save(out, quality=95)
    return out


def generate_main(
    image_path: str | Path,
    out_path: str | Path,
    model: ImageModel | None = None,
    extra_prompt: str = "",
    keep_original: bool = False,
) -> Path:
    """主图生成。给了模型走图生图，不给模型走本地规范化。"""
    target = Path(out_path)
    if model is None or isinstance(model, MockImageModel):
        if keep_original:
            target.parent.mkdir(parents=True, exist_ok=True)
            Image.open(image_path).convert("RGB").save(target, quality=95)
            return target
        return local_normalize_main(image_path, target)

    prompt = MAIN_PROMPT if not extra_prompt else f"{MAIN_PROMPT} {extra_prompt.strip()}"
    data = model.edit_file(image_path, prompt, size="1024x1024")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def generate_scene(
    image_path: str | Path,
    out_path: str | Path,
    scene: str,
    model: ImageModel,
    palette: str | None = None,
    occasion: str | None = None,
    kb: KnowledgeBase | None = None,
    extra_prompt: str = "",
) -> tuple[Path, str]:
    """按场景与色板生成生活方式图，返回（输出路径, 使用的提示词）。"""
    kb = kb or load_knowledge()
    prompt = kb.build_scene_prompt(scene, palette_name=palette, occasion=occasion, extra=extra_prompt)
    data = model.edit_file(image_path, prompt, size="1024x1024")
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target, prompt


def compose_detail(spec: dict, out_path: str | Path, kb: KnowledgeBase | None = None) -> Path:
    kb = kb or load_knowledge()
    return compose_detail_page(DetailSpec.from_dict(spec), out_path, kb=kb)
