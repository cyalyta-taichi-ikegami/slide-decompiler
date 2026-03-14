"""1 スライド分のパイプライン全処理（非同期）

処理順:
    1. Gemini 解析（座標・テキスト・色を抽出）
    2. マスク生成（CPU 処理）
    3. インペインティング & 翻訳 ← 独立しているので並列実行
    4. 結果を返す（組み立ては main で担当）
"""
import asyncio
import io
import logging
from functools import partial

from PIL import Image

from models.slide_elements import SlideAnalysis
from pipeline.analyzer import analyze_slide
from pipeline.inpainter import inpaint_slide
from pipeline.translator import translate_elements
from utils.mask_generator import generate_mask

logger = logging.getLogger(__name__)


async def process_slide(
    slide_index: int,
    image_bytes: bytes,
    target_lang: str = "en",
) -> tuple[int, bytes, SlideAnalysis]:
    """1 スライドを非同期で処理する。

    すべての同期 API 呼び出しを run_in_executor でスレッドプールに委譲し、
    イベントループをブロックしない。
    インペインティングと翻訳は互いに独立しているため asyncio.gather で並列実行する。

    Args:
        slide_index: スライド番号（0 始まり）
        image_bytes: スライド画像（PNG bytes）
        target_lang: 翻訳先言語コード（"en" など）

    Returns:
        (slide_index, 背景画像 bytes, 翻訳済み SlideAnalysis)
    """
    loop = asyncio.get_running_loop()
    logger.info(f"[スライド {slide_index}] 処理開始")

    # 画像サイズを取得（マスク生成に必要）
    with Image.open(io.BytesIO(image_bytes)) as img:
        img_width, img_height = img.size

    # Step 1: Gemini 解析
    logger.info(f"[スライド {slide_index}] Gemini 解析中...")
    analysis: SlideAnalysis = await loop.run_in_executor(
        None, partial(analyze_slide, image_bytes)
    )

    # Step 2: バイナリマスク生成（CPU 処理）
    logger.info(f"[スライド {slide_index}] マスク生成中...")
    mask_bytes: bytes = await loop.run_in_executor(
        None, partial(generate_mask, img_width, img_height, analysis)
    )

    # Step 3 & 4: インペインティングと翻訳を並列実行（最も時間がかかる部分）
    logger.info(f"[スライド {slide_index}] インペインティング & 翻訳 並列実行中...")
    background_bytes, translated_analysis = await asyncio.gather(
        loop.run_in_executor(None, partial(inpaint_slide, image_bytes, mask_bytes)),
        loop.run_in_executor(None, partial(translate_elements, analysis, target_lang)),
    )

    logger.info(f"[スライド {slide_index}] 処理完了")
    return slide_index, background_bytes, translated_analysis
