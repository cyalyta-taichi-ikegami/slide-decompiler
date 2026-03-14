"""pptx-fixer メインエントリーポイント

PPTX ファイルを丸ごと受け取り、全スライドを処理して
編集可能な PPTX を出力する。

使い方（ローカル / Cloud Run Jobs 共通）:
    python main.py --input input.pptx --output output.pptx [--lang en]

Cloud Run Jobs で実行する場合は環境変数で入出力パスを渡すことも可能:
    INPUT_PATH  / OUTPUT_PATH を設定すると --input / --output の代わりに使われる

必須環境変数:
    GCP_PROJECT_ID    Google Cloud プロジェクト ID

任意環境変数:
    GCP_LOCATION          Vertex AI リージョン（デフォルト: us-central1）
    GEMINI_MODEL          使用する Gemini モデル名
    IMAGEN_MODEL          使用する Imagen モデル名
    MAX_CONCURRENT_SLIDES 同時処理スライド数（デフォルト: 3）
    INPUT_PATH            入力 PPTX パス（--input の代替）
    OUTPUT_PATH           出力 PPTX パス（--output の代替）
"""
import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

import config  # 環境変数バリデーション（GCP_PROJECT_ID 未設定なら KeyError で即終了）
from config import SLIDE_WIDTH_EMU, SLIDE_HEIGHT_EMU, MAX_CONCURRENT_SLIDES
from pipeline.assembler import build_slide
from pipeline.slide_processor import process_slide
from utils.pptx_to_images import pptx_slides_to_images

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def run_pipeline(
    input_pptx: str,
    output_pptx: str,
    target_lang: str = "en",
) -> None:
    """PPTX 全スライドを並列処理して編集可能な PPTX を出力する。

    並列処理フロー:
        1. PPTX → PNG 変換（LibreOffice、順次）
        2. 各スライドを asyncio.gather で並列処理
           - セマフォで同時実行数を MAX_CONCURRENT_SLIDES に制限
             （Vertex AI の TPM クォータ超過を防ぐ）
        3. スライド順序通りに PPTX を組み立てて保存

    タイムアウト対策:
        Cloud Run Jobs はリクエストタイムアウトがなく最大 24 時間実行できるため、
        スライド数が多い場合や高品質設定（baseSteps を上げた場合）でも
        タイムアウトなく処理が完了する。
    """
    logger.info(f"入力: {input_pptx}")
    logger.info("スライドを PNG に変換中（LibreOffice）...")
    slide_images: list[bytes] = pptx_slides_to_images(input_pptx)
    total = len(slide_images)
    logger.info(f"合計 {total} スライドを処理します（同時実行数: {MAX_CONCURRENT_SLIDES}）")

    # 出力 Presentation を 16:9 で初期化
    prs = Presentation()
    prs.slide_width = Emu(SLIDE_WIDTH_EMU)
    prs.slide_height = Emu(SLIDE_HEIGHT_EMU)

    # セマフォで API クォータを保護する
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_SLIDES)

    async def process_with_semaphore(idx: int, image_bytes: bytes):
        async with semaphore:
            return await process_slide(idx, image_bytes, target_lang)

    tasks = [process_with_semaphore(i, img) for i, img in enumerate(slide_images)]

    # return_exceptions=True で 1 枚の失敗が全体を止めないようにする
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # エラーログを出してから失敗スライドの有無を確認
    results: dict[int, tuple[bytes, object]] = {}
    failed: list[int] = []
    for result in raw_results:
        if isinstance(result, Exception):
            logger.error(f"スライド処理中にエラーが発生しました: {result}")
            failed.append(-1)
        else:
            idx, bg_bytes, analysis = result
            results[idx] = (bg_bytes, analysis)

    if failed:
        raise RuntimeError(f"{len(failed)} 枚のスライドで処理に失敗しました。ログを確認してください。")

    # スライド順序通りに組み立て
    logger.info("PPTX を組み立て中...")
    for idx in range(total):
        bg_bytes, analysis = results[idx]
        build_slide(prs, bg_bytes, analysis)

    prs.save(output_pptx)
    logger.info(f"完了: {output_pptx}")


def _parse_args() -> tuple[str, str, str]:
    """コマンドライン引数または環境変数から入出力パスと言語を取得する"""
    parser = argparse.ArgumentParser(description="PPTX 画像 → 編集可能 PPTX 変換ツール")
    parser.add_argument("--input",  default=os.environ.get("INPUT_PATH"),  help="入力 PPTX ファイルパス")
    parser.add_argument("--output", default=os.environ.get("OUTPUT_PATH"), help="出力 PPTX ファイルパス")
    parser.add_argument("--lang",   default="en",                          help="翻訳先言語コード（デフォルト: en）")
    args = parser.parse_args()

    if not args.input:
        parser.error("--input または環境変数 INPUT_PATH を指定してください")
    if not args.output:
        parser.error("--output または環境変数 OUTPUT_PATH を指定してください")

    return args.input, args.output, args.lang


def main() -> None:
    input_path, output_path, lang = _parse_args()
    asyncio.run(run_pipeline(input_path, output_path, lang))


if __name__ == "__main__":
    main()
