from pathlib import Path

from noon_stylist.compose import DetailSpec, compose_detail_page
from noon_stylist.knowledge import load_knowledge


def test_compose_detail_page_creates_image(tmp_path):
    kb = load_knowledge()
    spec = DetailSpec(
        title_ar="قهوة عربية أصيلة",
        title_en="Authentic Arabic Coffee",
        bullets=[
            {"ar": "تحميص متوسط", "en": "Medium roast"},
            {"ar": "عبوة 500 جرام", "en": "500 g pack"},
        ],
        badge="AED 39 · Free delivery",
        palette="royal_gold",
    )
    out = compose_detail_page(spec, tmp_path / "detail.png", kb=kb)
    assert Path(out).exists()
    assert Path(out).stat().st_size > 1000


def test_compose_handles_missing_product_image(tmp_path):
    spec = DetailSpec(title_ar="منتج", product_image=str(tmp_path / "missing.png"))
    out = compose_detail_page(spec, tmp_path / "detail2.png")
    assert Path(out).exists()
