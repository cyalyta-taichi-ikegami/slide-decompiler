"""Gemini による画像解析・要素抽出レイヤー

Gemini 3.1 Pro の Structured Outputs（構造化出力）を利用し、
スライド画像内の全要素を SlideAnalysis として確実に返す。
"""
import logging
from functools import partial

import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import (
    GCP_PROJECT_ID,
    GCP_LOCATION,
    GEMINI_MODEL,
    MAX_RETRY_ATTEMPTS,
    RETRY_MIN_WAIT_SEC,
    RETRY_MAX_WAIT_SEC,
)
from models.slide_elements import SlideAnalysis

logger = logging.getLogger(__name__)

# Vertex AI 初期化（モジュールロード時に 1 回だけ実行）
vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)

_ANALYSIS_PROMPT = """
あなたはスライド画像を解析する専門家AIです。
与えられたスライド画像内の「すべて」の視覚的要素を解析し、
以下のルールに厳密に従って JSON を出力してください。

【解析ルール】
1. テキスト要素（タイトル・本文・ラベル・装飾文字・デザイン文字など）を漏れなく抽出する
2. バウンディングボックスは 0〜1000 の正規化座標で指定する（左上が 0,0 / 右下が 1000,1000）
3. color_hex はテキスト・図形の「前景色」を RGB 16進数 (#RRGGBB) で正確に推定する
4. element_type が "image" または "background" の要素は is_editable=false にする
5. テキストを含む要素はすべて is_editable=true にする
6. 背景写真・イラストは element_type="image", is_editable=false で記録する（除去しないため）
"""


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT_SEC, max=RETRY_MAX_WAIT_SEC),
    reraise=True,
)
def analyze_slide(image_bytes: bytes) -> SlideAnalysis:
    """スライド画像を Gemini で解析し SlideAnalysis を返す。

    Args:
        image_bytes: PNG 形式のスライド画像バイト列

    Returns:
        SlideAnalysis（全要素の座標・テキスト・色情報を含む）
    """
    model = GenerativeModel(
        GEMINI_MODEL,
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema=SlideAnalysis.model_json_schema(),
        ),
    )

    image_part = Part.from_data(data=image_bytes, mime_type="image/png")
    response = model.generate_content([_ANALYSIS_PROMPT, image_part])

    analysis = SlideAnalysis.model_validate_json(response.text)
    logger.info(f"解析完了: {len(analysis.elements)} 要素を検出")
    return analysis
