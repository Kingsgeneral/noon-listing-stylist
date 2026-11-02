"""图像模型抽象层：所有供应商实现同一接口，方便替换与 A/B。"""

from __future__ import annotations

import io
from abc import ABC, abstractmethod

from PIL import Image


class ImageModel(ABC):
    name: str = "base"

    def __init__(self, config=None):
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, size: str = "1024x1024") -> bytes:
        """文生图，返回图片字节流。"""

    @abstractmethod
    def edit(self, image: bytes, prompt: str, size: str = "1024x1024") -> bytes:
        """图生图/局部编辑，返回图片字节流。"""

    def edit_file(self, image_path, prompt: str, size: str = "1024x1024") -> bytes:
        return self.edit(open(image_path, "rb").read(), prompt, size=size)

    @staticmethod
    def to_png_bytes(image: Image.Image) -> bytes:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()


class MockImageModel(ImageModel):
    """占位模型：不调用任何网络，用于跑通流程和单元测试。"""

    name = "mock"

    def generate(self, prompt: str, size: str = "1024x1024") -> bytes:
        w, h = (int(x) for x in size.lower().split("x"))
        img = Image.new("RGB", (w, h), "#F7F5EF")
        return self.to_png_bytes(img)

    def edit(self, image: bytes, prompt: str, size: str = "1024x1024") -> bytes:
        img = Image.open(io.BytesIO(image)).convert("RGB")
        return self.to_png_bytes(img)
