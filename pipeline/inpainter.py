"""Imagen 3 によるインペインティング（テキスト除去・背景復元）レイヤー

EDIT_MODE_INPAINT_REMOVAL を使い、マスク領域のテキスト・図形を
周囲の背景で自然に補完した画像（PNG bytes）を返す。
"""
import logging

import vertexai
from vertexai.preview.vision_models import ImageGenerationModel
from vertexai.preview.vision_models import Image as VertexImage
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import (
    GCP_PROJECT_ID,
    GCP_LOCATION,
    IMAGEN_MODEL,
    MASK_DILATION,
    INPAINT_BASE_STEPS,
    MAX_RETRY_ATTEMPTS,
    RETRY_MIN_WAIT_SEC,
    RETRY_MAX_WAIT_SEC,
)

logger = logging.getLogger(__name__)

vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT_SEC, max=RETRY_MAX_WAIT_SEC),
    reraise=True,
)
def inpaint_slide(image_bytes: bytes, mask_bytes: bytes) -> bytes:
    """元画像とマスク画像を Imagen 3 に渡してインペインティングを実行する。

    Args:
        image_bytes: 元のスライド画像（PNG bytes）
        mask_bytes:  除去対象領域が白のバイナリマスク（PNG bytes）

    Returns:
        テキスト・図形が除去された背景のみの画像（PNG bytes）

    Note:
        MASK_DILATION（デフォルト 1.5%）でマスクをわずかに膨張させることで
        アンチエイリアスのハロー現象を防ぐ。
        INPAINT_BASE_STEPS を上げると品質が向上するがレイテンシも増加する。
    """
    model = ImageGenerationModel.from_pretrained(IMAGEN_MODEL)

    base_image = VertexImage(image_bytes=image_bytes)
    mask_image = VertexImage(image_bytes=mask_bytes)

    result = model.edit_image(
        base_image=base_image,
        mask=mask_image,
        edit_mode="inpaint-removal",
        mask_dilation=MASK_DILATION,
        base_steps=INPAINT_BASE_STEPS,
    )

    output_bytes: bytes = result.images[0]._image_bytes
    logger.info("インペインティング完了")
    return output_bytes
