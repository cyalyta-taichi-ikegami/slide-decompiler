"""Gemini によるテキスト翻訳・整形レイヤー

SlideAnalysis 内の全テキスト要素を一括翻訳して新しい SlideAnalysis を返す。
翻訳 API の呼び出し数を最小化するため、全テキストを 1 リクエストにまとめる。
"""
import json
import logging

import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig
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

vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)

_TRANSLATE_PROMPT = """
以下の JSON 配列に含まれる日本語テキストを、
ビジネスプレゼンテーション向けの自然な英語に翻訳してください。

ルール:
- 入力と同じ要素数・同じ順序で JSON 配列として返してください
- 各要素は {{"id": <元のid>, "text": "<英訳>"}} の形式にしてください
- 空文字列はそのまま空文字列で返してください
- 説明・注釈は一切不要です

入力:
{json_input}
"""


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(MAX_RETRY_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=RETRY_MIN_WAIT_SEC, max=RETRY_MAX_WAIT_SEC),
    reraise=True,
)
def _batch_translate(model: GenerativeModel, texts: list[dict]) -> list[dict]:
    """テキスト配列を 1 回の API コールでまとめて翻訳する"""
    json_input = json.dumps(texts, ensure_ascii=False)
    response = model.generate_content(
        _TRANSLATE_PROMPT.format(json_input=json_input),
        generation_config=GenerationConfig(response_mime_type="application/json"),
    )
    return json.loads(response.text)


def translate_elements(analysis: SlideAnalysis, target_lang: str = "en") -> SlideAnalysis:
    """SlideAnalysis 内の全テキスト要素を翻訳して新しい SlideAnalysis を返す。

    Args:
        analysis:    Gemini が返した SlideAnalysis
        target_lang: 翻訳先言語コード（現在 "en" のみサポート）

    Returns:
        テキストが翻訳された新しい SlideAnalysis（元オブジェクトは変更しない）
    """
    if target_lang != "en":
        return analysis  # 翻訳不要の場合はそのまま

    # 翻訳対象のテキストを収集（空テキスト・非編集要素はスキップ）
    targets = [
        {"id": i, "text": e.text_content}
        for i, e in enumerate(analysis.elements)
        if e.is_editable and e.text_content.strip()
    ]

    if not targets:
        return analysis

    model = GenerativeModel(GEMINI_MODEL)
    translated_list = _batch_translate(model, targets)

    # id → 翻訳テキストの辞書を作成
    translated_map: dict[int, str] = {item["id"]: item["text"] for item in translated_list}

    updated_elements = []
    for i, element in enumerate(analysis.elements):
        if i in translated_map:
            updated_elements.append(element.model_copy(update={"text_content": translated_map[i]}))
        else:
            updated_elements.append(element)

    logger.info(f"翻訳完了: {len(targets)} テキストを翻訳")
    return analysis.model_copy(update={"elements": updated_elements})
