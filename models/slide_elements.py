"""Gemini 構造化出力用 Pydantic データモデル"""
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class ElementType(str, Enum):
    TEXT = "text"
    TITLE = "title"
    SUBTITLE = "subtitle"
    LABEL = "label"
    ICON = "icon"
    ARROW = "arrow"
    SHAPE = "shape"
    IMAGE = "image"         # 写真・イラスト（除去しない）
    BACKGROUND = "background"  # 背景全体（除去しない）
    OTHER = "other"


class BoundingBox(BaseModel):
    y_min: int = Field(..., ge=0, le=1000, description="上端の正規化Y座標（0-1000）")
    x_min: int = Field(..., ge=0, le=1000, description="左端の正規化X座標（0-1000）")
    y_max: int = Field(..., ge=0, le=1000, description="下端の正規化Y座標（0-1000）")
    x_max: int = Field(..., ge=0, le=1000, description="右端の正規化X座標（0-1000）")

    @field_validator("y_max")
    @classmethod
    def y_max_gt_y_min(cls, v: int, info) -> int:
        if "y_min" in info.data and v <= info.data["y_min"]:
            raise ValueError("y_max は y_min より大きい必要があります")
        return v

    @field_validator("x_max")
    @classmethod
    def x_max_gt_x_min(cls, v: int, info) -> int:
        if "x_min" in info.data and v <= info.data["x_min"]:
            raise ValueError("x_max は x_min より大きい必要があります")
        return v


class SlideElement(BaseModel):
    element_type: ElementType = Field(..., description="要素の種類")
    text_content: str = Field(default="", description="OCR で抽出したテキスト（テキスト要素のみ）")
    bounding_box: BoundingBox
    color_hex: str = Field(
        default="#000000",
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="テキストまたは図形の前景 RGB カラーコード（例: #FF5733）",
    )
    font_bold: bool = Field(default=False, description="太字かどうか")
    is_editable: bool = Field(
        default=True,
        description="テキストボックスとして PPTX 上に配置すべき要素か。"
        " IMAGE / BACKGROUND タイプは False にすること。",
    )


class SlideAnalysis(BaseModel):
    elements: list[SlideElement] = Field(..., description="スライド内の全要素リスト")
    background_description: str = Field(default="", description="背景の概要説明（任意）")
