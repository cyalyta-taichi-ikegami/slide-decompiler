"""PPTX の各スライドを PNG 画像に変換するユーティリティ

LibreOffice の headless モードを使ってスライドを PNG に書き出す。
Cloud Run の Dockerfile で libreoffice パッケージをインストールすること。
"""
import subprocess
import tempfile
from pathlib import Path


def pptx_slides_to_images(pptx_path: str, dpi: int = 150) -> list[bytes]:
    """PPTX ファイルをスライドごとの PNG bytes リストに変換する。

    Args:
        pptx_path: 入力 PPTX ファイルのパス
        dpi: 出力解像度（デフォルト 150dpi。高品質にしたい場合は 200 以上を推奨）

    Returns:
        スライド順の PNG bytes リスト（インデックス 0 = 1 枚目）

    Raises:
        RuntimeError: LibreOffice が見つからない、または変換失敗した場合
    """
    pptx_path = Path(pptx_path).resolve()
    if not pptx_path.exists():
        raise FileNotFoundError(f"入力ファイルが見つかりません: {pptx_path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to", "png",
                "--outdir", tmpdir,
                str(pptx_path),
            ],
            capture_output=True,
            text=True,
            timeout=300,  # 大きな PPTX でも 5 分あれば十分
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice の変換に失敗しました:\n{result.stderr}"
            )

        # LibreOffice は "ファイル名-スライド番号.png" という命名規則で出力する
        png_files = sorted(Path(tmpdir).glob("*.png"))
        if not png_files:
            raise RuntimeError(
                "LibreOffice が PNG を出力しませんでした。"
                " PPTX ファイルが壊れていないか確認してください。"
            )

        return [f.read_bytes() for f in png_files]
