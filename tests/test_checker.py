from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from noon_stylist.checker import check_main_image
from noon_stylist.knowledge import load_knowledge
from noon_stylist.pipeline import local_normalize_main


def _make_product_image(path: Path, size=(1500, 1500), bg="white", box=(160, 160, 1340, 1340)):
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    draw.rectangle(box, fill="#4A6FA5")
    img.save(path)
    return path


def test_compliant_main_image_passes(tmp_path):
    path = _make_product_image(tmp_path / "ok.png")
    report = check_main_image(path)
    assert report.passed, report.to_dict()
    assert report.metrics["background_white_ratio"] > 0.9
    assert 0.5 < report.metrics["product_bbox_ratio"] < 0.95


def test_small_image_is_rejected(tmp_path):
    path = _make_product_image(tmp_path / "small.png", size=(600, 600), box=(200, 200, 400, 400))
    report = check_main_image(path)
    codes = {f.code for f in report.findings}
    assert not report.passed
    assert "SIZE_TOO_SMALL" in codes


def test_colored_background_is_rejected(tmp_path):
    path = _make_product_image(tmp_path / "colored.png", bg="#D9C7A7")
    report = check_main_image(path)
    codes = {f.code for f in report.findings}
    assert not report.passed
    assert "BACKGROUND_NOT_WHITE" in codes


def test_non_square_is_rejected(tmp_path):
    path = _make_product_image(tmp_path / "rect.png", size=(1500, 1200), box=(500, 400, 1000, 800))
    report = check_main_image(path)
    codes = {f.code for f in report.findings}
    assert "ASPECT_NOT_SQUARE" in codes


def test_local_normalize_outputs_square_white(tmp_path):
    src = Image.new("RGBA", (800, 600), (0, 0, 0, 0))
    draw = ImageDraw.Draw(src)
    draw.ellipse((200, 150, 600, 450), fill=(180, 60, 60, 255))
    src_path = tmp_path / "rgba.png"
    src.save(src_path)

    out = local_normalize_main(src_path, tmp_path / "normalized.png", side=1200)
    img = Image.open(out).convert("RGB")
    assert img.size == (1200, 1200)
    assert img.getpixel((5, 5))[0] > 245
    report = check_main_image(out)
    assert not any(f.code == "SIZE_TOO_SMALL" for f in report.findings)


def test_knowledge_prompt_includes_redlines():
    kb = load_knowledge()
    prompt = kb.build_scene_prompt("majlis_living", palette_name="royal_gold", occasion="ramadan")
    assert "majlis" in prompt.lower()
    assert "no alcohol" in prompt.lower()
    assert "palette" in prompt.lower()
    assert kb.scene_names()
    assert kb.palette_names()
