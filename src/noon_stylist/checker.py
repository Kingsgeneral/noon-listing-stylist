"""主图合规校验：把 Noon 规则变成可断言的检查项。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .knowledge import KnowledgeBase, load_knowledge

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


@dataclass
class Finding:
    code: str
    level: str  # error / warn / info
    message: str
    fix: str = ""

    def to_dict(self) -> dict:
        return {"code": self.code, "level": self.level, "message": self.message, "fix": self.fix}


@dataclass
class Report:
    path: str
    size: tuple[int, int]
    findings: list[Finding] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not any(f.level == "error" for f in self.findings)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "warn"]

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "size": list(self.size),
            "passed": self.passed,
            "findings": [f.to_dict() for f in self.findings],
            "metrics": self.metrics,
        }


def _near_white_ratio(arr, threshold: int) -> float:
    mask = (arr[:, :, 0] >= threshold) & (arr[:, :, 1] >= threshold) & (arr[:, :, 2] >= threshold)
    return float(mask.mean())


def _product_bbox(arr, bg_threshold: int) -> tuple[int, int, int, int] | None:
    diff = np.abs(arr.astype("int16") - bg_threshold).max(axis=2)
    mask = diff > 18  # 与白底的明显差异
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def check_main_image(path: str | Path, kb: KnowledgeBase | None = None) -> Report:
    if np is None:
        raise RuntimeError("检查主图需要 numpy，请先 pip install numpy")

    kb = kb or load_knowledge()
    spec = (kb.rules.get("main_image") or {})
    size_spec = spec.get("size") or {}
    shape_spec = spec.get("shape") or {}
    bg_spec = spec.get("background") or {}
    comp_spec = spec.get("composition") or {}

    img_path = Path(path)
    with Image.open(img_path) as opened:
        img = opened.convert("RGB")
        fmt = (opened.format or "").lower()
    w, h = img.size
    arr = np.asarray(img)
    report = Report(path=str(img_path), size=(w, h))

    # 尺寸
    min_side = int(size_spec.get("min_side_px", 1000))
    if min(w, h) < min_side:
        report.findings.append(
            Finding(
                code="SIZE_TOO_SMALL",
                level="error",
                message=f"短边 {min(w, h)}px 低于 Noon 最小要求 {min_side}px",
                fix=f"放大到短边至少 {size_spec.get('recommended_side_px', 1500)}px",
            )
        )
    else:
        report.findings.append(Finding(code="SIZE_OK", level="info", message=f"尺寸合规：{w}x{h}"))

    # 比例
    tolerance = float(shape_spec.get("tolerance", 0.02))
    ratio = w / h
    if abs(ratio - 1.0) > tolerance:
        report.findings.append(
            Finding(
                code="ASPECT_NOT_SQUARE",
                level="error",
                message=f"宽高比 {ratio:.3f} 不是 1:1（容忍 ±{tolerance:.0%}）",
                fix="主图按 1:1 裁切或补齐留白",
            )
        )
    report.metrics["aspect_ratio"] = round(ratio, 4)

    # 白底：只统计商品以外区域，避免"商品占比大"与"白底占比高"互相矛盾
    threshold = int(bg_spec.get("min_channel_value", 248))
    white_ratio = _near_white_ratio(arr, threshold)
    report.metrics["white_ratio"] = round(white_ratio, 4)

    deviation = np.abs(arr.astype("int16") - threshold).max(axis=2)
    product_mask = deviation > 18
    background_mask = ~product_mask
    if background_mask.sum() == 0:
        report.findings.append(
            Finding(code="NO_BACKGROUND", level="error", message="画面被主体填满，没有留白", fix="四周留白至少 3%")
        )
        report.findings.append(
            Finding(
                code="BACKGROUND_NOT_WHITE",
                level="error",
                message="商品以外区域几乎不存在近白像素（背景为彩色或满幅图形）",
                fix="去背景后补纯白底（RGB 255,255,255）",
            )
        )
        background_white = 0.0
        background_empty = True
    else:
        bg_pixels = arr[background_mask]
        background_white = float((bg_pixels >= threshold).all(axis=1).mean())
        background_empty = False
    report.metrics["background_white_ratio"] = round(background_white, 4)

    min_white = float(bg_spec.get("background_white_ratio_min", bg_spec.get("min_white_ratio", 0.92)))
    if not background_empty and background_white < min_white:
        report.findings.append(
            Finding(
                code="BACKGROUND_NOT_WHITE",
                level="error",
                message=f"商品以外区域近白占比 {background_white:.1%}，低于要求 {min_white:.0%}",
                fix="去背景后补纯白底（RGB 255,255,255）",
            )
        )

    # 主体占比与居中
    bbox = _product_bbox(arr, threshold)
    if bbox is None:
        report.findings.append(
            Finding(code="NO_PRODUCT_DETECTED", level="warn", message="未检测到明显主体，画面可能全白")
        )
    if bbox:
        x0, y0, x1, y1 = bbox
        bbox_ratio = ((x1 - x0 + 1) * (y1 - y0 + 1)) / float(w * h)
        report.metrics["product_bbox_ratio"] = round(bbox_ratio, 4)
        lo = float(comp_spec.get("product_bbox_ratio_min", 0.55))
        hi = float(comp_spec.get("product_bbox_ratio_max", 0.95))
        if bbox_ratio < lo:
            report.findings.append(
                Finding(
                    code="PRODUCT_TOO_SMALL",
                    level="warn",
                    message=f"商品占画面 {bbox_ratio:.1%}，低于建议下限 {lo:.0%}",
                    fix="裁切留白，让商品更饱满",
                )
            )
        elif bbox_ratio > hi:
            report.findings.append(
                Finding(
                    code="PRODUCT_TOO_LARGE",
                    level="warn",
                    message=f"商品占画面 {bbox_ratio:.1%}，超出建议上限 {hi:.0%}",
                    fix="四周增加留白，避免贴边",
                )
            )
        cx = (x0 + x1) / 2 / w
        cy = (y0 + y1) / 2 / h
        offset = max(abs(cx - 0.5), abs(cy - 0.5))
        report.metrics["center_offset"] = round(offset, 4)
        tol = float(comp_spec.get("centered_tolerance", 0.08))
        if offset > tol:
            report.findings.append(
                Finding(
                    code="NOT_CENTERED",
                    level="warn",
                    message=f"商品中心偏离画面中心 {offset:.1%}",
                    fix="重新居中构图",
                )
            )
        margin_min = float(comp_spec.get("margin_min_ratio", 0.03))
        edge_margin = min(x0, y0, w - 1 - x1, h - 1 - y1) / float(min(w, h))
        report.metrics["min_margin_ratio"] = round(edge_margin, 4)
        if edge_margin < margin_min:
            report.findings.append(
                Finding(
                    code="EDGE_TIGHT",
                    level="warn",
                    message=f"商品贴边（最小留白 {edge_margin:.1%}）",
                    fix="四周留出至少 3% 安全边距",
                )
            )

    # 边框检测：外圈 1.5% 环带若明显非白，多半是加了边框
    ring = int(max(2, min(w, h) * 0.015))
    border_pixels = np.concatenate(
        [
            arr[:ring, :, :].reshape(-1, 3),
            arr[-ring:, :, :].reshape(-1, 3),
            arr[:, :ring, :].reshape(-1, 3),
            arr[:, -ring:, :].reshape(-1, 3),
        ]
    )
    border_white = float((border_pixels >= threshold).all(axis=1).mean())
    report.metrics["border_white_ratio"] = round(border_white, 4)
    if border_white < 0.85:
        report.findings.append(
            Finding(
                code="BORDER_OR_FRAME",
                level="warn",
                message=f"画面外圈近白比例 {border_white:.1%}，疑似有边框或色块",
                fix="去掉边框/装饰边，保持纯白底",
            )
        )

    # 四角纯色检测：能抓住"米色/灰色影棚背景"这类主体化误判
    corner_size = max(4, int(min(w, h) * 0.04))
    corners = [
        arr[:corner_size, :corner_size],
        arr[:corner_size, -corner_size:],
        arr[-corner_size:, :corner_size],
        arr[-corner_size:, -corner_size:],
    ]
    corner_means = [patch.reshape(-1, 3).mean(axis=0) for patch in corners]
    corner_stds = [float(patch.reshape(-1, 3).std(axis=0).max()) for patch in corners]
    uniform_corners = all(std < 8 for std in corner_stds)
    corner_rgb = [int(v) for v in np.mean(corner_means, axis=0)]
    report.metrics["corner_rgb"] = corner_rgb
    report.metrics["corner_uniform"] = bool(uniform_corners)
    if uniform_corners and min(corner_rgb) < threshold:
        report.findings.append(
            Finding(
                code="COLORED_BACKGROUND",
                level="error",
                message=f"四角为纯色非白背景 RGB{tuple(corner_rgb)}",
                fix="用抠图/蒙版把背景换成纯白，不要直接留影棚底色",
            )
        )

    # 格式
    allowed = {f.lower() for f in size_spec.get("allowed_formats", ["jpg", "jpeg", "png"])}
    if fmt and fmt not in allowed:
        report.findings.append(
            Finding(code="FORMAT_UNSUPPORTED", level="warn", message=f"格式 {fmt} 不在允许列表 {sorted(allowed)}")
        )

    return report
