"""テキスト除去用バイナリマスク画像の動的生成

Gemini が返したバウンディングボックス群を基に、
除去対象領域を白（255）・保持領域を黒（0）で描いた
PNG バイナリを生成する。
"""
import io
from PIL import Image, ImageDraw

from models.slide_elements import SlideAnalysis, ElementType
from utils.coordinate_mapper import normalized_to_pixels

# これらのタイプがマスク（除去）対象
_REMOVABLE_TYPES = frozenset({
    ElementType.TEXT,
    ElementType.TITLE,
    ElementType.SUBTITLE,
    ElementType.LABEL,
    ElementType.ICON,
    ElementType.ARROW,
    ElementType.SHAPE,
    ElementType.OTHER,
})


def generate_mask(
    image_width: int,
    image_height: int,
    analysis: SlideAnalysis,
) -> bytes:
    """除去対象要素の位置を白で塗りつぶしたバイナリマスク画像（PNG）を返す。

    Args:
        image_width:  元画像の横ピクセル数
        image_height: 元画像の縦ピクセル数
        analysis:     Gemini が返した SlideAnalysis

    Returns:
        PNG 形式のマスク画像バイト列
    """
    # 黒一色のキャンバス（保持領域 = 黒）
    mask = Image.new("L", (image_width, image_height), color=0)
    draw = ImageDraw.Draw(mask)

    for element in analysis.elements:
        if element.element_type not in _REMOVABLE_TYPES:
            continue

        x_min, y_min, x_max, y_max = normalized_to_pixels(
            element.bounding_box, image_width, image_height
        )
        # 除去領域を白で描画（Imagen 3 が白い部分をインペインティングする）
        draw.rectangle([x_min, y_min, x_max, y_max], fill=255)

    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    return buf.getvalue()
