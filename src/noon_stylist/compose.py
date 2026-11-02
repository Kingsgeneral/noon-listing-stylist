"""详情图排版引擎。

关键设计：阿拉伯文字绝不交给图像模型生成（连写与 RTL 极易出错），
而是用真实字体 + 版式渲染，模型只负责底图与商品图。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .knowledge import KnowledgeBase, load_knowledge

FONT_CANDIDATES_AR = [
    "C:/Windows/Fonts/tahoma.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT_CANDIDATES_LATIN = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

DEFAULT_PALETTE = {"bg": "#0B1B33", "accent": "#C9A227", "surface": "#F7F5EF", "ink": "#1B1B1B"}


@dataclass
class DetailSpec:
    title_ar: str
    title_en: str = ""
    product_image: str | None = None
    bullets: list[dict] = field(default_factory=list)  # [{"ar": "...", "en": "..."}]
    badge: str = ""
    palette: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "DetailSpec":
        return cls(
            title_ar=data.get("title_ar", ""),
            title_en=data.get("title_en", ""),
            product_image=data.get("product_image"),
            bullets=data.get("bullets") or [],
            badge=data.get("badge", ""),
            palette=data.get("palette"),
        )


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _shape_arabic(text: str) -> str:
    """做阿拉伯语连写整形与 RTL 重排；缺依赖时原样返回。"""
    if not text:
        return text
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display

        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _resolve_palette(kb: KnowledgeBase | None, name: str | None) -> dict:
    palette = dict(DEFAULT_PALETTE)
    if not kb or not name:
        return palette
    spec = kb.palette(name)
    colors = spec.get("colors") or []
    keys = ["bg", "accent", "surface", "ink"]
    for key, value in zip(keys, colors):
        palette[key] = value
    return palette


def _fit_image(path: Path, box_w: int, box_h: int) -> Image.Image:
    img = Image.open(path).convert("RGB")
    ratio = min(box_w / img.width, box_h / img.height)
    new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
    return img.resize(new_size, Image.LANCZOS)


def compose_detail_page(
    spec: DetailSpec,
    out_path: str | Path,
    kb: KnowledgeBase | None = None,
    width: int = 1200,
) -> Path:
    kb = kb or load_knowledge()
    palette = _resolve_palette(kb, spec.palette)
    margin = 80
    header_h = 300
    bullets = spec.bullets or []
    bullet_h = 110
    footer_h = 110 if spec.badge else 0

    product_block_h = 820 if spec.product_image else 0
    height = header_h + product_block_h + bullet_h * len(bullets) + footer_h + 120

    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)

    # 头部色块
    draw.rectangle([0, 0, width, header_h], fill=palette["bg"])
    draw.rectangle([0, header_h - 8, width, header_h], fill=palette["accent"])

    f_ar_title = _load_font(FONT_CANDIDATES_AR, 52)
    f_en_title = _load_font(FONT_CANDIDATES_LATIN, 26)
    ar_title = _shape_arabic(spec.title_ar)
    if ar_title:
        draw.text((width - margin, 90), ar_title, font=f_ar_title, fill="white", anchor="ra")
    if spec.title_en:
        draw.text((margin, 96), spec.title_en, font=f_en_title, fill="#D9D9D9", anchor="la")
        draw.line([margin, 140, margin + 60, 140], fill=palette["accent"], width=4)

    y = header_h + 40

    # 商品图区
    if spec.product_image:
        try:
            product = _fit_image(Path(spec.product_image), width - margin * 2, product_block_h - 80)
            canvas.paste(product, ((width - product.width) // 2, y + (product_block_h - 80 - product.height) // 2))
        except FileNotFoundError:
            draw.text((width // 2, y + 100), "product image not found", font=f_en_title, fill="#999999", anchor="ma")
        y += product_block_h

    # 卖点区
    f_ar_bullet = _load_font(FONT_CANDIDATES_AR, 34)
    f_en_bullet = _load_font(FONT_CANDIDATES_LATIN, 20)
    for item in bullets:
        ar = _shape_arabic(item.get("ar", ""))
        en = item.get("en", "")
        draw.ellipse([width - margin - 14, y + 26, width - margin, y + 40], fill=palette["accent"])
        if ar:
            draw.text((width - margin - 28, y + 8), ar, font=f_ar_bullet, fill=palette["ink"], anchor="ra")
        if en:
            draw.text((margin, y + 52), en, font=f_en_bullet, fill="#777777", anchor="la")
        y += bullet_h

    # 底部署名/信任条
    if spec.badge:
        draw.rectangle([0, height - footer_h, width, height], fill=palette["surface"])
        f_badge = _load_font(FONT_CANDIDATES_LATIN, 24)
        draw.text((width // 2, height - footer_h // 2), spec.badge, font=f_badge, fill=palette["ink"], anchor="mm")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, quality=92)
    return out
