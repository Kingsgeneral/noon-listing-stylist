# Noon Listing Stylist

面向 **Noon 中东市场（AE / SA / EG）** 的商品图本地化与 SKU 视觉优化工具。

输入一张商品图，输出符合 Noon 规范的主图、符合海湾审美的场景图、以及阿语优先的双语详情图，并给出可执行的整改清单。

> 与通用 AI 生图工具的区别：本项目的核心不是提示词，而是**知识层**——Noon 图片规范、海湾审美预设、文化红线清单，都是可校验、可迭代的结构化文件。

## 它解决什么问题

跨境卖家做中东市场时，商品图常见三类问题：

1. **不合规**：主图带促销角标、非纯白底、加了边框、尺寸不足——直接被降权或下架
2. **不本地**：中文促销文案、东亚审美构图、没有阿语信息、场景不符合当地居住形态
3. **不稳定**：每次让 AI 生成都靠现编提示词，同一 SKU 多张图风格漂移

本工具把这三件事拆成可复现的三步：**规范化 → 本地化 → 校验**。

## 核心特性

- **知识层驱动**：`knowledge/` 下的三个 YAML 是产品的真正资产，字段带 `verified` 标记，可与平台文档版本对齐
- **多模型可插拔**：Nano Banana（Gemini Image）、GPT Image 2、Qwen Image Edit、Seedream 等，统一接口，改配置即切换，BYOK
- **规则可断言**：主图白底比例、宽高比、商品占比、居中偏移、贴边、边框全部量化检测，输出带修复建议的整改清单
- **阿语走排版不走生图**：详情图用真实字体 + RTL 排版引擎渲染，避免图像模型生成阿语乱码
- **离线可用**：不配任何 API Key 也能做本地主图规范化、详情图排版、规范校验

## 快速开始

```bash
git clone <repo-url>
cd noon-listing-stylist
python -m pip install -r requirements.txt

# 1. 校验一张主图（不需要任何 Key）
python -m noon_stylist.cli check data/samples/demo_product.png

# 2. 本地规范化：去透明背景、补白底、居中、补成正方形
python -m noon_stylist.cli main data/samples/demo_product.png --out out/main.png --local

# 3. 详情图排版（阿语 RTL + 双语卖点）
python -m noon_stylist.cli detail --spec data/samples/detail_spec.json --out out/detail.png

# 4. 查看内置场景与色板
python -m noon_stylist.cli presets
```

使用模型生成场景图（需要 API Key）：

```bash
cp config/providers.example.yaml config/providers.yaml
export GEMINI_API_KEY=your_key          # Windows: set GEMINI_API_KEY=...
python -m noon_stylist.cli scene data/samples/demo_product.png \
  --scene majlis_living --palette royal_gold --occasion ramadan --out out/scene.png
```

## 配置模型

`config/providers.yaml` 决定用哪家模型，API Key 只从环境变量读取，绝不写入文件：

```yaml
default_provider: nano-banana
providers:
  nano-banana:
    type: gemini_image
    model: gemini-2.5-flash-image
    base_url: https://generativelanguage.googleapis.com
    api_key_env: GEMINI_API_KEY
  gpt-image-2:
    type: openai_image
    model: gpt-image-2
    base_url: https://api.openai.com/v1
    api_key_env: OPENAI_API_KEY
```

新增供应商只需实现 `ImageModel` 的两个方法（`generate` / `edit`），再到 `models/registry.py` 注册类型。

## 知识层结构

| 文件 | 作用 | 谁维护 |
|------|------|--------|
| `knowledge/noon_image_rules.yaml` | 平台硬规则：尺寸、白底、禁止元素、品类期望 | 需随平台文档更新，字段带 `verified` 标记 |
| `knowledge/gulf_aesthetics.yaml` | 海湾审美：色板、场景、节庆窗口、构图先验 | 用爆款店铺真实图片统计校准 |
| `knowledge/cultural_redlines.yaml` | 文化红线：酒精、猪肉、宗教符号、着装、手势 | 上架前必读，`block` 级不可妥协 |

## 项目状态

- ✅ P0 知识层（三份 YAML + 加载器 + 提示词构建）
- ✅ P0 主图规范校验（9 类检查项）
- ✅ P0 本地主图规范化（无需模型）
- ✅ P0 详情图排版引擎（阿语 RTL + 双语）
- ✅ P0 多供应商可插拔模型层
- ⏳ P1 场景图生成效果调优（需要真实商品图）
- ⏳ P2 竞品视觉基线：抓取爆款店铺商品图 → 类目风格统计 → 生成后打分
- ⏳ P3 Streamlit 可视化工作台

## 开发

```bash
python -m pytest -q
```

## 免责声明

本项目为独立开发的第三方工具，与 Noon 官方无隶属或合作关系。平台规则以 Noon Seller Lab 最新官方文档为准，知识层中的规格字段需自行复核后使用。请勿使用本项目处理侵犯他人权利的素材。
