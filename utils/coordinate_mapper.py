"""座標変換ユーティリティ

正規化座標（Gemini 出力の 0-1000 スケール）から
ピクセル座標・EMU・フォントサイズの変換を担う。
"""
from config import (
    SLIDE_WIDTH_EMU,
    SLIDE_HEIGHT_EMU,
    SLIDE_WIDTH_INCHES,
    SLIDE_HEIGHT_INCHES,
    PT_PER_INCH,
    FONT_SIZE_TUNING_FACTOR,
)
from models.slide_elements import BoundingBox


def normalized_to_pixels(
    bbox: BoundingBox,
    image_width: int,
    image_height: int,
) -> tuple[int, int, int, int]:
    """正規化座標（0-1000）→ ピクセル座標 (x_min, y_min, x_max, y_max)"""
    x_min = int((bbox.x_min / 1000) * image_width)
    y_min = int((bbox.y_min / 1000) * image_height)
    x_max = int((bbox.x_max / 1000) * image_width)
    y_max = int((bbox.y_max / 1000) * image_height)
    return x_min, y_min, x_max, y_max


def normalized_to_emu(bbox: BoundingBox) -> tuple[int, int, int, int]:
    """正規化座標（0-1000）→ EMU (left, top, width, height)

    python-pptx の add_textbox / add_picture に渡せる形式で返す。
    """
    left   = int((bbox.x_min / 1000) * SLIDE_WIDTH_EMU)
    top    = int((bbox.y_min / 1000) * SLIDE_HEIGHT_EMU)
    width  = int(((bbox.x_max - bbox.x_min) / 1000) * SLIDE_WIDTH_EMU)
    height = int(((bbox.y_max - bbox.y_min) / 1000) * SLIDE_HEIGHT_EMU)
    return left, top, width, height


def estimate_font_size_pt(bbox: BoundingBox) -> int:
    """バウンディングボックスの高さからフォントサイズ（整数 pt）を推定する。

    計算式：
        H_inches = (y_max - y_min) / 1000 * Slide_Height_Inches
        H_points = H_inches * 72                    # 1 inch = 72 pt
        font_pt  = H_points * FONT_SIZE_TUNING_FACTOR  # PowerPoint バウンド高さ補正

    結果を 6〜144 pt にクランプして返す。
    """
    h_inches = ((bbox.y_max - bbox.y_min) / 1000) * SLIDE_HEIGHT_INCHES
    h_points = h_inches * PT_PER_INCH
    font_pt = h_points * FONT_SIZE_TUNING_FACTOR
    return max(6, min(144, int(font_pt)))
