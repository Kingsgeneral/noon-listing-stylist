"""命令行入口：

    python -m noon_stylist.cli check data/samples/demo.png
    python -m noon_stylist.cli presets
    python -m noon_stylist.cli main <图片> --out out/main.png [--provider gpt-image-2]
    python -m noon_stylist.cli scene <图片> --scene majlis_living --palette royal_gold --out out/scene.png
    python -m noon_stylist.cli detail --spec spec.json --out out/detail.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .checker import check_main_image
from .knowledge import load_knowledge
from .models import get_model
from .pipeline import compose_detail, generate_main, generate_scene


def _cmd_check(args) -> int:
    report = check_main_image(args.image)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.passed else 1


def _cmd_presets(args) -> int:
    kb = load_knowledge()
    print("场景（scenes）:")
    for name, spec in (kb.aesthetics.get("scenes") or {}).items():
        print(f"  - {name}: {spec.get('label_zh', '')}")
    print("色板（palettes）:")
    for name, spec in (kb.aesthetics.get("palettes") or {}).items():
        print(f"  - {name}: {spec.get('description', '')}")
    print("节庆（occasions）:")
    for name in (kb.aesthetics.get("seasonal_windows") or {}):
        print(f"  - {name}")
    return 0


def _cmd_main(args) -> int:
    model = None if args.local else get_model(args.provider)
    out = generate_main(args.image, args.out, model=model, extra_prompt=args.prompt)
    print(f"主图已生成: {out}")
    return 0


def _cmd_scene(args) -> int:
    model = get_model(args.provider)
    out, prompt = generate_scene(
        args.image,
        args.out,
        scene=args.scene,
        model=model,
        palette=args.palette,
        occasion=args.occasion,
    )
    print(f"场景图已生成: {out}")
    print(f"提示词: {prompt}")
    return 0


def _cmd_detail(args) -> int:
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out = compose_detail(spec, args.out)
    print(f"详情图已生成: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="noon-stylist", description="Noon 商品图本地化工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="校验主图是否符合 Noon 规范")
    p_check.add_argument("image")
    p_check.set_defaults(func=_cmd_check)

    p_presets = sub.add_parser("presets", help="列出内置场景与色板")
    p_presets.set_defaults(func=_cmd_presets)

    p_main = sub.add_parser("main", help="生成规范主图")
    p_main.add_argument("image")
    p_main.add_argument("--out", required=True)
    p_main.add_argument("--provider", default=None)
    p_main.add_argument("--prompt", default="")
    p_main.add_argument("--local", action="store_true", help="只用本地处理，不调用模型")
    p_main.set_defaults(func=_cmd_main)

    p_scene = sub.add_parser("scene", help="生成场景图")
    p_scene.add_argument("image")
    p_scene.add_argument("--scene", required=True)
    p_scene.add_argument("--out", required=True)
    p_scene.add_argument("--palette", default=None)
    p_scene.add_argument("--occasion", default=None)
    p_scene.add_argument("--provider", default=None)
    p_scene.set_defaults(func=_cmd_scene)

    p_detail = sub.add_parser("detail", help="用排版引擎合成详情图")
    p_detail.add_argument("--spec", required=True)
    p_detail.add_argument("--out", required=True)
    p_detail.set_defaults(func=_cmd_detail)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
